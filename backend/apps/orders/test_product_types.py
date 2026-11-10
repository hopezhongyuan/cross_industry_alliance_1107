"""商品类型扩展后的订单履约测试：卡券、免接单实物、门店配送费。"""

from datetime import timedelta
from uuid import uuid4

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AppUser
from apps.aftersales.models import AfterSale
from apps.catalog.models import Category, Product, ProductSku
from apps.fulfillment.models import VerifyCode
from apps.merchants.models import Merchant, MerchantStaff
from apps.orders.models import Order
from apps.payments.models import PaymentOrder


class ProductTypeFlowTests(TestCase):
    def setUp(self):
        self.consumer = AppUser.objects.create_user(phone="13900000110", password="pass12345")
        self.staff = AppUser.objects.create_user(phone="13900000111", password="pass12345")
        self.client = APIClient()
        self.client.force_authenticate(self.consumer)
        self.merchant_client = APIClient()
        self.merchant_client.force_authenticate(self.staff)

        self.category = Category.objects.create(name="扩展类目", commission_rate="0.0500")
        self.merchant = Merchant.objects.create(
            merchant_no="EXT001",
            name="扩展商户",
            category=self.category,
            status=Merchant.Status.ACTIVE,
            industry=Merchant.Industry.ACCOMMODATION,
            delivery_fee=500,
        )
        MerchantStaff.objects.create(merchant=self.merchant, user=self.staff, role=MerchantStaff.Role.OWNER)

        self.physical = Product.objects.create(
            merchant=self.merchant,
            category=self.category,
            type=Product.Type.PHYSICAL,
            title="实物",
            price=1000,
            status=Product.Status.ON_SALE,
            delivery_types=["EXPRESS", "STORE_DELIVERY", "PICKUP"],
        )
        self.physical_sku = ProductSku.objects.create(product=self.physical, sku_code="EXT-P", price=1000, stock=20)

        self.coupon = Product.objects.create(
            merchant=self.merchant,
            category=self.category,
            type=Product.Type.COUPON,
            title="洗车券",
            price=2000,
            status=Product.Status.ON_SALE,
            delivery_types=["VERIFY"],
            verify_count=3,
            valid_type=Product.ValidType.DAYS,
            valid_days=7,
        )
        self.coupon_sku = ProductSku.objects.create(product=self.coupon, sku_code="EXT-C", price=2000, stock=20)

    def _create_order(self, order_type, product, sku, quantity=1):
        payload = {
            "merchant_id": self.merchant.id,
            "order_type": order_type,
            "items": [{"product_id": product.id, "sku_id": sku.id, "quantity": quantity}],
            "contact": {"name": "李四", "phone": "13800138001", "address_detail": "测试地址"},
        }
        response = self.client.post("/api/v1/orders/", payload, format="json", HTTP_IDEMPOTENCY_KEY=uuid4().hex)
        self.assertEqual(response.status_code, 201, response.data)
        return Order.objects.get(pk=response.data["data"]["id"])

    def _pay(self, order):
        response = self.client.post(
            f"/api/v1/orders/{order.id}/pay/", {}, format="json", HTTP_IDEMPOTENCY_KEY=uuid4().hex
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

    # ---------- 卡券 ----------
    def test_coupon_paid_generates_n_codes_and_skips_accept(self):
        order = self._create_order("COUPON", self.coupon, self.coupon_sku)
        self._pay(order)
        self.assertEqual(order.status, Order.Status.PENDING_FULFILL)
        self.assertEqual(order.fulfillment_status, Order.FulfillmentStatus.VERIFY_READY)
        codes = VerifyCode.objects.filter(order=order)
        self.assertEqual(codes.count(), 3)
        self.assertTrue(all(code.status == VerifyCode.Status.ACTIVE for code in codes))

    def test_coupon_days_validity(self):
        order = self._create_order("COUPON", self.coupon, self.coupon_sku)
        self._pay(order)
        code = VerifyCode.objects.filter(order=order).first()
        expected = order.paid_at + timedelta(days=7)
        self.assertLess(abs((code.valid_to - expected).total_seconds()), 60)

    def test_coupon_verify_completes_on_last_code(self):
        order = self._create_order("COUPON", self.coupon, self.coupon_sku)
        self._pay(order)
        codes = list(VerifyCode.objects.filter(order=order).order_by("id"))

        first = self.merchant_client.post("/api/v1/merchant/verify/", {"code": codes[0].code}, format="json")
        self.assertEqual(first.status_code, 200, first.data)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING_FULFILL)

        second = self.merchant_client.post("/api/v1/merchant/verify/", {"code": codes[1].code}, format="json")
        self.assertEqual(second.status_code, 200, second.data)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING_FULFILL)

        third = self.merchant_client.post("/api/v1/merchant/verify/", {"code": codes[2].code}, format="json")
        self.assertEqual(third.status_code, 200, third.data)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.COMPLETED)

    def test_coupon_order_allows_after_sale_before_verify(self):
        order = self._create_order("COUPON", self.coupon, self.coupon_sku)
        self._pay(order)
        response = self.client.post(
            "/api/v1/after-sales/",
            {
                "order_id": order.id,
                "type": "REFUND_ONLY",
                "reason_code": "OTHER",
                "request_amount": order.paid_amount,
                "description": "不想要了",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.AFTER_SALE)
        self.assertTrue(AfterSale.objects.filter(order=order).exists())

    # ---------- 实物接单可配置 ----------
    def test_physical_without_acceptance_goes_direct(self):
        self.physical.acceptance_required = False
        self.physical.save(update_fields=["acceptance_required"])
        order = self._create_order("EXPRESS", self.physical, self.physical_sku)
        self._pay(order)
        self.assertEqual(order.status, Order.Status.PENDING_FULFILL)
        self.assertEqual(order.fulfillment_status, Order.FulfillmentStatus.NOT_STARTED)

    def test_physical_with_acceptance_waits_for_merchant(self):
        order = self._create_order("EXPRESS", self.physical, self.physical_sku)
        self._pay(order)
        self.assertEqual(order.status, Order.Status.PENDING_ACCEPT)

    # ---------- Review 修复回归 ----------
    def test_coupon_verify_blocked_while_after_sale(self):
        order = self._create_order("COUPON", self.coupon, self.coupon_sku)
        self._pay(order)
        self.client.post(
            "/api/v1/after-sales/",
            {
                "order_id": order.id,
                "type": "REFUND_ONLY",
                "reason_code": "OTHER",
                "request_amount": order.paid_amount,
                "description": "退款",
            },
            format="json",
        )
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.AFTER_SALE)
        code = VerifyCode.objects.filter(order=order).first()
        response = self.merchant_client.post("/api/v1/merchant/verify/", {"code": code.code}, format="json")
        self.assertEqual(response.status_code, 409, response.data)
        code.refresh_from_db()
        self.assertEqual(code.status, VerifyCode.Status.ACTIVE)

    def test_coupon_partial_refund_rejected_before_verify(self):
        order = self._create_order("COUPON", self.coupon, self.coupon_sku)
        self._pay(order)
        response = self.client.post(
            "/api/v1/after-sales/",
            {
                "order_id": order.id,
                "type": "REFUND_ONLY",
                "reason_code": "OTHER",
                "request_amount": 100,
                "description": "部分退款",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 409, response.data)
        self.assertEqual(response.data["code"], "REFUND_AMOUNT_EXCEEDED")

    def test_coupon_codes_multiplied_by_quantity(self):
        order = self._create_order("COUPON", self.coupon, self.coupon_sku, quantity=2)
        self._pay(order)
        self.assertEqual(VerifyCode.objects.filter(order=order).count(), 6)

    def test_coupon_range_valid_from_blocks_early_verify(self):
        future = timezone.now() + timedelta(days=3)
        self.coupon.valid_type = Product.ValidType.RANGE
        self.coupon.valid_days = None
        self.coupon.valid_from = future
        self.coupon.valid_to = future + timedelta(days=10)
        self.coupon.save(update_fields=["valid_type", "valid_days", "valid_from", "valid_to"])
        order = self._create_order("COUPON", self.coupon, self.coupon_sku)
        self._pay(order)
        code = VerifyCode.objects.filter(order=order).first()
        response = self.merchant_client.post("/api/v1/merchant/verify/", {"code": code.code}, format="json")
        self.assertEqual(response.status_code, 409, response.data)

    def test_order_type_must_match_product_delivery_types(self):
        self.physical.delivery_types = ["PICKUP"]
        self.physical.save(update_fields=["delivery_types"])
        payload = {
            "merchant_id": self.merchant.id,
            "order_type": "EXPRESS",
            "items": [{"product_id": self.physical.id, "sku_id": self.physical_sku.id, "quantity": 1}],
            "contact": {"name": "李四", "phone": "13800138001", "address_detail": "测试地址"},
        }
        response = self.client.post("/api/v1/orders/", payload, format="json", HTTP_IDEMPOTENCY_KEY=uuid4().hex)
        self.assertEqual(response.status_code, 409, response.data)
        self.assertEqual(response.data["code"], "DELIVERY_TYPE_NOT_SUPPORTED")

    def test_delivery_fee_included_in_merchant_income(self):
        order = self._create_order("STORE_DELIVERY", self.physical, self.physical_sku)
        self.assertEqual(
            order.merchant_income_amount,
            order.product_amount - order.commission_amount + order.delivery_fee,
        )

    # ---------- 配送费 ----------
    def test_store_delivery_charges_merchant_delivery_fee(self):
        order = self._create_order("STORE_DELIVERY", self.physical, self.physical_sku)
        self.assertEqual(order.delivery_fee, 500)
        self.assertEqual(order.payable_amount, order.product_amount + 500)

    def test_pickup_has_no_delivery_fee(self):
        order = self._create_order("PICKUP", self.physical, self.physical_sku)
        self.assertEqual(order.delivery_fee, 0)
