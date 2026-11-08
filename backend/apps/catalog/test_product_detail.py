"""商品详情：服务时段、退款展示与门店信息。"""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.merchants.models import Merchant

from .models import Category, Product, ProductSku, ServiceSlot


class ProductDetailTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.category = Category.objects.create(name="详情类目")
        self.merchant = Merchant.objects.create(
            merchant_no="M410",
            name="详情门店",
            category=self.category,
            status=Merchant.Status.ACTIVE,
            address="文三路 90 号",
            contact_phone="0571-88888888",
        )
        self.service = Product.objects.create(
            merchant=self.merchant,
            category=self.category,
            type=Product.Type.SERVICE,
            title="手冲体验",
            price=8800,
            status=Product.Status.ON_SALE,
            appointment_required=True,
            verify_days=30,
        )
        ProductSku.objects.create(product=self.service, sku_code="SVC-1", price=8800, stock=10)
        self.slot = ServiceSlot.objects.create(
            product=self.service,
            slot_date=timezone.localdate() + timedelta(days=1),
            start_time="16:30",
            end_time="17:00",
            capacity=2,
        )
        self.physical = Product.objects.create(
            merchant=self.merchant,
            category=self.category,
            type=Product.Type.PHYSICAL,
            title="实物套餐",
            price=1000,
            status=Product.Status.ON_SALE,
        )

    def test_service_detail_returns_slots_and_rules(self):
        response = self.client.get(f"/api/v1/products/{self.service.id}/")
        self.assertEqual(response.status_code, 200, response.data)
        data = response.data
        self.assertEqual(data["merchant_address"], "文三路 90 号")
        self.assertEqual(data["refund_policy"], "未核销、有效期内可退")
        self.assertEqual(len(data["slots"]), 1)
        self.assertEqual(data["slots"][0]["remaining"], 2)

    def test_physical_detail_has_no_slots(self):
        response = self.client.get(f"/api/v1/products/{self.physical.id}/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["slots"], [])
