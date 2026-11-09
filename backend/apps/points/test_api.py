"""积分接口测试（消费者端 + 平台后台）。"""

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import AppUser
from apps.points.services import award_for_register, get_or_create_account


class ConsumerPointsApiTests(TestCase):
    def setUp(self):
        self.user = AppUser.objects.create_user(phone="13900000801", password="pass12345")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_account(self):
        award_for_register(self.user.id)
        response = self.client.get("/api/v1/points/account/")
        self.assertEqual(response.status_code, 200)
        data = response.data["data"]
        self.assertEqual(data["balance"], 50)
        self.assertEqual(data["total_earned"], 50)

    def test_transactions(self):
        award_for_register(self.user.id)
        response = self.client.get("/api/v1/points/transactions/")
        self.assertEqual(response.status_code, 200)
        items = response.data["data"]["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["biz_type"], "REGISTER")

    def test_transactions_filter(self):
        award_for_register(self.user.id)
        response = self.client.get("/api/v1/points/transactions/?biz_type=SIGNIN")
        self.assertEqual(len(response.data["data"]["items"]), 0)

    def test_transactions_invalid_type(self):
        response = self.client.get("/api/v1/points/transactions/?biz_type=BAD")
        self.assertEqual(response.status_code, 422)

    def test_signin(self):
        response = self.client.post("/api/v1/points/signin/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["delta"], 5)
        # 重复签到幂等
        response2 = self.client.post("/api/v1/points/signin/")
        self.assertEqual(response2.data["data"]["delta"], 5)
        account = get_or_create_account(self.user.id)
        self.assertEqual(account.balance, 5)

    def test_share(self):
        response = self.client.post("/api/v1/points/share/", {"target_type": "PRODUCT", "target_id": 1}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["data"]["awarded"])
        self.assertEqual(response.data["data"]["delta"], 2)

    def test_share_invalid_target(self):
        response = self.client.post("/api/v1/points/share/", {"target_type": "BAD", "target_id": 1}, format="json")
        self.assertEqual(response.status_code, 422)

    def test_rules_public(self):
        client = APIClient()
        response = client.get("/api/v1/points/rules/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("consumption_rate", response.data["data"])

    def test_account_requires_auth(self):
        client = APIClient()
        response = client.get("/api/v1/points/account/")
        self.assertEqual(response.status_code, 401)


class AdminPointsApiTests(TestCase):
    def setUp(self):
        self.admin = AppUser.objects.create_superuser(phone="13900000901", password="pass12345")
        self.user = AppUser.objects.create_user(phone="13900000902", password="pass12345")
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_config_get(self):
        response = self.client.get("/api/v1/admin/points/config/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["consumption_rate"], 100)

    def test_config_update(self):
        response = self.client.put(
            "/api/v1/admin/points/config/",
            {"consumption_rate": 200, "signin_points": 10},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["consumption_rate"], 200)
        self.assertEqual(response.data["data"]["signin_points"], 10)

    def test_users_list(self):
        award_for_register(self.user.id)
        response = self.client.get("/api/v1/admin/points/users/")
        self.assertEqual(response.status_code, 200)
        items = response.data["data"]["items"]
        phones = [i["user_phone"] for i in items]
        self.assertIn(self.user.phone, phones)

    def test_users_search(self):
        award_for_register(self.user.id)
        response = self.client.get(f"/api/v1/admin/points/users/?keyword={self.user.phone}")
        self.assertEqual(len(response.data["data"]["items"]), 1)

    def test_user_transactions(self):
        award_for_register(self.user.id)
        response = self.client.get(f"/api/v1/admin/points/users/{self.user.id}/transactions/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["data"]["items"]), 1)

    def test_adjust(self):
        award_for_register(self.user.id)  # 50
        response = self.client.post(
            "/api/v1/admin/points/adjust/",
            {"user_id": self.user.id, "delta": -20, "reason": "后台扣减测试"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["data"]["balance_after"], 30)

    def test_adjust_no_reason(self):
        response = self.client.post(
            "/api/v1/admin/points/adjust/",
            {"user_id": self.user.id, "delta": 10, "reason": ""},
            format="json",
        )
        self.assertEqual(response.status_code, 422)

    def test_admin_requires_permission(self):
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.get("/api/v1/admin/points/config/")
        self.assertEqual(response.status_code, 403)
