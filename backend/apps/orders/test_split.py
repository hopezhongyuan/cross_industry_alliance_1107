"""商品行分账、退款冲回与订单详情。"""

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AppUser
from apps.catalog.models import Category, Product, ProductSku
from apps.ledger.models import MerchantAccount
from apps.ledger.services import create_settlement_item, effective_commission
from apps.merchants.models import Merchant, MerchantStaff
from apps.orders.models import Order
from apps.orders.order_services import create_order
from apps.orders.split_services import apply_refund


class OrderSplitTests(TestCase):
    def setUp(self):
        self.user = AppUser.objects.create_user(phone="13900000501", password="pass12345")
        self.admin = AppUser.objects.create_user(phone="13900000502", password="pass12345", is_staff=True)
        self.staff = AppUser.objects.create_user(phone="13900000503", password="pass12345")
        self.category = Category.objects.create(name="分账类目", commission_rate="0.0500")
        self.merchant = Merchant.objects.create(
            merchant_no="M1501", name="分账商户", category=self.category, status=Merchant.Status.ACTIVE
        )
        MerchantAccount.objects.create(merchant=self.merchant)
        MerchantStaff.objects.create(merchant=self.merchant, user=self.staff, role=MerchantStaff.Role.OWNER)
        self.product_a = Product.objects.create(
            merchant=self.merchant,
            category=self.category,
            type=Product.Type.PHYSICAL,
            title="分账商品 A",
            price=333,
            status=Product.Status.ON_SALE,
        )
        self.product_b = Product.objects.create(
            merchant=self.merchant,
            category=self.category,
            type=Product.Type.PHYSICAL,
            title="分账商品 B",
            price=777,
            status=Product.Status.ON_SALE,
        )
        self.sku_a = ProductSku.objects.create(product=self.product_a, sku_code="SPLIT-A", price=333, stock=10)
        self.sku_b = ProductSku.objects.create(product=self.product_b, sku_code="SPLIT-B", price=777, stock=10)
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(self.admin)
        self.merchant_client = APIClient()
        self.merchant_client.force_authenticate(self.staff)

    def _order(self):
        order, _ = create_order(
            self.user,
            merchant_id=self.merchant.id,
            order_type=Order.Type.EXPRESS,
            items=[
                {"product_id": self.product_a.id, "sku_id": self.sku_a.id, "quantity": 1},
                {"product_id": self.product_b.id, "sku_id": self.sku_b.id, "quantity": 1},
            ],
            contact={"name": "测试", "phone": "13800000000", "address_detail": "测试地址"},
            idempotency_key="split-test-key",
            request_hash="split-test-hash",
        )
        return order

    def test_line_split_has_no_rounding_gap(self):
        order = self._order()
        items = list(order.items.order_by("id"))
        self.assertEqual(order.product_amount, 1110)
        self.assertEqual(order.commission_amount, 56)
        self.assertEqual([item.platform_amount for item in items], [17, 39])
        self.assertEqual([item.merchant_amount for item in items], [316, 738])
        self.assertEqual(order.platform_income_amount, 56)
        self.assertEqual(order.merchant_income_amount, 1054)
        self.assertEqual(sum(item.platform_amount + item.merchant_amount for item in items), order.product_amount)

    def test_line_refund_reverses_platform_and_merchant(self):
        order = self._order()
        order.paid_amount = order.payable_amount
        order.save(update_fields=["paid_amount", "updated_at"])
        first = order.items.order_by("id").first()

        apply_refund(order, 333, order_item=first)

        order.refresh_from_db()
        first.refresh_from_db()
        self.assertEqual(first.refund_amount, 333)
        self.assertEqual(first.platform_refund_amount, 17)
        self.assertEqual(first.merchant_refund_amount, 316)
        self.assertEqual(order.refunded_amount, 333)
        self.assertEqual(order.platform_refund_amount, 17)
        self.assertEqual(order.merchant_refund_amount, 316)
        self.assertEqual(order.platform_income_amount, 39)
        self.assertEqual(order.merchant_income_amount, 738)
        self.assertEqual(order.platform_income_amount + order.merchant_income_amount, 777)

    def test_full_refund_includes_delivery_fee(self):
        order = self._order()
        order.delivery_fee = 500
        order.payable_amount += 500
        order.paid_amount = order.payable_amount
        order.save(update_fields=["delivery_fee", "payable_amount", "paid_amount", "updated_at"])

        apply_refund(order, 1610)

        order.refresh_from_db()
        self.assertEqual(order.refunded_amount, 1610)
        self.assertEqual(order.platform_refund_amount, 56)
        self.assertEqual(order.merchant_refund_amount, 1554)
        self.assertEqual(order.platform_income_amount, 0)
        self.assertEqual(order.merchant_income_amount, 0)
        self.assertEqual(sum(item.refund_amount for item in order.items.all()), 1110)

    def test_settlement_commission_excludes_delivery_fee(self):
        order = self._order()
        order.status = Order.Status.COMPLETED
        order.completed_at = timezone.now()
        order.delivery_fee = 500
        order.payable_amount += 500
        order.paid_amount += 500
        order.merchant_income_amount += 500
        order.save(
            update_fields=[
                "status",
                "completed_at",
                "delivery_fee",
                "payable_amount",
                "paid_amount",
                "merchant_income_amount",
                "updated_at",
            ]
        )

        item = create_settlement_item(order)
        self.assertEqual(item.commission_amount, 56)
        self.assertEqual(item.net_amount, 1554)
        self.assertEqual(effective_commission(item), 56)

    def test_admin_and_merchant_order_detail_expose_split(self):
        order = self._order()

        admin_response = self.admin_client.get(f"/api/v1/admin/orders/{order.id}/")
        self.assertEqual(admin_response.status_code, 200, admin_response.data)
        data = admin_response.data["data"]
        self.assertEqual(data["platform_income_amount"], 56)
        self.assertEqual(data["merchant_income_amount"], 1054)
        self.assertEqual(len(data["items"]), 2)
        self.assertIn("platform_amount", data["items"][0])
        self.assertIn("merchant_amount", data["items"][0])

        merchant_response = self.merchant_client.get(f"/api/v1/merchant/orders/{order.id}/")
        self.assertEqual(merchant_response.status_code, 200, merchant_response.data)
        merchant_data = merchant_response.data["data"]
        self.assertEqual(merchant_data["merchant_income_amount"], 1054)
        self.assertEqual(merchant_data["items"][0]["platform_net_amount"], 17)
        self.assertEqual(merchant_data["items"][0]["merchant_net_amount"], 316)

    def test_merchant_cannot_read_other_merchant_order(self):
        order = self._order()
        other_merchant = Merchant.objects.create(merchant_no="M1502", name="其他商户", status=Merchant.Status.ACTIVE)
        other_staff = AppUser.objects.create_user(phone="13900000504", password="pass12345")
        MerchantStaff.objects.create(merchant=other_merchant, user=other_staff, role=MerchantStaff.Role.OWNER)
        other_client = APIClient()
        other_client.force_authenticate(other_staff)

        response = other_client.get(f"/api/v1/merchant/orders/{order.id}/")
        self.assertEqual(response.status_code, 404)
