"""审核中心：任务列表、审核决定与商户/资质状态联动。"""

from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import AppUser
from apps.catalog.models import Category
from apps.governance.models import AuditTask, OperationLog
from apps.merchants.models import Merchant, MerchantQualification


class AuditCenterTests(TestCase):
    def setUp(self):
        self.admin = AppUser.objects.create_user(phone="13900000201", password="pass12345", is_staff=True)
        self.consumer = AppUser.objects.create_user(phone="13900000202", password="pass12345")
        self.category = Category.objects.create(name="花艺", commission_rate=Decimal("0.0500"))
        self.merchant = Merchant.objects.create(
            merchant_no="M701", name="拾光花店", category=self.category, status=Merchant.Status.PENDING
        )
        self.qualification = MerchantQualification.objects.create(
            merchant=self.merchant,
            type=MerchantQualification.Type.BUSINESS_LICENSE,
            file_url="https://example.com/license.pdf",
        )
        self.task = AuditTask.objects.create(
            biz_type=AuditTask.BizType.MERCHANT, biz_id=self.merchant.id, status=AuditTask.Status.PENDING
        )

        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.consumer_client = APIClient()
        self.consumer_client.force_authenticate(self.consumer)

    def test_list_requires_platform_admin(self):
        response = self.consumer_client.get("/api/v1/admin/audits/")
        self.assertEqual(response.status_code, 403)

    def test_list_returns_biz_name_and_summary(self):
        response = self.client.get("/api/v1/admin/audits/?biz_type=MERCHANT&status=PENDING")
        self.assertEqual(response.status_code, 200, response.data)
        data = response.data["data"]
        self.assertEqual(data["items"][0]["biz_name"], "拾光花店")
        self.assertEqual(data["summary"]["MERCHANT"], 1)

    def test_approve_merchant_activates_and_approves_qualification(self):
        response = self.client.post(
            f"/api/v1/admin/audits/{self.task.id}/decision/", {"decision": "APPROVE"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.merchant.refresh_from_db()
        self.qualification.refresh_from_db()
        self.assertEqual(self.merchant.status, Merchant.Status.ACTIVE)
        self.assertIsNotNone(self.merchant.opened_at)
        self.assertEqual(self.qualification.audit_status, MerchantQualification.AuditStatus.APPROVED)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, AuditTask.Status.APPROVED)
        self.assertTrue(OperationLog.objects.filter(action="AUDIT_DECIDE", biz_id=self.merchant.id).exists())

    def test_reject_requires_reason(self):
        response = self.client.post(
            f"/api/v1/admin/audits/{self.task.id}/decision/", {"decision": "REJECT", "reason": ""}, format="json"
        )
        self.assertEqual(response.status_code, 422)

    def test_reject_merchant_updates_status_and_reason(self):
        response = self.client.post(
            f"/api/v1/admin/audits/{self.task.id}/decision/",
            {"decision": "REJECT", "reason": "执照信息不一致"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.merchant.refresh_from_db()
        self.qualification.refresh_from_db()
        self.assertEqual(self.merchant.status, Merchant.Status.REJECTED)
        self.assertEqual(self.qualification.audit_status, MerchantQualification.AuditStatus.REJECTED)
        self.assertEqual(self.qualification.reject_reason, "执照信息不一致")

    def test_decision_twice_conflicts(self):
        url = f"/api/v1/admin/audits/{self.task.id}/decision/"
        self.client.post(url, {"decision": "APPROVE"}, format="json")
        again = self.client.post(url, {"decision": "APPROVE"}, format="json")
        self.assertEqual(again.status_code, 409)
        self.assertEqual(again.data["code"], "AUDIT_STATE_CONFLICT")

    def test_qualification_task_updates_qualification_only(self):
        task = AuditTask.objects.create(
            biz_type=AuditTask.BizType.QUALIFICATION,
            biz_id=self.qualification.id,
            status=AuditTask.Status.PENDING,
        )
        response = self.client.post(f"/api/v1/admin/audits/{task.id}/decision/", {"decision": "APPROVE"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.qualification.refresh_from_db()
        self.assertEqual(self.qualification.audit_status, MerchantQualification.AuditStatus.APPROVED)

    def test_missing_task_returns_404(self):
        response = self.client.post("/api/v1/admin/audits/9999/decision/", {"decision": "APPROVE"}, format="json")
        self.assertEqual(response.status_code, 404)

    def test_batch_decision_reports_partial_result(self):
        handled = AuditTask.objects.create(
            biz_type=AuditTask.BizType.QUALIFICATION,
            biz_id=self.qualification.id,
            status=AuditTask.Status.APPROVED,
        )
        response = self.client.post(
            "/api/v1/admin/audits/batch-decision/",
            {"ids": [self.task.id, handled.id], "decision": "APPROVE"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        data = response.data["data"]
        self.assertEqual(data["succeeded"], 1)
        self.assertEqual(data["failed"], 1)
        results = {item["id"]: item for item in data["items"]}
        self.assertTrue(results[self.task.id]["ok"])
        self.assertFalse(results[handled.id]["ok"])
        self.assertEqual(results[handled.id]["error_code"], "AUDIT_STATE_CONFLICT")
        self.merchant.refresh_from_db()
        self.assertEqual(self.merchant.status, Merchant.Status.ACTIVE)

    def test_batch_reject_requires_reason(self):
        response = self.client.post(
            "/api/v1/admin/audits/batch-decision/",
            {"ids": [self.task.id], "decision": "REJECT", "reason": ""},
            format="json",
        )
        self.assertEqual(response.status_code, 422)

    def test_batch_decision_requires_platform_admin(self):
        response = self.consumer_client.post(
            "/api/v1/admin/audits/batch-decision/",
            {"ids": [self.task.id], "decision": "APPROVE"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
