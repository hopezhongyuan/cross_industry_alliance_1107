"""平台配置：密钥不回显、公开接口不泄密、Logo 素材校验。"""

import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import AppUser

from .models import MediaAsset, PlatformConfig


class PlatformConfigTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.temp_dir)
        self.override.enable()
        self.admin = AppUser.objects.create_user(phone="13900000301", password="pass12345", is_staff=True)
        self.consumer = AppUser.objects.create_user(phone="13900000302", password="pass12345")
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.consumer_client = APIClient()
        self.consumer_client.force_authenticate(self.consumer)

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _payload(self, **overrides):
        payload = {
            "platform_name": "异业联盟测试平台",
            "contact_phone": "400-800-0000",
            "privacy_policy": "隐私协议正文",
            "user_agreement": "用户注册协议正文",
            "agreement_version": "2026.11",
            "miniapp_app_id": "wx-test-app",
            "miniapp_app_secret": "secret-value",
            "miniapp_original_id": "gh_test",
            "amap_web_key": "web-key",
            "amap_js_key": "js-key",
            "amap_js_security_code": "security-code",
            "amap_enabled": False,
        }
        payload.update(overrides)
        return payload

    def test_requires_platform_admin(self):
        response = self.consumer_client.get("/api/v1/admin/platform-config/")
        self.assertEqual(response.status_code, 403)

    def test_admin_read_write_hides_secrets(self):
        read = self.client.get("/api/v1/admin/platform-config/")
        self.assertEqual(read.status_code, 200, read.data)
        self.assertFalse(read.data["data"]["miniapp_app_secret_configured"])

        updated = self.client.put("/api/v1/admin/platform-config/", self._payload(), format="json")
        self.assertEqual(updated.status_code, 200, updated.data)
        data = updated.data["data"]
        self.assertEqual(data["platform_name"], "异业联盟测试平台")
        self.assertTrue(data["miniapp_app_secret_configured"])
        self.assertTrue(data["amap_web_key_configured"])
        self.assertNotIn("miniapp_app_secret", data)
        self.assertNotIn("amap_web_key", data)
        self.assertNotIn("amap_js_security_code", data)

        config = PlatformConfig.objects.get(singleton_key="default")
        self.assertEqual(config.miniapp_app_secret, "secret-value")
        self.assertEqual(config.amap_web_key, "web-key")

    def test_blank_secret_keeps_existing(self):
        self.client.put("/api/v1/admin/platform-config/", self._payload(), format="json")
        self.client.put(
            "/api/v1/admin/platform-config/",
            self._payload(miniapp_app_secret="", amap_web_key="", amap_js_security_code=""),
            format="json",
        )
        config = PlatformConfig.objects.get(singleton_key="default")
        self.assertEqual(config.miniapp_app_secret, "secret-value")
        self.assertEqual(config.amap_web_key, "web-key")

    def test_public_endpoint_never_returns_secrets(self):
        self.client.put("/api/v1/admin/platform-config/", self._payload(), format="json")
        response = self.consumer_client.get("/api/v1/platform/config/")
        self.assertEqual(response.status_code, 200, response.data)
        data = response.data["data"]
        self.assertEqual(data["platform_name"], "异业联盟测试平台")
        self.assertEqual(data["privacy_policy"], "隐私协议正文")
        for key in ("miniapp_app_secret", "amap_web_key", "miniapp_app_id"):
            self.assertNotIn(key, data)

    def test_logo_must_come_from_media_library(self):
        rejected = self.client.put(
            "/api/v1/admin/platform-config/",
            self._payload(logo_url="https://example.com/logo.png"),
            format="json",
        )
        self.assertEqual(rejected.status_code, 422)

        asset = MediaAsset.objects.create(
            kind=MediaAsset.Kind.IMAGE,
            file=SimpleUploadedFile("logo.png", b"fake-image", content_type="image/png"),
            name="平台 Logo",
        )
        accepted = self.client.put(
            "/api/v1/admin/platform-config/", self._payload(logo_url=asset.file.url), format="json"
        )
        self.assertEqual(accepted.status_code, 200, accepted.data)
        self.assertEqual(accepted.data["data"]["logo_url"], asset.file.url)
