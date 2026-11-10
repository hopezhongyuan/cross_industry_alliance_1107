"""商户行业字段：后台可见与筛选，消费者端不暴露。"""

from decimal import Decimal
from uuid import uuid4

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import AppUser
from apps.catalog.models import Category
from apps.ledger.models import MerchantAccount

from .models import Merchant, MerchantStaff


class MerchantIndustryTests(TestCase):
    def setUp(self):
        self.admin = AppUser.objects.create_user(phone="13900000201", password="pass12345", is_staff=True)
        self.consumer = AppUser.objects.create_user(phone="13900000202", password="pass12345")
        self.category = Category.objects.create(name="行业类目", commission_rate=Decimal("0.0500"))

        self.restaurant = Merchant.objects.create(
            merchant_no="IND001",
            name="小馆子",
            category=self.category,
            status=Merchant.Status.ACTIVE,
            city="杭州",
            district="西湖区",
            industry=Merchant.Industry.RESTAURANT,
        )
        self.hotel = Merchant.objects.create(
            merchant_no="IND002",
            name="山间民宿",
            category=self.category,
            status=Merchant.Status.ACTIVE,
            city="杭州",
            district="桐庐",
            industry=Merchant.Industry.ACCOMMODATION,
            delivery_fee=800,
        )
        MerchantAccount.objects.create(merchant=self.restaurant, available_balance=0)

        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.consumer_client = APIClient()
        self.consumer_client.force_authenticate(self.consumer)

    def test_admin_list_includes_industry(self):
        response = self.client.get("/api/v1/admin/merchants/")
        self.assertEqual(response.status_code, 200, response.data)
        row = next(item for item in response.data["data"]["items"] if item["id"] == self.restaurant.id)
        self.assertEqual(row["industry"], "RESTAURANT")
        self.assertEqual(row["industry_label"], "餐饮")
        self.assertEqual(row["delivery_fee"], 0)

    def test_admin_list_filters_by_industry(self):
        response = self.client.get("/api/v1/admin/merchants/?industry=RESTAURANT")
        self.assertEqual(response.status_code, 200, response.data)
        ids = [item["id"] for item in response.data["data"]["items"]]
        self.assertEqual(ids, [self.restaurant.id])

    def test_admin_list_rejects_invalid_industry(self):
        response = self.client.get("/api/v1/admin/merchants/?industry=NOPE")
        self.assertEqual(response.status_code, 422)

    def test_admin_can_update_industry_and_delivery_fee(self):
        response = self.client.patch(
            f"/api/v1/admin/merchants/{self.restaurant.id}/profile/",
            {"industry": "FITNESS", "delivery_fee": 300},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.restaurant.refresh_from_db()
        self.assertEqual(self.restaurant.industry, Merchant.Industry.FITNESS)
        self.assertEqual(self.restaurant.delivery_fee, 300)

    def test_consumer_store_detail_hides_industry(self):
        response = self.consumer_client.get(f"/api/v1/stores/{self.restaurant.id}/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertNotIn("industry", response.data["data"])

    def test_create_merchant_accepts_industry(self):
        owner = AppUser.objects.create_user(phone="13900000203", password="pass12345")
        response = self.client.post(
            "/api/v1/admin/merchants/",
            {
                "name": "新健身馆",
                "category_id": self.category.id,
                "industry": "FITNESS",
                "contact_phone": "13800000203",
                "city": "杭州",
                "district": "滨江",
                "address": "江南大道 1 号",
                "owner_phone": owner.phone,
                "delivery_fee": 200,
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY=uuid4().hex,
        )
        self.assertEqual(response.status_code, 201, response.data)
        merchant = Merchant.objects.get(name="新健身馆")
        self.assertEqual(merchant.industry, Merchant.Industry.FITNESS)
        self.assertEqual(merchant.delivery_fee, 200)
        self.assertTrue(MerchantStaff.objects.filter(merchant=merchant, user=owner).exists())
