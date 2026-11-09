"""商户端售后列表接口测试。"""

from decimal import Decimal
from uuid import uuid4

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import AppUser
from apps.aftersales.models import AfterSale
from apps.catalog.models import Category
from apps.merchants.models import Merchant, MerchantStaff
from apps.orders.models import Order


class MerchantAfterSaleListTests(TestCase):
    def setUp(self):
        self.owner = AppUser.objects.create_user(phone="13900000601", password="pass12345")
        self.consumer = AppUser.objects.create_user(phone="13900000602", password="pass12345")
        self.outsider = AppUser.objects.create_user(phone="13900000603", password="pass12345")

        self.category = Category.objects.create(name="餐饮", commission_rate=Decimal("0.0500"))
        self.merchant = Merchant.objects.create(
            merchant_no="M911", name="售后商户", category=self.category, status=Merchant.Status.ACTIVE
        )
        MerchantStaff.objects.create(merchant=self.merchant, user=self.owner, role=MerchantStaff.Role.OWNER)

        self.order = Order.objects.create(
            order_no="O" + uuid4().hex[:8],
            user=self.consumer,
            merchant=self.merchant,
            order_type=Order.Type.PICKUP,
            status=Order.Status.AFTER_SALE,
            payable_amount=3000,
        )

        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        self.outsider_client = APIClient()
        self.outsider_client.force_authenticate(self.outsider)

    def test_list_returns_only_own_after_sales(self):
        AfterSale.objects.create(
            after_sale_no="AS" + uuid4().hex[:8],
            order=self.order,
            user=self.consumer,
            merchant=self.merchant,
            type=AfterSale.Type.REFUND_ONLY,
            reason_code="QUALITY",
            request_amount=3000,
            status=AfterSale.Status.APPLIED,
            merchant_decision=AfterSale.MerchantDecision.PENDING,
        )
        agreed = AfterSale.objects.create(
            after_sale_no="AS" + uuid4().hex[:8],
            order=self.order,
            user=self.consumer,
            merchant=self.merchant,
            type=AfterSale.Type.REFUND_ONLY,
            reason_code="OTHER",
            request_amount=1500,
            approved_amount=1500,
            status=AfterSale.Status.MERCHANT_AGREED,
            merchant_decision=AfterSale.MerchantDecision.AGREED,
        )

        response = self.client.get("/api/v1/merchant/after-sales/")
        self.assertEqual(response.status_code, 200, response.data)
        items = response.data["data"]["items"]
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["id"], agreed.id)  # 按 created_at 倒序
        self.assertEqual(items[0]["order_no"], self.order.order_no)
        self.assertEqual(items[0]["type_label"], "仅退款")
        self.assertEqual(items[1]["merchant_decision"], "PENDING")

    def test_filter_by_status(self):
        AfterSale.objects.create(
            after_sale_no="AS" + uuid4().hex[:8],
            order=self.order,
            user=self.consumer,
            merchant=self.merchant,
            type=AfterSale.Type.REFUND_ONLY,
            reason_code="Q",
            request_amount=1000,
            status=AfterSale.Status.APPLIED,
            merchant_decision=AfterSale.MerchantDecision.PENDING,
        )
        AfterSale.objects.create(
            after_sale_no="AS" + uuid4().hex[:8],
            order=self.order,
            user=self.consumer,
            merchant=self.merchant,
            type=AfterSale.Type.REFUND_ONLY,
            reason_code="Q",
            request_amount=1000,
            status=AfterSale.Status.COMPLETED,
            merchant_decision=AfterSale.MerchantDecision.AGREED,
        )

        response = self.client.get("/api/v1/merchant/after-sales/?status=APPLIED")
        self.assertEqual(len(response.data["data"]["items"]), 1)

    def test_filter_by_merchant_decision(self):
        AfterSale.objects.create(
            after_sale_no="AS" + uuid4().hex[:8],
            order=self.order,
            user=self.consumer,
            merchant=self.merchant,
            type=AfterSale.Type.REFUND_ONLY,
            reason_code="Q",
            request_amount=1000,
            merchant_decision=AfterSale.MerchantDecision.PENDING,
        )

        response = self.client.get("/api/v1/merchant/after-sales/?merchant_decision=PENDING")
        self.assertEqual(len(response.data["data"]["items"]), 1)

    def test_invalid_status_returns_422(self):
        response = self.client.get("/api/v1/merchant/after-sales/?status=INVALID")
        self.assertEqual(response.status_code, 422)

    def test_list_requires_merchant_staff(self):
        response = self.outsider_client.get("/api/v1/merchant/after-sales/")
        self.assertEqual(response.status_code, 403)
