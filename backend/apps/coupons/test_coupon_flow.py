"""优惠券核心流程测试：领券、平台券/商户券下单记账、退券、过期。"""

from datetime import timedelta
from uuid import uuid4

from django.db import models
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AppUser
from apps.catalog.models import Category, Product, ProductSku
from apps.coupons.models import Coupon, UserCoupon
from apps.ledger.constants import AccountType, Direction
from apps.ledger.models import LedgerEntry
from apps.merchants.models import Merchant
from apps.orders.models import Order


class CouponFlowTests(TestCase):
    def setUp(self):
        self.consumer = AppUser.objects.create_user(phone="13900000030", password="pass12345")
        self.client = APIClient()
        self.client.force_authenticate(self.consumer)

        self.category = Category.objects.create(name="优惠券类目", commission_rate="0.1000")
        self.merchant = Merchant.objects.create(
            merchant_no="CP001", name="券商户", category=self.category, status=Merchant.Status.ACTIVE
        )
        self.product = Product.objects.create(
            merchant=self.merchant,
            category=self.category,
            type=Product.Type.PHYSICAL,
            title="券商品",
            price=10000,  # 100元
            status=Product.Status.ON_SALE,
        )
        self.sku = ProductSku.objects.create(product=self.product, sku_code="CP-SKU", price=10000, stock=10)

        self.now = timezone.now()

    def _create_platform_coupon(self, face_value=1000, min_amount=5000):
        return Coupon.objects.create(
            name="平台满减券",
            type=Coupon.Type.PLATFORM,
            face_value=face_value,
            min_amount=min_amount,
            scope_type=Coupon.ScopeType.ALL,
            total_stock=100,
            per_user_limit=1,
            valid_from=self.now - timedelta(days=1),
            valid_to=self.now + timedelta(days=30),
            status=Coupon.Status.ACTIVE,
        )

    def _create_merchant_coupon(self, face_value=2000, min_amount=8000):
        return Coupon.objects.create(
            name="商户满减券",
            type=Coupon.Type.MERCHANT,
            merchant=self.merchant,
            face_value=face_value,
            min_amount=min_amount,
            scope_type=Coupon.ScopeType.ALL,
            total_stock=100,
            per_user_limit=1,
            valid_from=self.now - timedelta(days=1),
            valid_to=self.now + timedelta(days=30),
            status=Coupon.Status.ACTIVE,
        )

    def _order_payload(self, user_coupon_id=None):
        payload = {
            "merchant_id": self.merchant.id,
            "order_type": "EXPRESS",
            "items": [{"product_id": self.product.id, "sku_id": self.sku.id, "quantity": 1}],
            "contact": {"name": "张三", "phone": "13800138000", "address_detail": "测试地址"},
        }
        if user_coupon_id is not None:
            payload["user_coupon_id"] = user_coupon_id
        return payload

    def test_claim_and_use_platform_coupon(self):
        coupon = self._create_platform_coupon(face_value=1000, min_amount=5000)
        uc = UserCoupon.objects.create(
            coupon=coupon, user=self.consumer, status=UserCoupon.Status.UNUSED, expire_at=coupon.valid_to
        )
        coupon.issued_count = 1
        coupon.save()

        response = self.client.post(
            "/api/v1/orders/",
            self._order_payload(user_coupon_id=uc.id),
            format="json",
            HTTP_IDEMPOTENCY_KEY=uuid4().hex,
        )
        self.assertEqual(response.status_code, 201, response.data)
        order = Order.objects.get(pk=response.data["data"]["id"])
        self.assertEqual(order.discount_amount, 1000)
        self.assertEqual(order.platform_subsidy_amount, 1000)
        self.assertEqual(order.merchant_discount_amount, 0)
        self.assertEqual(order.payable_amount, 9000)
        # 平台券佣金按原价算
        self.assertEqual(order.commission_amount, 1000)  # 10000 * 0.1
        self.assertEqual(order.merchant_income_amount, 9000)  # 10000 - 1000

        # 支付回调：检查平台营销费用记账
        self.client.post(
            "/api/v1/orders/{}/pay/".format(order.id),
            {"channel": "WECHAT_MINI"},
            format="json",
            HTTP_IDEMPOTENCY_KEY=uuid4().hex,
        )
        self.client.post(
            "/api/v1/callback/wechat/pay/",
            {
                "payment_no": order.payments.first().payment_no,
                "transaction_id": f"txn-{uuid4().hex[:12]}",
                "amount": 9000,
                "trade_state": "SUCCESS",
            },
            format="json",
        )
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING_ACCEPT)
        debit = (
            LedgerEntry.objects.filter(
                account_type=AccountType.PLATFORM_MARKETING_EXPENSE, direction=Direction.DEBIT
            ).aggregate(v=models.Sum("amount"))["v"]
            or 0
        )
        self.assertEqual(debit, 1000)

    def test_use_merchant_coupon(self):
        coupon = self._create_merchant_coupon(face_value=2000, min_amount=8000)
        uc = UserCoupon.objects.create(
            coupon=coupon, user=self.consumer, status=UserCoupon.Status.UNUSED, expire_at=coupon.valid_to
        )
        coupon.issued_count = 1
        coupon.save()

        response = self.client.post(
            "/api/v1/orders/",
            self._order_payload(user_coupon_id=uc.id),
            format="json",
            HTTP_IDEMPOTENCY_KEY=uuid4().hex,
        )
        self.assertEqual(response.status_code, 201, response.data)
        order = Order.objects.get(pk=response.data["data"]["id"])
        self.assertEqual(order.discount_amount, 2000)
        self.assertEqual(order.merchant_discount_amount, 2000)
        self.assertEqual(order.platform_subsidy_amount, 0)
        self.assertEqual(order.payable_amount, 8000)
        # 商户券佣金按优惠后算
        self.assertEqual(order.commission_amount, 800)  # 8000 * 0.1
        self.assertEqual(order.merchant_income_amount, 7200)  # 8000 - 800

    def test_cancel_order_releases_coupon(self):
        coupon = self._create_platform_coupon()
        uc = UserCoupon.objects.create(
            coupon=coupon, user=self.consumer, status=UserCoupon.Status.UNUSED, expire_at=coupon.valid_to
        )
        coupon.issued_count = 1
        coupon.save()
        response = self.client.post(
            "/api/v1/orders/",
            self._order_payload(user_coupon_id=uc.id),
            format="json",
            HTTP_IDEMPOTENCY_KEY=uuid4().hex,
        )
        order_id = response.data["data"]["id"]
        self.client.post(f"/api/v1/orders/{order_id}/cancel/", {"reason": "取消"}, format="json")
        uc.refresh_from_db()
        self.assertEqual(uc.status, UserCoupon.Status.UNUSED)

    def test_expire_coupons(self):
        from apps.coupons.services import expire_coupons

        coupon = self._create_platform_coupon()
        uc = UserCoupon.objects.create(
            coupon=coupon,
            user=self.consumer,
            status=UserCoupon.Status.UNUSED,
            expire_at=self.now - timedelta(minutes=1),
        )
        count = expire_coupons()
        self.assertEqual(count, 1)
        uc.refresh_from_db()
        self.assertEqual(uc.status, UserCoupon.Status.EXPIRED)
