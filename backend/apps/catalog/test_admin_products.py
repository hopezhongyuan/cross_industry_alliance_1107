"""平台商品管理、违规下架与模板认领。"""

from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import AppUser
from apps.catalog.models import Category, Product, ProductTemplate, TemplateAdoption
from apps.governance.models import OperationLog
from apps.merchants.models import Merchant, MerchantStaff


class AdminProductManageTests(TestCase):
    def setUp(self):
        self.admin = AppUser.objects.create_user(phone="13900000601", password="pass12345", is_staff=True)
        self.owner = AppUser.objects.create_user(phone="13900000602", password="pass12345")
        self.category = Category.objects.create(name="平台类目", commission_rate=Decimal("0.0500"))
        self.child = Category.objects.create(name="平台子类", parent=self.category, level=2)
        self.merchant = Merchant.objects.create(
            merchant_no="M1001", name="商品商户", category=self.category, status=Merchant.Status.ACTIVE
        )
        MerchantStaff.objects.create(merchant=self.merchant, user=self.owner, role=MerchantStaff.Role.OWNER)
        self.product = Product.objects.create(
            merchant=self.merchant,
            category=self.child,
            type=Product.Type.PHYSICAL,
            title="原商品",
            price=1000,
            status=Product.Status.ON_SALE,
        )
        self.product.skus.create(sku_code="A", price=1000, stock=10)
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(self.admin)
        self.merchant_client = APIClient()
        self.merchant_client.force_authenticate(self.owner)

    def _payload(self, **overrides):
        payload = {
            "category_id": self.child.id,
            "type": "PHYSICAL",
            "title": "平台优化后的商品",
            "price_amount": 1200,
            "delivery_types": ["EXPRESS"],
            "skus": [{"sku_code": "A", "price_amount": 1200, "stock": 12}],
        }
        payload.update(overrides)
        return payload

    def test_admin_edit_product_takes_effect_without_reaudit(self):
        response = self.admin_client.put(f"/api/v1/admin/products/{self.product.id}/", self._payload(), format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.product.refresh_from_db()
        self.assertEqual(self.product.title, "平台优化后的商品")
        self.assertEqual(self.product.status, Product.Status.ON_SALE)
        self.assertEqual(self.product.version, 1)
        self.assertEqual(self.product.skus.get(sku_code="A").price, 1200)
        self.assertTrue(OperationLog.objects.filter(action="PRODUCT_ADMIN_UPDATE", biz_id=self.product.id).exists())

    def test_admin_list_products(self):
        response = self.admin_client.get("/api/v1/admin/products/?status=ON_SALE")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["data"]["items"][0]["title"], "原商品")

    def test_force_off_blocks_merchant_relist_and_admin_restore(self):
        off = self.admin_client.post(
            f"/api/v1/admin/products/{self.product.id}/status/",
            {"action": "FORCE_OFF", "reason": "违规宣传"},
            format="json",
        )
        self.assertEqual(off.status_code, 200, off.data)
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, Product.Status.OFF_SALE)
        self.assertEqual(self.product.off_sale_by, "PLATFORM")
        self.assertEqual(self.product.off_sale_reason, "违规宣传")

        blocked = self.merchant_client.post(
            f"/api/v1/merchant/products/{self.product.id}/status/", {"status": "ON_SALE"}, format="json"
        )
        self.assertEqual(blocked.status_code, 409)

        restore = self.admin_client.post(
            f"/api/v1/admin/products/{self.product.id}/status/", {"action": "RESTORE"}, format="json"
        )
        self.assertEqual(restore.status_code, 200, restore.data)
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, Product.Status.ON_SALE)
        self.assertEqual(self.product.off_sale_by, "")

        listed = self.merchant_client.post(
            f"/api/v1/merchant/products/{self.product.id}/status/", {"status": "ON_SALE"}, format="json"
        )
        self.assertEqual(listed.status_code, 409)  # 已在售，不允许重复上架

    def test_merchant_off_sale_records_merchant_source(self):
        response = self.merchant_client.post(
            f"/api/v1/merchant/products/{self.product.id}/status/", {"status": "OFF_SALE"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.product.refresh_from_db()
        self.assertEqual(self.product.off_sale_by, "MERCHANT")
        on = self.merchant_client.post(
            f"/api/v1/merchant/products/{self.product.id}/status/", {"status": "ON_SALE"}, format="json"
        )
        self.assertEqual(on.status_code, 200, on.data)
        self.product.refresh_from_db()
        self.assertEqual(self.product.off_sale_by, "")

    def test_batch_force_off_returns_per_item_result(self):
        draft = Product.objects.create(
            merchant=self.merchant,
            category=self.child,
            type=Product.Type.PHYSICAL,
            title="草稿商品",
            price=500,
            status=Product.Status.DRAFT,
        )
        response = self.admin_client.post(
            "/api/v1/admin/products/batch-status/",
            {"ids": [self.product.id, draft.id], "action": "FORCE_OFF", "reason": "批量违规"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        data = response.data["data"]
        self.assertEqual(data["succeeded"], 1)
        self.assertEqual(data["failed"], 1)
        results = {item["id"]: item for item in data["items"]}
        self.assertTrue(results[self.product.id]["ok"])
        self.assertEqual(results[self.product.id]["status"], Product.Status.OFF_SALE)
        self.assertFalse(results[draft.id]["ok"])
        self.assertEqual(results[draft.id]["error_code"], "PRODUCT_STATE_CONFLICT")

    def test_batch_force_off_requires_reason(self):
        response = self.admin_client.post(
            "/api/v1/admin/products/batch-status/",
            {"ids": [self.product.id], "action": "FORCE_OFF", "reason": ""},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["data"]["failed"], 1)
        self.assertEqual(response.data["data"]["items"][0]["error_code"], "VALIDATION_ERROR")

    def test_batch_status_requires_platform_admin(self):
        response = self.merchant_client.post(
            "/api/v1/admin/products/batch-status/",
            {"ids": [self.product.id], "action": "FORCE_OFF", "reason": "越权"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)


class ProductTemplateTests(TestCase):
    def setUp(self):
        self.admin = AppUser.objects.create_user(phone="13900000701", password="pass12345", is_staff=True)
        self.owner = AppUser.objects.create_user(phone="13900000702", password="pass12345")
        self.other_owner = AppUser.objects.create_user(phone="13900000703", password="pass12345")
        self.category = Category.objects.create(name="模板类目", commission_rate=Decimal("0.0500"))
        self.child = Category.objects.create(name="模板子类", parent=self.category, level=2)
        self.merchant = Merchant.objects.create(
            merchant_no="M1101", name="模板商户", category=self.category, status=Merchant.Status.ACTIVE
        )
        self.other_merchant = Merchant.objects.create(
            merchant_no="M1102", name="模板商户二", category=self.category, status=Merchant.Status.ACTIVE
        )
        MerchantStaff.objects.create(merchant=self.merchant, user=self.owner, role=MerchantStaff.Role.OWNER)
        MerchantStaff.objects.create(merchant=self.other_merchant, user=self.other_owner, role=MerchantStaff.Role.OWNER)
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(self.admin)
        self.merchant_client = APIClient()
        self.merchant_client.force_authenticate(self.owner)
        self.other_client = APIClient()
        self.other_client.force_authenticate(self.other_owner)

    def _payload(self, **overrides):
        payload = {
            "title": "平台模板商品",
            "type": "PHYSICAL",
            "category_id": self.child.id,
            "price_amount": 1000,
            "delivery_types": ["EXPRESS"],
            "skus": [{"sku_code": "A", "spec": {"name": "标准"}, "price_amount": 1000, "stock": 10}],
            "status": "PUBLISHED",
            "scope": "ALL",
        }
        payload.update(overrides)
        return payload

    def _create_template(self, **overrides):
        return self.admin_client.post("/api/v1/admin/product-templates/", self._payload(**overrides), format="json")

    def test_template_distribution_visibility(self):
        none = self._create_template(scope="NONE")
        self.assertEqual(none.status_code, 201, none.data)
        self.assertEqual(self.merchant_client.get("/api/v1/merchant/product-templates/").data["data"], [])

        all_template = self._create_template()
        self.assertEqual(all_template.status_code, 201, all_template.data)
        visible = self.merchant_client.get("/api/v1/merchant/product-templates/").data["data"]
        self.assertEqual(len(visible), 1)
        self.assertEqual(visible[0]["title"], "平台模板商品")

        selected = self._create_template(scope="SELECTED", merchant_ids=[self.merchant.id])
        self.assertEqual(selected.status_code, 201, selected.data)
        self.assertEqual(len(self.merchant_client.get("/api/v1/merchant/product-templates/").data["data"]), 2)
        self.assertEqual(len(self.other_client.get("/api/v1/merchant/product-templates/").data["data"]), 1)

    def test_merchant_adopts_template_idempotently(self):
        template = ProductTemplate.objects.get(pk=self._create_template().data["data"]["id"])
        first = self.merchant_client.post(
            f"/api/v1/merchant/product-templates/{template.id}/adopt/", {"listed": True}, format="json"
        )
        self.assertEqual(first.status_code, 201, first.data)
        product = Product.objects.get(pk=first.data["data"]["product_id"])
        self.assertEqual(product.status, Product.Status.ON_SALE)
        self.assertEqual(product.template, template)
        self.assertEqual(product.skus.count(), 1)
        adoption = TemplateAdoption.objects.get(template=template, merchant=self.merchant)
        self.assertEqual(adoption.product, product)

        again = self.merchant_client.post(
            f"/api/v1/merchant/product-templates/{template.id}/adopt/", {"listed": True}, format="json"
        )
        self.assertEqual(again.status_code, 200)
        self.assertEqual(again.data["data"]["product_id"], product.id)

        other = self.other_client.post(
            f"/api/v1/merchant/product-templates/{template.id}/adopt/", {"listed": False}, format="json"
        )
        self.assertEqual(other.status_code, 201, other.data)
        self.assertEqual(Product.objects.filter(template=template).count(), 2)

    def test_manual_sync_updates_adopted_product(self):
        template = ProductTemplate.objects.get(pk=self._create_template().data["data"]["id"])
        product_id = self.merchant_client.post(
            f"/api/v1/merchant/product-templates/{template.id}/adopt/", {}, format="json"
        ).data["data"]["product_id"]

        updated = self.admin_client.put(
            f"/api/v1/admin/product-templates/{template.id}/",
            self._payload(
                title="模板已更新",
                price_amount=1200,
                skus=[{"sku_code": "A", "spec": {"name": "标准"}, "price_amount": 1200, "stock": 10}],
            ),
            format="json",
        )
        self.assertEqual(updated.status_code, 200, updated.data)
        sync = self.admin_client.post(f"/api/v1/admin/product-templates/{template.id}/sync/", {}, format="json")
        self.assertEqual(sync.status_code, 200, sync.data)
        self.assertEqual(sync.data["data"]["synced"], 1)
        product = Product.objects.get(pk=product_id)
        self.assertEqual(product.title, "模板已更新")
        self.assertEqual(product.price, 1200)
        self.assertEqual(product.skus.get(sku_code="A").price, 1200)
