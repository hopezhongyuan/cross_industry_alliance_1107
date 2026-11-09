"""优惠券核心流程测试：领券、平台券/商户券下单记账、退券、过期、跨商户分摊。"""

from datetime import timedelta
from uuid import uuid4

from django.db import models
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AppUser
from apps.catalog.models import Category, Product, ProductSku
from apps.coupons.models import Coupon, CouponAllocation, UserCoupon
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


class CrossMerchantCouponTests(TestCase):
    """跨商户平台券分摊测试。"""

    def setUp(self):
        self.consumer = AppUser.objects.create_user(phone="13900000040", password="pass12345")
        self.client = APIClient()
        self.client.force_authenticate(self.consumer)

        self.category = Category.objects.create(name="分摊类目", commission_rate="0.1000")
        self.merchant_a = Merchant.objects.create(
            merchant_no="AL001", name="商户A", category=self.category, status=Merchant.Status.ACTIVE
        )
        self.merchant_b = Merchant.objects.create(
            merchant_no="BL002", name="商户B", category=self.category, status=Merchant.Status.ACTIVE
        )
        self.product_a = Product.objects.create(
            merchant=self.merchant_a,
            category=self.category,
            type=Product.Type.PHYSICAL,
            title="商品A",
            price=6000,
            status=Product.Status.ON_SALE,
        )
        self.product_b = Product.objects.create(
            merchant=self.merchant_b,
            category=self.category,
            type=Product.Type.PHYSICAL,
            title="商品B",
            price=5000,
            status=Product.Status.ON_SALE,
        )
        self.sku_a = ProductSku.objects.create(product=self.product_a, sku_code="A-SKU", price=6000, stock=10)
        self.sku_b = ProductSku.objects.create(product=self.product_b, sku_code="B-SKU", price=5000, stock=10)

        self.now = timezone.now()
        # 平台券 满100减20，合计 60+50=110 满足门槛
        self.coupon = Coupon.objects.create(
            name="跨商户满减券",
            type=Coupon.Type.PLATFORM,
            face_value=2000,
            min_amount=10000,
            scope_type=Coupon.ScopeType.ALL,
            total_stock=100,
            per_user_limit=1,
            valid_from=self.now - timedelta(days=1),
            valid_to=self.now + timedelta(days=30),
            status=Coupon.Status.ACTIVE,
        )
        self.uc = UserCoupon.objects.create(
            coupon=self.coupon, user=self.consumer, status=UserCoupon.Status.UNUSED, expire_at=self.coupon.valid_to
        )
        self.coupon.issued_count = 1
        self.coupon.save()

    def _batch_payload(self, platform_coupon_id=None):
        payload = {
            "groups": [
                {
                    "merchant_id": self.merchant_a.id,
                    "order_type": "EXPRESS",
                    "items": [{"product_id": self.product_a.id, "sku_id": self.sku_a.id, "quantity": 1}],
                },
                {
                    "merchant_id": self.merchant_b.id,
                    "order_type": "EXPRESS",
                    "items": [{"product_id": self.product_b.id, "sku_id": self.sku_b.id, "quantity": 1}],
                },
            ],
            "contact": {"name": "张三", "phone": "13800138000", "address_detail": "测试地址"},
        }
        if platform_coupon_id is not None:
            payload["platform_coupon_id"] = platform_coupon_id
        return payload

    def test_cross_merchant_platform_coupon_allocation(self):
        """跨商户平台券：优惠按商品金额比例分摊到各商户订单。"""
        response = self.client.post(
            "/api/v1/orders/batch/",
            self._batch_payload(platform_coupon_id=self.uc.id),
            format="json",
            HTTP_IDEMPOTENCY_KEY=uuid4().hex,
        )
        self.assertEqual(response.status_code, 201, response.data)
        data = response.data["data"]
        self.assertEqual(len(data["orders"]), 2)

        orders = {o["merchant_id"]: Order.objects.get(pk=o["id"]) for o in data["orders"]}
        order_a = orders[self.merchant_a.id]
        order_b = orders[self.merchant_b.id]

        # 分摊：A 60/110 * 20 = 10.91 → 1091；B 50/110 * 20 = 9.09 → 909
        self.assertEqual(order_a.discount_amount + order_b.discount_amount, 2000)
        self.assertAlmostEqual(order_a.discount_amount, 1091, delta=1)
        self.assertAlmostEqual(order_b.discount_amount, 909, delta=1)
        self.assertEqual(order_a.platform_subsidy_amount, order_a.discount_amount)
        self.assertEqual(order_b.platform_subsidy_amount, order_b.discount_amount)
        # 平台券佣金按原价算
        self.assertEqual(order_a.commission_amount, 600)  # 6000 * 0.1
        self.assertEqual(order_b.commission_amount, 500)  # 5000 * 0.1
        self.assertEqual(order_a.payable_amount, 6000 - order_a.discount_amount)
        self.assertEqual(order_b.payable_amount, 5000 - order_b.discount_amount)
        # 合单总金额 = 11000 - 2000 = 9000
        self.assertEqual(data["total_amount"], 9000)

        # 券已锁定为 USED，且有两条分摊记录
        self.uc.refresh_from_db()
        self.assertEqual(self.uc.status, UserCoupon.Status.USED)
        allocs = CouponAllocation.objects.filter(user_coupon=self.uc, status=CouponAllocation.Status.ACTIVE)
        self.assertEqual(allocs.count(), 2)
        self.assertEqual(sum(a.allocated_amount for a in allocs), 2000)

    def test_cross_merchant_coupon_payment_accounting(self):
        """跨商户平台券支付后，平台营销费用合计 = 整张券面额。"""
        response = self.client.post(
            "/api/v1/orders/batch/",
            self._batch_payload(platform_coupon_id=self.uc.id),
            format="json",
            HTTP_IDEMPOTENCY_KEY=uuid4().hex,
        )
        group_no = response.data["data"]["group_no"]
        total = response.data["data"]["total_amount"]

        self.client.post(
            f"/api/v1/payment-groups/{group_no}/pay/",
            {"channel": "WECHAT_MINI"},
            format="json",
            HTTP_IDEMPOTENCY_KEY=uuid4().hex,
        )
        self.client.post(
            "/api/v1/callback/wechat/pay/",
            {
                "payment_no": group_no,
                "transaction_id": f"txn-{uuid4().hex[:12]}",
                "amount": total,
                "trade_state": "SUCCESS",
            },
            format="json",
        )
        debit = (
            LedgerEntry.objects.filter(
                account_type=AccountType.PLATFORM_MARKETING_EXPENSE, direction=Direction.DEBIT
            ).aggregate(v=models.Sum("amount"))["v"]
            or 0
        )
        self.assertEqual(debit, 2000)

    def test_cancel_one_order_partially_releases_coupon(self):
        """取消其中一个商户订单：该分摊释放，但券仍为 USED（另一分摊生效）。"""
        response = self.client.post(
            "/api/v1/orders/batch/",
            self._batch_payload(platform_coupon_id=self.uc.id),
            format="json",
            HTTP_IDEMPOTENCY_KEY=uuid4().hex,
        )
        order_a_id = next(o["id"] for o in response.data["data"]["orders"] if o["merchant_id"] == self.merchant_a.id)

        self.client.post(f"/api/v1/orders/{order_a_id}/cancel/", {"reason": "取消"}, format="json")
        self.uc.refresh_from_db()
        # 券仍为 USED，因为商户B的分摊还在
        self.assertEqual(self.uc.status, UserCoupon.Status.USED)
        active = CouponAllocation.objects.filter(user_coupon=self.uc, status=CouponAllocation.Status.ACTIVE)
        self.assertEqual(active.count(), 1)
        self.assertEqual(active.first().merchant_id, self.merchant_b.id)

    def test_cancel_all_orders_returns_coupon(self):
        """取消所有商户订单：所有分摊释放，券退回 UNUSED。"""
        response = self.client.post(
            "/api/v1/orders/batch/",
            self._batch_payload(platform_coupon_id=self.uc.id),
            format="json",
            HTTP_IDEMPOTENCY_KEY=uuid4().hex,
        )
        for o in response.data["data"]["orders"]:
            self.client.post(f"/api/v1/orders/{o['id']}/cancel/", {"reason": "取消"}, format="json")
        self.uc.refresh_from_db()
        self.assertEqual(self.uc.status, UserCoupon.Status.UNUSED)
        active = CouponAllocation.objects.filter(user_coupon=self.uc, status=CouponAllocation.Status.ACTIVE)
        self.assertEqual(active.count(), 0)

    def test_full_refund_releases_coupon(self):
        """全额退款（调 release_user_coupon_by_order）后券退回 UNUSED。"""
        from apps.coupons.services import release_user_coupon_by_order

        response = self.client.post(
            "/api/v1/orders/batch/",
            self._batch_payload(platform_coupon_id=self.uc.id),
            format="json",
            HTTP_IDEMPOTENCY_KEY=uuid4().hex,
        )
        # 模拟每个订单全额退款时释放券分摊
        for o in response.data["data"]["orders"]:
            release_user_coupon_by_order(o["id"])
        self.uc.refresh_from_db()
        self.assertEqual(self.uc.status, UserCoupon.Status.UNUSED)

    def test_threshold_uses_total_amount(self):
        """门槛按合计金额判断：合计不足时不可用。"""
        # 把门槛提高到 20000（合计 11000 不满足）
        self.coupon.min_amount = 20000
        self.coupon.save()
        response = self.client.post(
            "/api/v1/orders/batch/",
            self._batch_payload(platform_coupon_id=self.uc.id),
            format="json",
            HTTP_IDEMPOTENCY_KEY=uuid4().hex,
        )
        self.assertEqual(response.status_code, 409, response.data)
        self.assertIn("门槛", response.data["message"])
        # 券未被锁定
        self.uc.refresh_from_db()
        self.assertEqual(self.uc.status, UserCoupon.Status.UNUSED)
