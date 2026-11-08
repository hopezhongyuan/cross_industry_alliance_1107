"""M2 收尾：售后超时转仲裁、平台裁定与责任方退款。"""

from datetime import timedelta
from io import StringIO
from uuid import uuid4

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AppUser
from apps.aftersales.models import AfterSale, ArbitrationCase
from apps.aftersales.services import escalate_due_after_sales
from apps.catalog.models import Category, Product, ProductSku
from apps.ledger.models import MerchantAccount, SettlementItem
from apps.merchants.models import Merchant, MerchantStaff
from apps.orders.models import Order
from apps.payments.models import PaymentOrder


class ArbitrationFlowTests(TestCase):
    def setUp(self):
        self.consumer = AppUser.objects.create_user(phone="13900000020", password="pass12345")
        self.staff = AppUser.objects.create_user(phone="13900000021", password="pass12345")
        self.admin = AppUser.objects.create_user(phone="13900000022", password="pass12345", is_staff=True)
        self.client = APIClient()
        self.client.force_authenticate(self.consumer)
        self.merchant_client = APIClient()
        self.merchant_client.force_authenticate(self.staff)
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(self.admin)

        self.category = Category.objects.create(name="仲裁类目", commission_rate="0.0500")
        self.merchant = Merchant.objects.create(
            merchant_no="M201", name="仲裁商户", category=self.category, status=Merchant.Status.ACTIVE
        )
        MerchantStaff.objects.create(merchant=self.merchant, user=self.staff, role=MerchantStaff.Role.OWNER)
        self.product = Product.objects.create(
            merchant=self.merchant,
            category=self.category,
            type=Product.Type.PHYSICAL,
            title="仲裁商品",
            price=1000,
            status=Product.Status.ON_SALE,
        )
        self.sku = ProductSku.objects.create(product=self.product, sku_code="ARB-SKU", price=1000, stock=10)

    def _completed_order(self):
        payload = {
            "merchant_id": self.merchant.id,
            "order_type": "EXPRESS",
            "items": [{"product_id": self.product.id, "sku_id": self.sku.id, "quantity": 1}],
            "contact": {"name": "张三", "phone": "13800138000", "address_detail": "测试地址"},
        }
        response = self.client.post("/api/v1/orders/", payload, format="json", HTTP_IDEMPOTENCY_KEY=uuid4().hex)
        self.assertEqual(response.status_code, 201, response.data)
        order = Order.objects.get(pk=response.data["data"]["id"])

        pay = self.client.post(f"/api/v1/orders/{order.id}/pay/", {}, format="json", HTTP_IDEMPOTENCY_KEY=uuid4().hex)
        self.assertEqual(pay.status_code, 200, pay.data)
        payment = PaymentOrder.objects.get(order=order)
        self.assertEqual(
            self.client.post(
                "/api/v1/callback/wechat/pay/",
                {
                    "payment_no": payment.payment_no,
                    "transaction_id": f"txn-{uuid4().hex[:12]}",
                    "amount": payment.amount,
                    "trade_state": "SUCCESS",
                },
                format="json",
            ).status_code,
            200,
        )
        self.merchant_client.post(f"/api/v1/merchant/orders/{order.id}/accept/", {}, format="json")
        self.merchant_client.post(f"/api/v1/merchant/orders/{order.id}/ship/", {}, format="json")
        self.assertEqual(self.client.post(f"/api/v1/orders/{order.id}/confirm/", {}, format="json").status_code, 200)
        order.refresh_from_db()
        return order

    def _applied_after_sale(self, amount=500, evidence=None):
        order = self._completed_order()
        response = self.client.post(
            "/api/v1/after-sales/",
            {
                "order_id": order.id,
                "type": "REFUND_ONLY",
                "reason_code": "SERVICE_ISSUE",
                "request_amount": amount,
                "evidence": evidence or [],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        return AfterSale.objects.get(pk=response.data["data"]["id"])

    def _overdue_after_sale(self, amount=500):
        after_sale = self._applied_after_sale(amount)
        AfterSale.objects.filter(pk=after_sale.pk).update(deadline_at=timezone.now() - timedelta(minutes=5))
        after_sale.refresh_from_db()
        return after_sale

    def _escalate(self, after_sale):
        out = StringIO()
        call_command("escalate_after_sales", stdout=out)
        after_sale.refresh_from_db()
        return after_sale.arbitration_case

    def _rule(self, case, liability, refund_amount=0, ruling="裁定说明"):
        response = self.admin_client.post(
            f"/api/v1/admin/arbitrations/{case.id}/rule/",
            {"liability": liability, "refund_amount": refund_amount, "ruling": ruling},
            format="json",
        )
        return response

    def _assert_balanced(self):
        call_command("audit_ledger", stdout=StringIO())

    def test_admin_arbitration_detail_includes_after_sale_and_evidence(self):
        after_sale = self._applied_after_sale(amount=1000, evidence=["https://example.com/a.png"])
        AfterSale.objects.filter(pk=after_sale.pk).update(deadline_at=timezone.now() - timedelta(minutes=5))
        after_sale.refresh_from_db()
        case = self._escalate(after_sale)
        response = self.admin_client.get(f"/api/v1/admin/arbitrations/{case.id}/")
        self.assertEqual(response.status_code, 200, response.data)
        data = response.data["data"]
        self.assertEqual(data["case_no"], case.case_no)
        self.assertEqual(data["after_sale"]["after_sale_no"], after_sale.after_sale_no)
        self.assertEqual(data["after_sale"]["request_amount"], 1000)
        self.assertEqual(data["after_sale"]["evidence"], ["https://example.com/a.png"])
        self.assertEqual(data["after_sale"]["merchant_name"], self.merchant.name)

        forbidden = self.client.get(f"/api/v1/admin/arbitrations/{case.id}/")
        self.assertEqual(forbidden.status_code, 403)

    def test_apply_after_sale_sets_merchant_deadline(self):
        after_sale = self._applied_after_sale()
        delta = after_sale.deadline_at - timezone.now()
        self.assertGreater(delta, timedelta(hours=47))
        self.assertLess(delta, timedelta(hours=49))
        self.assertEqual(after_sale.status, AfterSale.Status.APPLIED)

    def test_overdue_after_sale_escalates_to_arbitration_once(self):
        after_sale = self._overdue_after_sale()
        case = self._escalate(after_sale)

        self.assertIsNotNone(case)
        self.assertEqual(case.status, ArbitrationCase.Status.PENDING)
        self.assertEqual(case.amount, 500)
        self.assertGreater(case.deadline_at - timezone.now(), timedelta(hours=71))
        self.assertEqual(after_sale.status, AfterSale.Status.ARBITRATING)
        self.assertEqual(after_sale.arbitration_case_id, case.id)

        order = Order.objects.get(pk=after_sale.order_id)
        self.assertEqual(order.status, Order.Status.AFTER_SALE)
        self.assertEqual(SettlementItem.objects.get(order=order).status, SettlementItem.Status.FROZEN)

        call_command("escalate_after_sales", stdout=StringIO())
        self.assertEqual(ArbitrationCase.objects.filter(after_sale=after_sale).count(), 1)
        self._assert_balanced()

    def test_not_due_after_sale_stays_applied(self):
        after_sale = self._applied_after_sale()
        self.assertEqual(escalate_due_after_sales(), 0)
        after_sale.refresh_from_db()
        self.assertEqual(after_sale.status, AfterSale.Status.APPLIED)
        self.assertFalse(ArbitrationCase.objects.exists())

    def test_rule_merchant_liability_full_refund(self):
        after_sale = self._overdue_after_sale(amount=1000)
        case = self._escalate(after_sale)
        response = self._rule(case, "MERCHANT", refund_amount=1000, ruling="商户未履约")

        self.assertEqual(response.status_code, 200, response.data)
        after_sale.refresh_from_db()
        case.refresh_from_db()
        order = Order.objects.get(pk=after_sale.order_id)
        item = SettlementItem.objects.get(order=order)
        account = MerchantAccount.objects.get(merchant=self.merchant)

        self.assertEqual(case.status, ArbitrationCase.Status.DECIDED)
        self.assertEqual(case.liability, ArbitrationCase.Liability.MERCHANT)
        self.assertEqual(case.decided_by_id, self.admin.id)
        self.assertEqual(after_sale.status, AfterSale.Status.COMPLETED)
        self.assertEqual(after_sale.approved_amount, 1000)
        self.assertEqual(order.status, Order.Status.REFUNDED)
        self.assertEqual(item.status, SettlementItem.Status.CANCELLED)
        self.assertEqual(account.pending_balance, 0)
        self.assertEqual(account.frozen_balance, 0)
        self._assert_balanced()

    def test_rule_shared_liability_partial_refund(self):
        after_sale = self._overdue_after_sale(amount=1000)
        case = self._escalate(after_sale)
        response = self._rule(case, "SHARED", refund_amount=500, ruling="双方共担")

        self.assertEqual(response.status_code, 200, response.data)
        after_sale.refresh_from_db()
        order = Order.objects.get(pk=after_sale.order_id)
        item = SettlementItem.objects.get(order=order)
        account = MerchantAccount.objects.get(merchant=self.merchant)

        self.assertEqual(after_sale.status, AfterSale.Status.COMPLETED)
        self.assertEqual(order.status, Order.Status.COMPLETED)
        self.assertEqual(order.refunded_amount, 500)
        self.assertEqual(item.status, SettlementItem.Status.PENDING)
        self.assertEqual(item.refund_amount, 500)
        self.assertEqual(account.pending_balance, 500)
        self.assertEqual(account.frozen_balance, 0)
        self._assert_balanced()

    def test_rule_user_liability_rejects_and_unfreezes(self):
        after_sale = self._overdue_after_sale(amount=1000)
        case = self._escalate(after_sale)
        response = self._rule(case, "USER", refund_amount=0, ruling="用户举证不足")

        self.assertEqual(response.status_code, 200, response.data)
        after_sale.refresh_from_db()
        order = Order.objects.get(pk=after_sale.order_id)
        item = SettlementItem.objects.get(order=order)
        account = MerchantAccount.objects.get(merchant=self.merchant)

        self.assertEqual(after_sale.status, AfterSale.Status.CANCELLED)
        self.assertIsNotNone(after_sale.closed_at)
        self.assertEqual(order.status, Order.Status.COMPLETED)
        self.assertEqual(item.status, SettlementItem.Status.PENDING)
        self.assertEqual(account.pending_balance, 1000)
        self.assertEqual(account.frozen_balance, 0)
        self._assert_balanced()

    def test_rule_platform_liability_refunds_without_charging_merchant(self):
        after_sale = self._overdue_after_sale(amount=1000)
        case = self._escalate(after_sale)
        response = self._rule(case, "PLATFORM", refund_amount=1000, ruling="不可归责，平台承担")

        self.assertEqual(response.status_code, 200, response.data)
        after_sale.refresh_from_db()
        order = Order.objects.get(pk=after_sale.order_id)
        item = SettlementItem.objects.get(order=order)
        account = MerchantAccount.objects.get(merchant=self.merchant)

        self.assertEqual(after_sale.status, AfterSale.Status.COMPLETED)
        self.assertEqual(order.status, Order.Status.REFUNDED)
        self.assertEqual(item.status, SettlementItem.Status.PENDING)
        self.assertEqual(item.refund_amount, 0)
        self.assertEqual(account.pending_balance, 1000)
        self.assertEqual(account.frozen_balance, 0)
        self._assert_balanced()

    def test_rule_requires_platform_admin(self):
        after_sale = self._overdue_after_sale(amount=1000)
        case = self._escalate(after_sale)
        response = self.client.post(
            f"/api/v1/admin/arbitrations/{case.id}/rule/",
            {"liability": "MERCHANT", "refund_amount": 1000, "ruling": "越权"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["code"], "PERMISSION_DENIED")

    def test_rule_twice_conflicts(self):
        after_sale = self._overdue_after_sale(amount=500)
        case = self._escalate(after_sale)
        self.assertEqual(self._rule(case, "MERCHANT", refund_amount=500).status_code, 200)
        second = self._rule(case, "USER", refund_amount=0)
        self.assertEqual(second.status_code, 409)
        self.assertEqual(second.data["code"], "ARBITRATION_STATE_CONFLICT")

    def test_rule_amount_exceeds_refundable(self):
        after_sale = self._overdue_after_sale(amount=500)
        case = self._escalate(after_sale)
        response = self._rule(case, "MERCHANT", refund_amount=1200)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "REFUND_AMOUNT_EXCEEDED")

    def test_user_liability_with_refund_is_rejected(self):
        after_sale = self._overdue_after_sale(amount=500)
        case = self._escalate(after_sale)
        response = self._rule(case, "USER", refund_amount=500)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")

    def test_rule_requires_arbitrating_status(self):
        after_sale = self._applied_after_sale()
        case = ArbitrationCase.objects.create(after_sale=after_sale, amount=after_sale.request_amount)
        response = self._rule(case, "MERCHANT", refund_amount=500)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "ARBITRATION_STATE_CONFLICT")
