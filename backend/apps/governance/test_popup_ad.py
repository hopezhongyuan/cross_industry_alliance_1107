"""弹窗广告测试：创建、上下架、当前生效、展示计数。"""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AppUser
from apps.governance.models import PopupAd


class PopupAdTests(TestCase):
    def setUp(self):
        self.admin = AppUser.objects.create_user(phone="13900000050", password="pass12345", is_staff=True)
        self.consumer = AppUser.objects.create_user(phone="13900000051", password="pass12345")
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(self.admin)
        self.public_client = APIClient()
        self.now = timezone.now()

    def test_create_and_list(self):
        resp = self.admin_client.post(
            "/api/v1/admin/popup-ads/",
            {
                "title": "双11弹窗",
                "image_url": "https://example.com/popup.png",
                "link_url": "/pages/activity/index",
                "frequency": "ONCE_PER_DAY",
                "priority": 10,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["data"]["status"], "DRAFT")

        resp = self.admin_client.get("/api/v1/admin/popup-ads/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data["data"]), 1)

    def test_enable_and_current(self):
        popup = PopupAd.objects.create(
            title="活动弹窗",
            image_url="https://example.com/p.png",
            link_url="/pages/a",
            frequency=PopupAd.Frequency.ONCE_PER_DAY,
            status=PopupAd.Status.DRAFT,
            priority=5,
        )
        resp = self.admin_client.post(f"/api/v1/admin/popup-ads/{popup.id}/enable/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["data"]["status"], "ENABLED")

        resp = self.public_client.get("/api/v1/popup-ads/current/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["data"]["id"], popup.id)
        self.assertEqual(resp.data["data"]["frequency"], "ONCE_PER_DAY")

    def test_disable_returns_none(self):
        popup = PopupAd.objects.create(
            title="活动弹窗",
            image_url="https://example.com/p.png",
            status=PopupAd.Status.ENABLED,
            priority=1,
        )
        self.admin_client.post(f"/api/v1/admin/popup-ads/{popup.id}/disable/")
        resp = self.public_client.get("/api/v1/popup-ads/current/")
        self.assertIsNone(resp.data["data"])

    def test_time_window_filtering(self):
        # 已过期
        PopupAd.objects.create(
            title="过期",
            image_url="https://example.com/p.png",
            status=PopupAd.Status.ENABLED,
            end_at=self.now - timedelta(days=1),
        )
        resp = self.public_client.get("/api/v1/popup-ads/current/")
        self.assertIsNone(resp.data["data"])

        # 未开始
        PopupAd.objects.create(
            title="未开始",
            image_url="https://example.com/p.png",
            status=PopupAd.Status.ENABLED,
            start_at=self.now + timedelta(days=1),
        )
        resp = self.public_client.get("/api/v1/popup-ads/current/")
        self.assertIsNone(resp.data["data"])

    def test_max_impressions(self):
        PopupAd.objects.create(
            title="限量弹窗",
            image_url="https://example.com/p.png",
            status=PopupAd.Status.ENABLED,
            max_impressions=1,
            impression_count=1,
            priority=1,
        )
        resp = self.public_client.get("/api/v1/popup-ads/current/")
        self.assertIsNone(resp.data["data"])

    def test_priority_picks_highest(self):
        PopupAd.objects.create(
            title="低优先级",
            image_url="https://example.com/low.png",
            status=PopupAd.Status.ENABLED,
            priority=1,
        )
        high = PopupAd.objects.create(
            title="高优先级",
            image_url="https://example.com/high.png",
            status=PopupAd.Status.ENABLED,
            priority=99,
        )
        resp = self.public_client.get("/api/v1/popup-ads/current/")
        self.assertEqual(resp.data["data"]["id"], high.id)

    def test_impression_increment(self):
        popup = PopupAd.objects.create(
            title="计数弹窗",
            image_url="https://example.com/p.png",
            status=PopupAd.Status.ENABLED,
            priority=1,
        )
        resp = self.public_client.post(f"/api/v1/popup-ads/{popup.id}/impression/")
        self.assertEqual(resp.status_code, 200)
        popup.refresh_from_db()
        self.assertEqual(popup.impression_count, 1)
