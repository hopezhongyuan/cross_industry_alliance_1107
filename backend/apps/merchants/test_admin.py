"""平台商户管理：列表、详情、状态迁移、创建与审计日志。"""

from decimal import Decimal
from uuid import uuid4

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import AppUser
from apps.catalog.models import Category
from apps.governance.models import OperationLog
from apps.ledger.models import MerchantAccount

from .models import Merchant, MerchantStaff


class AdminMerchantTests(TestCase):
    def setUp(self):
        self.admin = AppUser.objects.create_user(phone="13900000101", password="pass12345", is_staff=True)
        self.consumer = AppUser.objects.create_user(phone="13900000102", password="pass12345")
        self.staff_user = AppUser.objects.create_user(phone="13900000103", password="pass12345")

        self.category = Category.objects.create(name="咖啡", commission_rate=Decimal("0.0500"))
        self.active = Merchant.objects.create(
            merchant_no="M601",
            name="山野咖啡",
            category=self.category,
            status=Merchant.Status.ACTIVE,
            city="杭州",
            district="西湖区",
            contact_phone="13800000001",
            bank_info={"bank": "招商银行", "card_no": "6225888888888888"},
        )
        MerchantAccount.objects.create(merchant=self.active, available_balance=1000)
        MerchantStaff.objects.create(merchant=self.active, user=self.staff_user, role=MerchantStaff.Role.OWNER)
        self.pending = Merchant.objects.create(
            merchant_no="M602", name="拾光花店", category=self.category, status=Merchant.Status.PENDING
        )

        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.consumer_client = APIClient()
        self.consumer_client.force_authenticate(self.consumer)

    def test_list_requires_platform_admin(self):
        response = self.consumer_client.get("/api/v1/admin/merchants/")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["code"], "PERMISSION_DENIED")

    def test_list_filters_and_summary(self):
        response = self.client.get("/api/v1/admin/merchants/?status=ACTIVE")
        self.assertEqual(response.status_code, 200, response.data)
        data = response.data["data"]
        self.assertEqual(data["page"]["total"], 1)
        self.assertEqual(data["items"][0]["name"], "山野咖啡")
        self.assertEqual(data["items"][0]["commission_rate"], 0.05)
        self.assertEqual(data["summary"]["total"], 2)
        self.assertEqual(data["summary"]["pending"], 1)

        searched = self.client.get("/api/v1/admin/merchants/?q=花店")
        self.assertEqual(searched.data["data"]["items"][0]["merchant_no"], "M602")

        invalid = self.client.get("/api/v1/admin/merchants/?status=UNKNOWN")
        self.assertEqual(invalid.status_code, 422)

    def test_detail_masks_bank_and_exposes_relations(self):
        response = self.client.get(f"/api/v1/admin/merchants/{self.active.id}/")
        self.assertEqual(response.status_code, 200, response.data)
        data = response.data["data"]
        self.assertEqual(data["bank_last4"], "8888")
        self.assertEqual(data["balances"]["available_amount"], 1000)
        self.assertEqual(len(data["qualifications"]), 0)
        self.assertEqual(data["staff"][0]["user_id"], self.staff_user.id)

    def test_status_flow_and_idempotency(self):
        url = f"/api/v1/admin/merchants/{self.active.id}/status/"
        paused = self.client.post(url, {"status": "RESTING", "reason": "设备检修"}, format="json")
        self.assertEqual(paused.status_code, 200, paused.data)
        self.assertTrue(paused.data["data"]["changed"])

        same = self.client.post(url, {"status": "RESTING", "reason": "重复提交"}, format="json")
        self.assertEqual(same.status_code, 200, same.data)
        self.assertFalse(same.data["data"]["changed"])

        resumed = self.client.post(url, {"status": "ACTIVE", "reason": "恢复营业"}, format="json")
        self.assertEqual(resumed.status_code, 200, resumed.data)

        banned = self.client.post(url, {"status": "BANNED", "reason": "违规经营"}, format="json")
        self.assertEqual(banned.status_code, 200, banned.data)
        unbanned = self.client.post(url, {"status": "ACTIVE", "reason": "复核通过"}, format="json")
        self.assertEqual(unbanned.status_code, 200, unbanned.data)

        logs = OperationLog.objects.filter(biz_type="MERCHANT", biz_id=self.active.id)
        self.assertEqual(logs.count(), 4)
        self.assertEqual(logs.first().after_json["status"], "ACTIVE")

    def test_illegal_transition_rejected(self):
        url = f"/api/v1/admin/merchants/{self.active.id}/status/"
        self.client.post(url, {"status": "RESTING", "reason": "停业"}, format="json")
        response = self.client.post(url, {"status": "BANNED", "reason": "跳步封禁"}, format="json")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "MERCHANT_STATE_CONFLICT")

        pending = self.client.post(
            f"/api/v1/admin/merchants/{self.pending.id}/status/",
            {"status": "ACTIVE", "reason": "直接上线"},
            format="json",
        )
        self.assertEqual(pending.status_code, 409)

    def test_reason_required(self):
        response = self.client.post(
            f"/api/v1/admin/merchants/{self.active.id}/status/",
            {"status": "RESTING", "reason": ""},
            format="json",
        )
        self.assertEqual(response.status_code, 422)


