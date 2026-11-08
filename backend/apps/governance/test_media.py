"""素材库：文件夹、上传、引用保护。"""

import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import AppUser
from apps.catalog.models import Category, Product
from apps.governance.models import MediaAsset, MediaFolder
from apps.merchants.models import Merchant


class MediaLibraryTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.temp_dir)
        self.override.enable()
        self.admin = AppUser.objects.create_user(phone="13900000801", password="pass12345", is_staff=True)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_folder_crud_and_duplicate(self):
        created = self.client.post("/api/v1/admin/media-folders/", {"name": "商品图"}, format="json")
        self.assertEqual(created.status_code, 201, created.data)
        duplicate = self.client.post("/api/v1/admin/media-folders/", {"name": "商品图"}, format="json")
        self.assertEqual(duplicate.status_code, 422)
        folders = self.client.get("/api/v1/admin/media-folders/").data["data"]
        self.assertEqual(folders[0]["name"], "商品图")

    def test_upload_and_reference_guard(self):
        folder = MediaFolder.objects.create(name="素材组")
        upload = self.client.post(
            "/api/v1/admin/media-assets/",
            {
                "file": SimpleUploadedFile("cover.jpg", b"fake-image", content_type="image/jpeg"),
                "folder_id": folder.id,
            },
            format="multipart",
        )
        self.assertEqual(upload.status_code, 201, upload.data)
        asset = MediaAsset.objects.get(pk=upload.data["data"]["id"])
        self.assertEqual(asset.kind, MediaAsset.Kind.IMAGE)
        self.assertTrue(asset.file.url.startswith("/media/"))

        category = Category.objects.create(name="素材类目")
        merchant = Merchant.objects.create(merchant_no="M1201", name="素材商户", category=category)
        Product.objects.create(
            merchant=merchant,
            category=category,
            type=Product.Type.PHYSICAL,
            title="引用素材的商品",
            cover_url=asset.file.url,
            status=Product.Status.ON_SALE,
        )
        blocked = self.client.delete(f"/api/v1/admin/media-assets/{asset.id}/")
        self.assertEqual(blocked.status_code, 409)

    def test_upload_rejects_unknown_extension(self):
        response = self.client.post(
            "/api/v1/admin/media-assets/",
            {"file": SimpleUploadedFile("payload.exe", b"x", content_type="application/octet-stream")},
            format="multipart",
        )
        self.assertEqual(response.status_code, 422)
