"""佣金解析测试：商户覆盖优先，类目默认兜底。"""

from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.catalog.models import Category

from .models import Merchant
from .services import resolve_commission_rate


class CommissionResolutionTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="餐饮", commission_rate=Decimal("0.0500"))
        self.merchant = Merchant.objects.create(merchant_no="M200", name="测试餐厅", category=self.category)

    def test_uses_category_default_when_no_override(self):
        self.assertIsNone(self.merchant.commission_rate)
        self.assertEqual(resolve_commission_rate(self.merchant), Decimal("0.0500"))

    def test_merchant_override_wins(self):
        self.merchant.commission_rate = Decimal("0.0300")
        self.merchant.save(update_fields=["commission_rate"])
        self.assertEqual(resolve_commission_rate(self.merchant), Decimal("0.0300"))

    def test_zero_override_is_respected(self):
        self.merchant.commission_rate = Decimal("0")
        self.merchant.save(update_fields=["commission_rate"])
        self.assertEqual(resolve_commission_rate(self.merchant), Decimal("0"))

    def test_no_category_falls_back_to_zero(self):
        merchant = Merchant.objects.create(merchant_no="M201", name="无类目商户")
        self.assertEqual(resolve_commission_rate(merchant), Decimal("0"))


class StoreBrowseTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.category = Category.objects.create(name="门店类目")
        self.merchant = Merchant.objects.create(
            merchant_no="M420",
            name="门店浏览",
            category=self.category,
            status=Merchant.Status.ACTIVE,
            city="杭州",
            district="西湖区",
            address="文三路 90 号",
            lng=Decimal("120.130000"),
            lat=Decimal("30.280000"),
        )

    def test_nearby_returns_distance_and_filters(self):
        response = self.client.get("/api/v1/stores/nearby/?lat=30.2741&lng=120.1551")
        self.assertEqual(response.status_code, 200, response.data)
        items = response.data["data"]["items"]
        self.assertEqual(items[0]["name"], "门店浏览")
        self.assertIsInstance(items[0]["distance_meters"], int)
        self.assertEqual(response.data["data"]["page"]["total"], 1)

    def test_nearby_requires_coordinates(self):
        response = self.client.get("/api/v1/stores/nearby/")
        self.assertEqual(response.status_code, 422)

    def test_store_detail(self):
        response = self.client.get(f"/api/v1/stores/{self.merchant.id}/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["data"]["category_name"], "门店类目")
