"""店铺装修：底部导航、微页面与发布快照。"""

import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import AppUser

from .models import MediaAsset


class StorefrontTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.temp_dir)
        self.override.enable()
        self.admin = AppUser.objects.create_user(phone="13900000601", password="pass12345", is_staff=True)
        self.consumer = AppUser.objects.create_user(phone="13900000602", password="pass12345")
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.consumer_client = APIClient()
        self.consumer_client.force_authenticate(self.consumer)
        self.icon = MediaAsset.objects.create(
            kind=MediaAsset.Kind.IMAGE,
            file=SimpleUploadedFile("icon.png", b"fake-image", content_type="image/png"),
            name="导航图标",
        )

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _nav_item(self, title="首页"):
        return {
            "title": title,
            "icon_selected": self.icon.file.url,
            "icon_unselected": self.icon.file.url,
            "link_type": "FUNCTION",
            "link_value": "HOME",
            "status": "ENABLED",
        }

    def test_nav_replace_and_public_read(self):
        response = self.client.put(
            "/api/v1/admin/storefront/nav/",
            {"items": [self._nav_item("首页"), self._nav_item("购物车")], "link_type": "FUNCTION"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([item["title"] for item in response.data["data"]], ["首页", "购物车"])
        self.assertEqual(response.data["data"][0]["sort"], 0)

        public = self.consumer_client.get("/api/v1/storefront/nav/")
        self.assertEqual(public.status_code, 200)
        self.assertEqual(len(public.data["data"]), 2)

    def test_nav_limits_links_and_media(self):
        too_many = self.client.put(
            "/api/v1/admin/storefront/nav/",
            {"items": [self._nav_item(f"导航{i}") for i in range(6)]},
            format="json",
        )
        self.assertEqual(too_many.status_code, 422)

        external_icon = self.client.put(
            "/api/v1/admin/storefront/nav/",
            {"items": [{**self._nav_item(), "icon_selected": "https://example.com/icon.png"}]},
            format="json",
        )
        self.assertEqual(external_icon.status_code, 422)

        invalid_link = self.client.put(
            "/api/v1/admin/storefront/nav/",
            {"items": [{**self._nav_item(), "link_value": "UNKNOWN"}]},
            format="json",
        )
        self.assertEqual(invalid_link.status_code, 422)

        micro_missing = self.client.put(
            "/api/v1/admin/storefront/nav/",
            {"items": [{**self._nav_item(), "link_type": "MICRO_PAGE", "link_value": "not-exists"}]},
            format="json",
        )
        self.assertEqual(micro_missing.status_code, 422)

        forbidden = self.consumer_client.put(
            "/api/v1/admin/storefront/nav/", {"items": [self._nav_item()]}, format="json"
        )
        self.assertEqual(forbidden.status_code, 403)

    def test_page_publish_and_public_snapshot(self):
        created = self.client.post(
            "/api/v1/admin/storefront/pages/",
            {
                "slug": "home",
                "title": "首页",
                "share_title": "异业联盟",
                "draft_components": [
                    {
                        "id": "c1",
                        "type": "AD",
                        "config": {
                            "image": self.icon.file.url,
                            "height": 180,
                            "link": {"type": "FUNCTION", "value": "HOME"},
                        },
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)
        page_id = created.data["data"]["id"]

        unpublished = self.consumer_client.get("/api/v1/storefront/pages/home/")
        self.assertEqual(unpublished.status_code, 404)

        published = self.client.post(f"/api/v1/admin/storefront/pages/{page_id}/publish/", {}, format="json")
        self.assertEqual(published.status_code, 200, published.data)
        public = self.consumer_client.get("/api/v1/storefront/pages/home/")
        self.assertEqual(public.status_code, 200)
        self.assertEqual(len(public.data["data"]["components"]), 1)

        draft = self.client.put(
            f"/api/v1/admin/storefront/pages/{page_id}/",
            {
                "slug": "home",
                "title": "首页 v2",
                "draft_components": [
                    {
                        "id": "c1",
                        "type": "DIVIDER",
                        "config": {"height": 8, "style": "BLANK", "background": "#F6F1E7"},
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(draft.status_code, 200, draft.data)
        still_old = self.consumer_client.get("/api/v1/storefront/pages/home/")
        self.assertEqual(still_old.data["data"]["components"][0]["type"], "AD")

    def test_page_validation_and_delete_reference(self):
        duplicate = self.client.post(
            "/api/v1/admin/storefront/pages/",
            {"slug": "home", "title": "首页", "draft_components": []},
            format="json",
        )
        self.assertEqual(duplicate.status_code, 201)

        duplicated_slug = self.client.post(
            "/api/v1/admin/storefront/pages/",
            {"slug": "home", "title": "重复", "draft_components": []},
            format="json",
        )
        self.assertEqual(duplicated_slug.status_code, 422)

        bad_component = self.client.put(
            f"/api/v1/admin/storefront/pages/{duplicate.data['data']['id']}/",
            {"slug": "home", "title": "首页", "draft_components": [{"type": "UNKNOWN", "config": {}}]},
            format="json",
        )
        self.assertEqual(bad_component.status_code, 422)

        self.client.put(
            "/api/v1/admin/storefront/nav/",
            {"items": [{**self._nav_item(), "link_type": "MICRO_PAGE", "link_value": "home"}]},
            format="json",
        )
        blocked = self.client.delete(f"/api/v1/admin/storefront/pages/{duplicate.data['data']['id']}/")
        self.assertEqual(blocked.status_code, 409)
