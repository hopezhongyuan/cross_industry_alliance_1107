"""M2 履约、核销、售后与退款闭环测试。"""

from datetime import timedelta
from uuid import uuid4

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AppUser
from apps.aftersales.models import AfterSale
from apps.catalog.models import Category, Product, ProductSku, ServiceSlot
from apps.fulfillment.models import VerifyCode
from apps.ledger.models import MerchantAccount, SettlementItem
from apps.merchants.models import Merchant, MerchantStaff
from apps.orders.models import Order
from apps.payments.models import PaymentOrder, RefundOrder


class M2FlowTests(TestCase):
    def setUp(self):
        self.consumer = AppUser.objects.create_user(phone="13900000010", password="pass12345")
        self.staff = AppUser.objects.create_user(phone="13900000011", password="pass12345")
        self.client = APIClient()
        self.client.force_authenticate(self.consumer)
        self.merchant_client = APIClient()
        self.merchant_client.force_authenticate(self.staff)

        self.category = Category.objects.create(name="M2 类目", commission_rate="0.0500")
        self.merchant = Merchant.objects.create(
            merchant_no="M200", name="M2 商户", category=self.category, status=Merchant.Status.ACTIVE
        )
        MerchantStaff.objects.create(merchant=self.merchant, user=self.staff, role=MerchantStaff.Role.OWNER)

        self.product = Product.objects.create(
            merchant=self.merchant,
            category=self.category,
            type=Product.Type.PHYSICAL,
            title="M2 实物商品",
            price=1000,
            status=Product.Status.ON_SALE,
        )
        self.sku = ProductSku.objects.create(product=self.product, sku_code="M2-SKU", price=1000, stock=10)
        self.service = Product.objects.create(
            merchant=self.merchant,
            category=self.category,
            type=Product.Type.SERVICE,
            title="M2 服务",
            price=3000,
            status=Product.Status.ON_SALE,
            appointment_required=True,
        )
        self.service_sku = ProductSku.objects.create(product=self.service, sku_code="M2-SERVICE", price=3000, stock=5)
        self.slot = ServiceSlot.objects.create(
            product=self.service,
            slot_date=timezone.localdate() + timedelta(days=1),
            start_time="10:00",
            end_time="10:30",
            capacity=2,
        )

    def _create_order(self, order_type="EXPRESS", product=None, sku=None, quantity=1, appointment=None):
        product = product or self.product
        sku = sku or self.sku
        payload = {
            "merchant_id": self.merchant.id,
            "order_type": order_type,
            "items": [{"product_id": product.id, "sku_id": sku.id, "quantity": quantity}],
            "contact": {"name": "张三", "phone": "13800138000", "address_detail": "测试地址"},
        }
        if appointment:
            payload["appointment"] = appointment
        response = self.client.post("/api/v1/orders/", payload, format="json", HTTP_IDEMPOTENCY_KEY=uuid4().hex)
        self.assertEqual(response.status_code, 201, response.data)
        return Order.objects.get(pk=response.data["data"]["id"])

    def _pay(self, order):
        response = self.client.post(
            f"/api/v1/orders/{order.id}/pay/",
            {},
            format="json",
            HTTP_IDEMPOTENCY_KEY=uuid4().hex,
        )
        self.assertEqual(response.status_code, 200, response.data)
        payment = PaymentOrder.objects.get(order=order)
        callback = self.client.post(
            "/api/v1/callback/wechat/pay/",
            {
                "payment_no": payment.payment_no,
                "transaction_id": f"txn-{uuid4().hex[:12]}",
                "amount": payment.amount,
                "trade_state": "SUCCESS",
            },
            format="json",
        )
        self.assertEqual(callback.status_code, 200, callback.data)
        order.refresh_from_db()
        return payment

    def _complete_express(self):
        order = self._create_order()
        self._pay(order)
        self.merchant_client.post(f"/api/v1/merchant/orders/{order.id}/accept/", {}, format="json")
        self.merchant_client.post(
            f"/api/v1/merchant/orders/{order.id}/ship/",
            {"logistics_company": "顺丰", "logistics_no": "SF123"},
            format="json",
        )
        response = self.client.post(f"/api/v1/orders/{order.id}/confirm/", {}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        order.refresh_from_db()
        return order

    def test_accept_ship_confirm_completes_and_creates_settlement(self):
        order = self._create_order()
        self._pay(order)

        accepted = self.merchant_client.post(f"/api/v1/merchant/orders/{order.id}/accept/", {}, format="json")
        self.assertEqual(accepted.status_code, 200, accepted.data)
        self.assertEqual(accepted.data["data"]["status"], "PENDING_FULFILL")

        shipped = self.merchant_client.post(
            f"/api/v1/merchant/orders/{order.id}/ship/",
            {"logistics_company": "顺丰", "logistics_no": "SF123"},
            format="json",
        )
        self.assertEqual(shipped.status_code, 200, shipped.data)
        self.assertEqual(shipped.data["data"]["status"], "FULFILLING")
        self.assertEqual(shipped.data["data"]["delivery"]["logistics_no"], "SF123")

        confirmed = self.client.post(f"/api/v1/orders/{order.id}/confirm/", {}, format="json")
        self.assertEqual(confirmed.status_code, 200, confirmed.data)
        self.assertEqual(confirmed.data["data"]["status"], "COMPLETED")
        item = SettlementItem.objects.get(order=order)
        self.assertEqual(item.net_amount, 950)
        self.assertEqual(item.status, SettlementItem.Status.PENDING)
        order.refresh_from_db()
        self.assertEqual(item.due_at, order.completed_at + timedelta(days=7))

    def test_service_verify_completes_order(self):
        order = self._create_order(
            order_type="SERVICE",
            product=self.service,
            sku=self.service_sku,
            appointment={"slot_id": self.slot.id},
        )
        self._pay(order)
        self.merchant_client.post(f"/api/v1/merchant/orders/{order.id}/accept/", {}, format="json")
        code = VerifyCode.objects.get(order=order)
        response = self.merchant_client.post("/api/v1/merchant/verify/", {"code": code.code}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.COMPLETED)
        code.refresh_from_db()
        self.assertEqual(code.status, VerifyCode.Status.USED)
        self.assertTrue(SettlementItem.objects.filter(order=order, status="PENDING").exists())

    def test_pickup_verify_requires_ready_state(self):
        order = self._create_order(order_type="PICKUP")
        self._pay(order)
        self.merchant_client.post(f"/api/v1/merchant/orders/{order.id}/accept/", {}, format="json")
        code = VerifyCode.objects.get(order=order)

        early = self.merchant_client.post("/api/v1/merchant/verify/", {"code": code.code}, format="json")
        self.assertEqual(early.status_code, 409)

        self.merchant_client.post(f"/api/v1/merchant/orders/{order.id}/ship/", {}, format="json")
        ok = self.merchant_client.post("/api/v1/merchant/verify/", {"code": code.code}, format="json")
        self.assertEqual(ok.status_code, 200, ok.data)

    def test_merchant_reject_refunds_and_restores_stock(self):
        order = self._create_order()
        self._pay(order)
        response = self.merchant_client.post(
            f"/api/v1/merchant/orders/{order.id}/reject/",
            {"reason": "无法履约"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.REFUNDED)
        self.assertEqual(order.refunded_amount, 1000)
        refund = RefundOrder.objects.get(order=order)
        self.assertEqual(refund.status, RefundOrder.Status.SUCCESS)
        self.assertEqual(MerchantAccount.objects.get(merchant=self.merchant).pending_balance, 0)
        self.sku.refresh_from_db()
        self.assertEqual(self.sku.sold_stock, 0)

    def test_after_sale_agree_partial_refund(self):
        order = self._complete_express()
        applied = self.client.post(
            "/api/v1/after-sales/",
            {
                "order_id": order.id,
                "type": "REFUND_ONLY",
                "reason_code": "SERVICE_ISSUE",
                "request_amount": 500,
                "description": "部分不满意",
            },
            format="json",
        )
        self.assertEqual(applied.status_code, 201, applied.data)
        after_sale = AfterSale.objects.get(pk=applied.data["data"]["id"])
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.AFTER_SALE)
        item = SettlementItem.objects.get(order=order)
        self.assertEqual(item.status, SettlementItem.Status.FROZEN)
        account = MerchantAccount.objects.get(merchant=self.merchant)
        self.assertEqual(account.frozen_balance, 1000)
        self.assertEqual(account.pending_balance, 0)

        decided = self.merchant_client.post(
            f"/api/v1/merchant/after-sales/{after_sale.id}/decision/",
            {"decision": "AGREE", "approved_amount": 500, "reason": "补偿"},
            format="json",
        )
        self.assertEqual(decided.status_code, 200, decided.data)
        after_sale.refresh_from_db()
        order.refresh_from_db()
        item.refresh_from_db()
        account.refresh_from_db()
        self.assertEqual(after_sale.status, AfterSale.Status.COMPLETED)
        self.assertEqual(order.status, Order.Status.COMPLETED)
        self.assertEqual(order.refunded_amount, 500)
        self.assertEqual(item.status, SettlementItem.Status.PENDING)
        self.assertEqual(item.refund_amount, 500)
        self.assertEqual(account.frozen_balance, 0)
        self.assertEqual(account.pending_balance, 500)

    def test_after_sale_reject_unfreezes(self):
        order = self._complete_express()
        applied = self.client.post(
            "/api/v1/after-sales/",
            {"order_id": order.id, "type": "REFUND_ONLY", "reason_code": "OTHER", "request_amount": 500},
            format="json",
        )
        after_sale_id = applied.data["data"]["id"]
        decided = self.merchant_client.post(
            f"/api/v1/merchant/after-sales/{after_sale_id}/decision/",
            {"decision": "REJECT", "reason": "不符合条件"},
            format="json",
        )
        self.assertEqual(decided.status_code, 200, decided.data)
        order.refresh_from_db()
        item = SettlementItem.objects.get(order=order)
        account = MerchantAccount.objects.get(merchant=self.merchant)
        self.assertEqual(order.status, Order.Status.COMPLETED)
        self.assertEqual(item.status, SettlementItem.Status.PENDING)
        self.assertEqual(account.frozen_balance, 0)
        self.assertEqual(account.pending_balance, 1000)

    def test_review_once_per_order(self):
        order = self._complete_express()
        first = self.client.post(f"/api/v1/orders/{order.id}/review/", {"score": 5, "content": "很好"}, format="json")
        self.assertEqual(first.status_code, 201, first.data)
        second = self.client.post(f"/api/v1/orders/{order.id}/review/", {"score": 4}, format="json")
        self.assertEqual(second.status_code, 409)

    def test_non_staff_cannot_accept(self):
        order = self._create_order()
        self._pay(order)
        response = self.client.post(f"/api/v1/merchant/orders/{order.id}/accept/", {}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["code"], "PERMISSION_DENIED")
