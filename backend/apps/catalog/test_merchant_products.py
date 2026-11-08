"""商户发布商品、编辑重审、上下架与平台审核。"""

from decimal import Decimal
from uuid import uuid4

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import AppUser
from apps.catalog.models import Category, Product, ProductSku
from apps.governance.models import AuditTask, OperationLog
from apps.merchants.models import Merchant, MerchantStaff


class MerchantProductTests(TestCase):
    def setUp(self):
        self.owner = AppUser.objects.create_user(phone="13900000401", password="pass12345")
        self.clerk = AppUser.objects.create_user(phone="13900000402", password="pass12345")
        self.other_owner = AppUser.objects.create_user(phone="13900000403", password="pass12345")
        self.admin = AppUser.objects.create_user(phone="13900000404", password="pass12345", is_staff=True)

        self.category = Category.objects.create(name="商品类目", commission_rate=Decimal("0.0500"))
        self.merchant = Merchant.objects.create(
            merchant_no="M801", name="发布商户", category=self.category, status=Merchant.Status.ACTIVE
        )
        self.other_merchant = Merchant.objects.create(
            merchant_no="M802", name="其他商户", category=self.category, status=Merchant.Status.ACTIVE
        )
        MerchantStaff.objects.create(merchant=self.merchant, user=self.owner, role=MerchantStaff.Role.OWNER)
        MerchantStaff.objects.create(merchant=self.merchant, user=self.clerk, role=MerchantStaff.Role.CLERK)
        MerchantStaff.objects.create(merchant=self.other_merchant, user=self.other_owner, role=MerchantStaff.Role.OWNER)

        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        self.clerk_client = APIClient()
        self.clerk_client.force_authenticate(self.clerk)
        self.other_client = APIClient()
        self.other_client.force_authenticate(self.other_owner)
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(self.admin)

    def _payload(self, **overrides):
        payload = {
            "category_id": self.category.id,
            "type": "PHYSICAL",
            "title": "双人套餐",
            "subtitle": "到店自提",
            "cover_url": "https://example.com/cover.png",
            "description": "含两份主食",
            "price_amount": 1000,
            "original_price_amount": 1200,
            "verify_days": 30,
            "appointment_required": False,
            "delivery_types": ["EXPRESS", "PICKUP"],
            "skus": [
                {"sku_code": "A", "spec": {"name": "标准份"}, "price_amount": 1000, "stock": 10},
                {"sku_code": "B", "spec": {"name": "大份"}, "price_amount": 1500, "stock": 5},
            ],
        }
        payload.update(overrides)
        return payload

    def _create(self, client=None, key=None):
        return (client or self.client).post(
            "/api/v1/merchant/products/",
            self._payload(),
            format="json",
            HTTP_IDEMPOTENCY_KEY=key or uuid4().hex,
        )

    def test_create_product_submits_audit(self):
        response = self._create()
        self.assertEqual(response.status_code, 201, response.data)
        product = Product.objects.get(pk=response.data["data"]["id"])
        self.assertEqual(product.status, Product.Status.PENDING_AUDIT)
        self.assertEqual(product.merchant, self.merchant)
        self.assertEqual(product.skus.count(), 2)
        self.assertIsNotNone(product.submitted_at)
        task = AuditTask.objects.get(biz_type=AuditTask.BizType.PRODUCT, biz_id=product.id)
        self.assertEqual(task.status, AuditTask.Status.PENDING)
        self.assertTrue(OperationLog.objects.filter(action="PRODUCT_SUBMIT", biz_id=product.id).exists())

    def test_create_requires_owner_or_manager(self):
        response = self._create(self.clerk_client)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.clerk_client.get("/api/v1/merchant/products/").status_code, 200)

    def test_create_is_idempotent(self):
        key = uuid4().hex
        first = self._create(key=key)
        second = self._create(key=key)
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(first.data["data"]["id"], second.data["data"]["id"])
        self.assertEqual(Product.objects.count(), 1)

    def test_create_validates_delivery_type(self):
        response = self.client.post(
            "/api/v1/merchant/products/",
            self._payload(type="SERVICE", delivery_types=["EXPRESS"]),
            format="json",
            HTTP_IDEMPOTENCY_KEY=uuid4().hex,
        )
        self.assertEqual(response.status_code, 422)

    def test_list_only_own_products(self):
        self._create()
        self._create(self.other_client)
        response = self.client.get("/api/v1/merchant/products/?status=PENDING_AUDIT")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["data"]["page"]["total"], 1)

    def test_detail_is_scoped_to_merchant(self):
        product_id = self._create().data["data"]["id"]
        self.assertEqual(self.client.get(f"/api/v1/merchant/products/{product_id}/").status_code, 200)
        self.assertEqual(self.other_client.get(f"/api/v1/merchant/products/{product_id}/").status_code, 404)

    def test_update_requires_version(self):
        product_id = self._create().data["data"]["id"]
        response = self.client.put(f"/api/v1/merchant/products/{product_id}/", self._payload(), format="json")
        self.assertEqual(response.status_code, 422)

        stale = self.client.put(
            f"/api/v1/merchant/products/{product_id}/",
            self._payload(version=9),
            format="json",
        )
        self.assertEqual(stale.status_code, 409)

    def test_admin_approve_product(self):
        product = Product.objects.get(pk=self._create().data["data"]["id"])
        task = AuditTask.objects.get(biz_type=AuditTask.BizType.PRODUCT, biz_id=product.id)
        response = self.admin_client.post(
            f"/api/v1/admin/audits/{task.id}/decision/", {"decision": "APPROVE"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        product.refresh_from_db()
        self.assertEqual(product.status, Product.Status.ON_SALE)
        self.assertIsNotNone(product.audited_at)
        self.assertEqual(product.reject_reason, "")

    def test_admin_reject_and_merchant_resubmit(self):
        product = Product.objects.get(pk=self._create().data["data"]["id"])
        task = AuditTask.objects.get(biz_type=AuditTask.BizType.PRODUCT, biz_id=product.id)
        response = self.admin_client.post(
            f"/api/v1/admin/audits/{task.id}/decision/",
            {"decision": "REJECT", "reason": "主图不清晰"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        product.refresh_from_db()
        self.assertEqual(product.status, Product.Status.REJECTED)
        self.assertEqual(product.reject_reason, "主图不清晰")

        resubmit = self.client.put(
            f"/api/v1/merchant/products/{product.id}/",
            self._payload(version=product.version, cover_url="https://example.com/cover2.png"),
            format="json",
        )
        self.assertEqual(resubmit.status_code, 200, resubmit.data)
        product.refresh_from_db()
        self.assertEqual(product.status, Product.Status.PENDING_AUDIT)
        self.assertFalse(product.reject_reason)
        self.assertEqual(AuditTask.objects.filter(biz_type=AuditTask.BizType.PRODUCT, biz_id=product.id).count(), 2)

    def test_stock_only_edit_keeps_on_sale_and_price_change_reaudits(self):
        product = Product.objects.get(pk=self._create().data["data"]["id"])
        product.status = Product.Status.ON_SALE
        product.save(update_fields=["status"])

        stock_edit = self._payload(
            version=product.version,
            skus=[
                {"sku_code": "A", "spec": {"name": "标准份"}, "price_amount": 1000, "stock": 20},
                {"sku_code": "B", "spec": {"name": "大份"}, "price_amount": 1500, "stock": 5},
            ],
        )
        response = self.client.put(f"/api/v1/merchant/products/{product.id}/", stock_edit, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        product.refresh_from_db()
        self.assertEqual(product.status, Product.Status.ON_SALE)

        price_edit = self._payload(
            version=product.version,
            price_amount=1100,
            skus=[
                {"sku_code": "A", "spec": {"name": "标准份"}, "price_amount": 1100, "stock": 20},
                {"sku_code": "B", "spec": {"name": "大份"}, "price_amount": 1500, "stock": 5},
            ],
        )
        response = self.client.put(f"/api/v1/merchant/products/{product.id}/", price_edit, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        product.refresh_from_db()
        self.assertEqual(product.status, Product.Status.PENDING_AUDIT)

    def test_off_sale_and_on_sale(self):
        product = Product.objects.get(pk=self._create().data["data"]["id"])
        product.status = Product.Status.ON_SALE
        product.save(update_fields=["status"])
        url = f"/api/v1/merchant/products/{product.id}/status/"

        off = self.client.post(url, {"status": "OFF_SALE"}, format="json")
        self.assertEqual(off.status_code, 200, off.data)
        product.refresh_from_db()
        self.assertEqual(product.status, Product.Status.OFF_SALE)

        on = self.client.post(url, {"status": "ON_SALE"}, format="json")
        self.assertEqual(on.status_code, 200, on.data)
        product.refresh_from_db()
        self.assertEqual(product.status, Product.Status.ON_SALE)

        again = self.client.post(url, {"status": "ON_SALE"}, format="json")
        self.assertEqual(again.status_code, 409)

    def test_admin_product_detail(self):
        product = Product.objects.get(pk=self._create().data["data"]["id"])
        response = self.admin_client.get(f"/api/v1/admin/products/{product.id}/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["data"]["title"], "双人套餐")
        self.assertEqual(len(response.data["data"]["skus"]), 2)


class ProductStatusEnumTests(TestCase):
    def test_sku_available_stock(self):
        category = Category.objects.create(name="库存类目")
        merchant = Merchant.objects.create(merchant_no="M810", name="库存商户", category=category)
        product = Product.objects.create(
            merchant=merchant, category=category, type=Product.Type.PHYSICAL, title="库存商品", price=100
        )
        sku = ProductSku.objects.create(
            product=product, sku_code="S1", price=100, stock=5, locked_stock=1, sold_stock=1
        )
        self.assertEqual(sku.available_stock, 3)


class ProductCategoryAndCodeTests(TestCase):
    def setUp(self):
        self.admin = AppUser.objects.create_user(phone="13900000501", password="pass12345", is_staff=True)
        self.owner = AppUser.objects.create_user(phone="13900000502", password="pass12345")
        self.other_owner = AppUser.objects.create_user(phone="13900000503", password="pass12345")
        self.category = Category.objects.create(name="餐饮", commission_rate=Decimal("0.0500"))
        self.child_category = Category.objects.create(name="快餐", parent=self.category, level=2)
        self.merchant = Merchant.objects.create(
            merchant_no="M901", name="分类商户", category=self.category, status=Merchant.Status.ACTIVE
        )
        self.other_merchant = Merchant.objects.create(
            merchant_no="M902", name="另一家分类商户", category=self.category, status=Merchant.Status.ACTIVE
        )
        MerchantStaff.objects.create(merchant=self.merchant, user=self.owner, role=MerchantStaff.Role.OWNER)
        MerchantStaff.objects.create(merchant=self.other_merchant, user=self.other_owner, role=MerchantStaff.Role.OWNER)
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        self.other_client = APIClient()
        self.other_client.force_authenticate(self.other_owner)
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(self.admin)

    def _payload(self, **overrides):
        payload = {
            "category_id": self.child_category.id,
            "type": "PHYSICAL",
            "title": "分类商品",
            "price_amount": 1000,
            "delivery_types": ["EXPRESS"],
            "skus": [{"sku_code": "A", "price_amount": 1000, "stock": 10}],
        }
        payload.update(overrides)
        return payload

    def _create_product(self, client=None, **overrides):
        return (client or self.client).post(
            "/api/v1/merchant/products/",
            self._payload(**overrides),
            format="json",
            HTTP_IDEMPOTENCY_KEY=uuid4().hex,
        )

    def test_admin_manages_two_level_categories(self):
        first = self.admin_client.post("/api/v1/admin/categories/", {"name": "一级类目"}, format="json")
        self.assertEqual(first.status_code, 201, first.data)
        second = self.admin_client.post(
            "/api/v1/admin/categories/",
            {"name": "二级类目", "parent_id": first.data["data"]["id"]},
            format="json",
        )
        self.assertEqual(second.status_code, 201, second.data)
        self.assertEqual(second.data["data"]["level"], 2)

        third = self.admin_client.post(
            "/api/v1/admin/categories/",
            {"name": "三级类目", "parent_id": second.data["data"]["id"]},
            format="json",
        )
        self.assertEqual(third.status_code, 422)

        listed = self.admin_client.get("/api/v1/admin/categories/")
        self.assertEqual(listed.status_code, 200, listed.data)
        self.assertEqual(len(listed.data["data"]), 4)
        self.assertEqual(self.client.get("/api/v1/admin/categories/").status_code, 403)

    def test_product_requires_leaf_and_enabled_category(self):
        parent = self._create_product(category_id=self.category.id)
        self.assertEqual(parent.status_code, 422)

        self.child_category.status = Category.Status.DISABLED
        self.child_category.save(update_fields=["status"])
        disabled = self._create_product()
        self.assertEqual(disabled.status_code, 422)

    def test_product_code_unique_per_merchant(self):
        first = self._create_product(product_code="AB-01")
        self.assertEqual(first.status_code, 201, first.data)

        other = self._create_product(self.other_client, product_code="AB-01")
        self.assertEqual(other.status_code, 201, other.data)

        duplicate = self._create_product(product_code="AB-01")
        self.assertEqual(duplicate.status_code, 409)

    def test_merchant_categories_are_isolated(self):
        created = self.client.post("/api/v1/merchant/product-categories/", {"name": "本店热销"}, format="json")
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(self.client.get("/api/v1/merchant/product-categories/").data["data"][0]["name"], "本店热销")
        self.assertEqual(self.other_client.get("/api/v1/merchant/product-categories/").data["data"], [])

        duplicate = self.client.post("/api/v1/merchant/product-categories/", {"name": "本店热销"}, format="json")
        self.assertEqual(duplicate.status_code, 422)

        renamed = self.client.put(
            f"/api/v1/merchant/product-categories/{created.data['data']['id']}/",
            {"name": "本店推荐", "sort": 2},
            format="json",
        )
        self.assertEqual(renamed.status_code, 200, renamed.data)
        self.assertEqual(renamed.data["data"]["name"], "本店推荐")

    def test_product_with_merchant_category_and_delete_guard(self):
        category = self.client.post("/api/v1/merchant/product-categories/", {"name": "套餐"}, format="json").data[
            "data"
        ]
        response = self._create_product(merchant_category_id=category["id"])
        self.assertEqual(response.status_code, 201, response.data)
        product = Product.objects.get(pk=response.data["data"]["id"])
        self.assertEqual(product.merchant_category_id, category["id"])
        listed = self.client.get("/api/v1/merchant/products/").data["data"]["items"][0]
        self.assertEqual(listed["merchant_category_name"], "套餐")

        blocked = self.client.delete(f"/api/v1/merchant/product-categories/{category['id']}/")
        self.assertEqual(blocked.status_code, 409)

        product.status = Product.Status.ON_SALE
        product.save(update_fields=["status"])
        foreign = self.client.post("/api/v1/merchant/product-categories/", {"name": "外部"}, format="json")
        foreign_id = foreign.data["data"]["id"]
        moved = self.client.put(
            f"/api/v1/merchant/products/{product.id}/",
            self._payload(version=product.version, merchant_category_id=foreign_id),
            format="json",
        )
        self.assertEqual(moved.status_code, 200, moved.data)
        self.assertEqual(Product.objects.get(pk=product.id).merchant_category_id, foreign_id)

        other_category = self.other_client.post(
            "/api/v1/merchant/product-categories/", {"name": "他店分类"}, format="json"
        ).data["data"]
        cross = self.client.put(
            f"/api/v1/merchant/products/{product.id}/",
            self._payload(version=product.version + 1, merchant_category_id=other_category["id"]),
            format="json",
        )
        self.assertEqual(cross.status_code, 422)