class AdminMerchantLocationTests(TestCase):
    def setUp(self):
        self.admin = AppUser.objects.create_user(phone="13900000401", password="pass12345", is_staff=True)
        self.consumer = AppUser.objects.create_user(phone="13900000402", password="pass12345")
        self.merchant = Merchant.objects.create(
            merchant_no="M1401", name="定位测试商户", status=Merchant.Status.ACTIVE, city="杭州"
        )
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.consumer_client = APIClient()
        self.consumer_client.force_authenticate(self.consumer)

    def test_update_location(self):
        response = self.client.put(
            f"/api/v1/admin/merchants/{self.merchant.id}/location/",
            {
                "lng": "120.155100",
                "lat": "30.274100",
                "province": "浙江",
                "city": "杭州",
                "district": "西湖区",
                "address": "西湖文化广场",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.merchant.refresh_from_db()
        self.assertEqual(str(self.merchant.lng), "120.155100")
        self.assertEqual(str(self.merchant.lat), "30.274100")
        self.assertEqual(self.merchant.address, "西湖文化广场")
        self.assertTrue(
            OperationLog.objects.filter(action="MERCHANT_LOCATION_UPDATE", biz_id=self.merchant.id).exists()
        )

    def test_location_validation_and_permission(self):
        invalid = self.client.put(
            f"/api/v1/admin/merchants/{self.merchant.id}/location/",
            {"lng": "120.1", "lat": "91"},
            format="json",
        )
        self.assertEqual(invalid.status_code, 422)
        forbidden = self.consumer_client.put(
            f"/api/v1/admin/merchants/{self.merchant.id}/location/",
            {"lng": "120.1", "lat": "30.1"},
            format="json",
        )
        self.assertEqual(forbidden.status_code, 403)


class AdminMerchantCreateTests(TestCase):
    def setUp(self):
        self.admin = AppUser.objects.create_user(phone="13900000301", password="pass12345", is_staff=True)
        self.consumer = AppUser.objects.create_user(phone="13900000302", password="pass12345")
        self.owner = AppUser.objects.create_user(phone="13900000303", password="pass12345", nickname="新店主")
        self.category = Category.objects.create(name="新商户类目", commission_rate=Decimal("0.0500"))
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.consumer_client = APIClient()
        self.consumer_client.force_authenticate(self.consumer)

    def _payload(self, **overrides):
        payload = {
            "name": "新创建商户",
            "short_name": "新店",
            "category_id": self.category.id,
            "contact_phone": "13800000002",
            "province": "浙江",
            "city": "杭州",
            "district": "西湖区",
            "address": "文三路 100 号",
            "commission_rate": "0.0400",
            "settlement_cycle_days": 7,
            "bank_info": {"bank": "招商银行", "card_no": "6225888888886621"},
            "owner_phone": self.owner.phone,
        }
        payload.update(overrides)
        return payload

    def test_create_merchant_activates_and_binds_owner(self):
        response = self.client.post(
            "/api/v1/admin/merchants/",
            self._payload(),
            format="json",
            HTTP_IDEMPOTENCY_KEY=uuid4().hex,
        )
        self.assertEqual(response.status_code, 201, response.data)
        data = response.data["data"]
        merchant = Merchant.objects.get(pk=data["id"])
        self.assertEqual(merchant.status, Merchant.Status.ACTIVE)
        self.assertTrue(merchant.merchant_no.startswith("M"))
        self.assertIsNotNone(merchant.opened_at)
        self.assertEqual(merchant.commission_rate, Decimal("0.0400"))
        self.assertEqual(merchant.bank_info["card_no"], "6225888888886621")
        self.assertTrue(MerchantAccount.objects.filter(merchant=merchant).exists())
        staff = MerchantStaff.objects.get(merchant=merchant)
        self.assertEqual(staff.user, self.owner)
        self.assertEqual(staff.role, MerchantStaff.Role.OWNER)
        self.assertEqual(merchant.qualifications.count(), 0)
        self.assertTrue(OperationLog.objects.filter(action="MERCHANT_CREATE", biz_id=merchant.id).exists())
        self.assertEqual(data["bank_last4"], "6621")
        self.assertEqual(data["staff"][0]["nickname"], "新店主")

    def test_create_requires_platform_admin(self):
        response = self.consumer_client.post(
            "/api/v1/admin/merchants/",
            self._payload(),
            format="json",
            HTTP_IDEMPOTENCY_KEY=uuid4().hex,
        )
        self.assertEqual(response.status_code, 403)

    def test_create_requires_idempotency_key(self):
        response = self.client.post("/api/v1/admin/merchants/", self._payload(), format="json")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(Merchant.objects.count(), 0)

    def test_create_requires_registered_owner(self):
        response = self.client.post(
            "/api/v1/admin/merchants/",
            self._payload(owner_phone="13900000999"),
            format="json",
            HTTP_IDEMPOTENCY_KEY=uuid4().hex,
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(Merchant.objects.count(), 0)

    def test_create_is_idempotent(self):
        key = uuid4().hex
        first = self.client.post("/api/v1/admin/merchants/", self._payload(), format="json", HTTP_IDEMPOTENCY_KEY=key)
        second = self.client.post("/api/v1/admin/merchants/", self._payload(), format="json", HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(first.data["data"]["id"], second.data["data"]["id"])
        self.assertEqual(Merchant.objects.count(), 1)

    def test_create_validates_commission_rate(self):
        response = self.client.post(
            "/api/v1/admin/merchants/",
            self._payload(commission_rate="1.5000"),
            format="json",
            HTTP_IDEMPOTENCY_KEY=uuid4().hex,
        )
        self.assertEqual(response.status_code, 422)

    def test_create_validates_required_fields(self):
        response = self.client.post(
            "/api/v1/admin/merchants/",
            self._payload(name=""),
            format="json",
            HTTP_IDEMPOTENCY_KEY=uuid4().hex,
        )
        self.assertEqual(response.status_code, 422)

    def test_created_merchant_appears_in_active_list(self):
        self.client.post(
            "/api/v1/admin/merchants/",
            self._payload(),
            format="json",
            HTTP_IDEMPOTENCY_KEY=uuid4().hex,
        )
        response = self.client.get("/api/v1/admin/merchants/?status=ACTIVE&q=新创建商户")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["data"]["items"][0]["name"], "新创建商户")
