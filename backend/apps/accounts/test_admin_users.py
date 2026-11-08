"""平台后台用户列表：脱敏、筛选与权限。"""

from django.test import TestCase
from rest_framework.test import APIClient

from apps.merchants.models import Merchant, MerchantStaff

from .models import AppUser


class AdminUserListTests(TestCase):
    def setUp(self):
        self.admin = AppUser.objects.create_user(
            phone="13900000201", password="pass12345", nickname="平台管理员", is_staff=True
        )
        self.consumer = AppUser.objects.create_user(phone="13900000202", password="pass12345", nickname="普通用户")
        self.owner = AppUser.objects.create_user(phone="13900000203", password="pass12345", nickname="店主")
        self.disabled = AppUser.objects.create_user(
            phone="13900000204", password="pass12345", nickname="停用用户", status=AppUser.Status.DISABLED
        )
        merchant = Merchant.objects.create(merchant_no="M1301", name="用户测试商户")
        MerchantStaff.objects.create(
            merchant=merchant, user=self.owner, role=MerchantStaff.Role.OWNER, status=MerchantStaff.Status.ACTIVE
        )
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.consumer_client = APIClient()
        self.consumer_client.force_authenticate(self.consumer)

    def test_requires_platform_admin(self):
        response = self.consumer_client.get("/api/v1/admin/users/")
        self.assertEqual(response.status_code, 403)

    def test_list_masks_phone_and_labels_user_type(self):
        response = self.client.get("/api/v1/admin/users/")
        self.assertEqual(response.status_code, 200, response.data)
        items = {item["nickname"]: item for item in response.data["data"]["items"]}
        self.assertEqual(items["普通用户"]["phone_masked"], "139****0202")
        self.assertEqual(items["普通用户"]["user_type"], "CONSUMER")
        self.assertEqual(items["店主"]["user_type"], "MERCHANT_STAFF")
        self.assertEqual(items["店主"]["merchant_names"], ["用户测试商户"])
        self.assertEqual(items["平台管理员"]["user_type"], "PLATFORM_ADMIN")
        self.assertNotIn("phone", items["普通用户"])

    def test_filters_by_status_type_and_keyword(self):
        disabled = self.client.get("/api/v1/admin/users/?status=DISABLED")
        self.assertEqual(disabled.data["data"]["items"][0]["nickname"], "停用用户")

        merchants = self.client.get("/api/v1/admin/users/?user_type=MERCHANT_STAFF")
        self.assertEqual([item["nickname"] for item in merchants.data["data"]["items"]], ["店主"])

        consumers = self.client.get("/api/v1/admin/users/?user_type=CONSUMER")
        self.assertEqual({item["nickname"] for item in consumers.data["data"]["items"]}, {"普通用户", "停用用户"})

        searched = self.client.get("/api/v1/admin/users/?q=0202")
        self.assertEqual(searched.data["data"]["items"][0]["nickname"], "普通用户")

    def test_rejects_invalid_filters(self):
        response = self.client.get("/api/v1/admin/users/?status=UNKNOWN")
        self.assertEqual(response.status_code, 422)
        response = self.client.get("/api/v1/admin/users/?user_type=UNKNOWN")
        self.assertEqual(response.status_code, 422)
