"""卡券/多类型商品序列化器校验测试。"""

from django.test import TestCase

from apps.catalog.models import Category, MerchantProductCategory
from apps.catalog.serializers import AdminTemplateInputSerializer, MerchantProductInputSerializer
from apps.merchants.models import Merchant


class MerchantProductCouponValidationTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="卡券类目")
        self.merchant = Merchant.objects.create(
            merchant_no="CV001", name="卡券商户", category=self.category, status=Merchant.Status.ACTIVE
        )

    def _payload(self, **overrides):
        payload = {
            "category_id": self.category.id,
            "type": "COUPON",
            "title": "洗车券",
            "price_amount": 1000,
            "delivery_types": ["VERIFY"],
            "valid_type": "DAYS",
            "valid_days": 7,
            "verify_count": 3,
            "skus": [{"sku_code": "CV-1", "price_amount": 1000, "stock": 10}],
        }
        payload.update(overrides)
        return payload

    def test_coupon_with_non_verify_delivery_rejected(self):
        serializer = MerchantProductInputSerializer(data=self._payload(delivery_types=["EXPRESS"]))
        self.assertFalse(serializer.is_valid())
        self.assertIn("履约方式与商品类型不匹配", str(serializer.errors))

    def test_coupon_days_requires_valid_days(self):
        serializer = MerchantProductInputSerializer(data=self._payload(valid_days=None))
        self.assertFalse(serializer.is_valid())
        self.assertIn("卡券有效天数必填且大于 0", str(serializer.errors))

    def test_coupon_range_requires_valid_order(self):
        from datetime import timedelta

        from django.utils import timezone

        now = timezone.now()
        serializer = MerchantProductInputSerializer(
            data=self._payload(
                valid_type="RANGE",
                valid_days=None,
                valid_from=(now + timedelta(days=2)).isoformat(),
                valid_to=(now + timedelta(days=1)).isoformat(),
            )
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("卡券失效时间必须晚于生效时间", str(serializer.errors))

    def test_coupon_permanent_clears_days(self):
        serializer = MerchantProductInputSerializer(data=self._payload(valid_type="PERMANENT"))
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIsNone(serializer.validated_data.get("valid_days"))

    def test_physical_accepts_store_delivery(self):
        serializer = MerchantProductInputSerializer(
            data=self._payload(type="PHYSICAL", delivery_types=["STORE_DELIVERY"], valid_days=None)
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_merchant_category_not_required(self):
        serializer = MerchantProductInputSerializer(data=self._payload())
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIsInstance(MerchantProductCategory.objects.count(), int)


class AdminTemplateTypeTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="模板类目")

    def _payload(self, **overrides):
        payload = {
            "title": "模板券",
            "type": "COUPON",
            "category_id": self.category.id,
            "price_amount": 1000,
            "delivery_types": ["VERIFY"],
            "valid_type": "DAYS",
            "valid_days": 30,
            "verify_count": 2,
            "skus": [{"sku_code": "T-1", "price_amount": 1000, "stock": 5}],
        }
        payload.update(overrides)
        return payload

    def test_coupon_template_valid(self):
        serializer = AdminTemplateInputSerializer(data=self._payload())
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["verify_count"], 2)

    def test_template_physical_store_delivery_valid(self):
        serializer = AdminTemplateInputSerializer(
            data=self._payload(type="PHYSICAL", delivery_types=["STORE_DELIVERY"], valid_days=None)
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_template_coupon_rejects_non_verify(self):
        serializer = AdminTemplateInputSerializer(data=self._payload(delivery_types=["EXPRESS"]))
        self.assertFalse(serializer.is_valid())
        self.assertIn("履约方式与商品类型不匹配", str(serializer.errors))
