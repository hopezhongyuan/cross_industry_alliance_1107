"""商户中心：自身资料、经营看板接口测试。"""

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AppUser
from apps.catalog.models import Category, Product
from apps.fulfillment.models import VerifyCode
from apps.ledger.models import MerchantAccount
from apps.merchants.models import Merchant, MerchantStaff
from apps.orders.models import Order


class MerchantCenterTests(TestCase):
    def setUp(self):
        self.owner = AppUser.objects.create_user(phone="13900000501", password="pass12345")
        self.clerk = AppUser.objects.create_user(phone="13900000502", password="pass12345")
        self.outsider = AppUser.objects.create_user(phone="13900000503", password="pass12345")

        self.category = Category.objects.create(name="餐饮", commission_rate=Decimal("0.0500"))
        self.merchant = Merchant.objects.create(
            merchant_no="M901",
            name="测试茶餐厅",
            short_name="茶餐",
            logo_url="https://example.com/logo.png",
            contact_phone="13900000501",
            city="上海",
            district="浦东",
            address="陆家嘴",
            business_hours={"weekdays": "10:00-22:00"},
            category=self.category,
            status=Merchant.Status.ACTIVE,
        )
        MerchantStaff.objects.create(merchant=self.merchant, user=self.owner, role=MerchantStaff.Role.OWNER)
        MerchantStaff.objects.create(merchant=self.merchant, user=self.clerk, role=MerchantStaff.Role.CLERK)

        self.account = MerchantAccount.objects.create(
            merchant_id=self.merchant.id, available_balance=88800, pending_balance=10000
        )

        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        self.clerk_client = APIClient()
        self.clerk_client.force_authenticate(self.clerk)
        self.outsider_client = APIClient()
        self.outsider_client.force_authenticate(self.outsider)

    def test_profile_returns_own_fields(self):
        response = self.client.get("/api/v1/merchant/profile/")
        self.assertEqual(response.status_code, 200, response.data)
        data = response.data["data"]
        self.assertEqual(data["id"], self.merchant.id)
        self.assertEqual(data["name"], "测试茶餐厅")
        self.assertEqual(data["short_name"], "茶餐")
        self.assertEqual(data["logo_url"], "https://example.com/logo.png")
        self.assertEqual(data["status"], "ACTIVE")
        self.assertEqual(data["status_label"], "营业中")
        self.assertEqual(data["contact_phone"], "13900000501")
        self.assertNotIn("commission_rate", data)

    def test_profile_requires_merchant_staff(self):
        response = self.outsider_client.get("/api/v1/merchant/profile/")
        self.assertEqual(response.status_code, 403)

    def test_dashboard_today_metrics(self):
        now = timezone.now()
        # 今日订单（已支付）
        Order.objects.create(
            order_no="T" + uuid4().hex[:8],
            user=self.owner,
            merchant=self.merchant,
            order_type=Order.Type.PICKUP,
            status=Order.Status.COMPLETED,
            payable_amount=5000,
            paid_amount=5000,
            paid_at=now,
            created_at=now,
        )
        # 今日待接单
        Order.objects.create(
            order_no="T" + uuid4().hex[:8],
            user=self.owner,
            merchant=self.merchant,
            order_type=Order.Type.PICKUP,
            status=Order.Status.PENDING_ACCEPT,
            payable_amount=2000,
            created_at=now,
        )
        # 昨日订单（不计入今日）
        Order.objects.create(
            order_no="T" + uuid4().hex[:8],
            user=self.owner,
            merchant=self.merchant,
            order_type=Order.Type.PICKUP,
            status=Order.Status.COMPLETED,
            payable_amount=3000,
            paid_amount=3000,
            paid_at=now - timedelta(days=1),
            created_at=now - timedelta(days=1),
        )
        # 待审核商品
        Product.objects.create(
            merchant=self.merchant,
            category=self.category,
            title="待审商品",
            status=Product.Status.PENDING_AUDIT,
            price=1000,
        )
        # 今日核销
        order = Order.objects.create(
            order_no="T" + uuid4().hex[:8],
            user=self.owner,
            merchant=self.merchant,
            order_type=Order.Type.PICKUP,
            status=Order.Status.COMPLETED,
            created_at=now,
        )
        VerifyCode.objects.create(
            order=order,
            merchant=self.merchant,
            code="VC" + uuid4().hex[:6],
            status=VerifyCode.Status.USED,
            used_at=now,
        )

        response = self.client.get("/api/v1/merchant/dashboard/")
        self.assertEqual(response.status_code, 200, response.data)
        data = response.data["data"]
        # 今日订单 = 4（已完成5000、待接单、核销单、verify order）
        self.assertEqual(data["today_orders"], 4)
        # 今日销售额 = 今日已支付金额合计 = 5000
        self.assertEqual(data["today_sales_amount"], 5000)
        # 待处理 = 待接单 + 待履约 = 1
        self.assertEqual(data["pending_orders"], 1)
        # 待审核商品 = 1
        self.assertEqual(data["pending_products"], 1)
        # 可提现余额
        self.assertEqual(data["available_balance"], 88800)
        # 今日核销 = 1
        self.assertEqual(data["today_verified_count"], 1)
        # 今日退款 = 0
        self.assertEqual(data["today_refund_count"], 0)
        # 售后待审 = 0
        self.assertEqual(data["pending_after_sales"], 0)

    def test_dashboard_requires_merchant_staff(self):
        response = self.outsider_client.get("/api/v1/merchant/dashboard/")
        self.assertEqual(response.status_code, 403)
