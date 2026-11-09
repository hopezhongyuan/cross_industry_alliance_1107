"""组合下单：跨商户批量下单 + 合单支付测试。"""

from uuid import uuid4

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import AppUser
from apps.catalog.models import Category, Product, ProductSku
from apps.merchants.models import Merchant
from apps.orders.models import Order
from apps.payments.models import PaymentGroup
from apps.points.models import UserPointAccount


class BatchOrderFlowTests(TestCase):
    def setUp(self):
        self.consumer = AppUser.objects.create_user(phone="13900000020", password="pass12345")
        self.client = APIClient()
        self.client.force_authenticate(self.consumer)

        self.category = Category.objects.create(name="组合下单类目", commission_rate="0.0500")
        self.merchant_a = Merchant.objects.create(
            merchant_no="BA001", name="商户A", category=self.category, status=Merchant.Status.ACTIVE
        )
        self.merchant_b = Merchant.objects.create(
            merchant_no="BA002", name="商户B", category=self.category, status=Merchant.Status.ACTIVE
        )
        self.product_a = Product.objects.create(
            merchant=self.merchant_a,
            category=self.category,
            type=Product.Type.PHYSICAL,
            title="商户A商品",
            price=1000,
            status=Product.Status.ON_SALE,
        )
        self.sku_a = ProductSku.objects.create(product=self.product_a, sku_code="BA-SKU-A", price=1000, stock=10)
        self.product_b = Product.objects.create(
            merchant=self.merchant_b,
            category=self.category,
            type=Product.Type.PHYSICAL,
            title="商户B商品",
            price=2000,
            status=Product.Status.ON_SALE,
        )
        self.sku_b = ProductSku.objects.create(product=self.product_b, sku_code="BA-SKU-B", price=2000, stock=10)

    def _batch_payload(self):
        return {
            "groups": [
                {
                    "merchant_id": self.merchant_a.id,
                    "order_type": "EXPRESS",
                    "items": [{"product_id": self.product_a.id, "sku_id": self.sku_a.id, "quantity": 2}],
                },
                {
                    "merchant_id": self.merchant_b.id,
                    "order_type": "EXPRESS",
                    "items": [{"product_id": self.product_b.id, "sku_id": self.sku_b.id, "quantity": 1}],
                },
            ],
            "contact": {"name": "张三", "phone": "13800138000", "address_detail": "测试地址"},
        }

    def test_batch_creates_one_order_per_merchant(self):
        idem = uuid4().hex
        response = self.client.post(
            "/api/v1/orders/batch/", self._batch_payload(), format="json", HTTP_IDEMPOTENCY_KEY=idem
        )
        self.assertEqual(response.status_code, 201, response.data)
        data = response.data["data"]
        self.assertEqual(len(data["orders"]), 2)
        self.assertEqual(data["total_amount"], 4000)
        merchant_ids = {o["merchant_id"] for o in data["orders"]}
        self.assertEqual(merchant_ids, {self.merchant_a.id, self.merchant_b.id})

        group_no = data["group_no"]
        group = PaymentGroup.objects.get(group_no=group_no)
        self.assertEqual(group.amount, 4000)
        orders = Order.objects.filter(payment_group=group)
        self.assertEqual(orders.count(), 2)
        for order in orders:
            self.assertEqual(order.status, Order.Status.PENDING_PAYMENT)

    def test_batch_idempotent_returns_same_group(self):
        idem = uuid4().hex
        first = self.client.post(
            "/api/v1/orders/batch/", self._batch_payload(), format="json", HTTP_IDEMPOTENCY_KEY=idem
        )
        self.assertEqual(first.status_code, 201)
        second = self.client.post(
            "/api/v1/orders/batch/", self._batch_payload(), format="json", HTTP_IDEMPOTENCY_KEY=idem
        )
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.data["data"]["group_no"], second.data["data"]["group_no"])
        self.assertEqual(Order.objects.count(), 2)

    def test_batch_rolls_back_when_one_merchant_invalid(self):
        payload = self._batch_payload()
        payload["groups"][1]["items"][0]["sku_id"] = 999999
        response = self.client.post("/api/v1/orders/batch/", payload, format="json", HTTP_IDEMPOTENCY_KEY=uuid4().hex)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(PaymentGroup.objects.count(), 0)

    def test_group_payment_pays_all_orders(self):
        idem = uuid4().hex
        response = self.client.post(
            "/api/v1/orders/batch/", self._batch_payload(), format="json", HTTP_IDEMPOTENCY_KEY=idem
        )
        group_no = response.data["data"]["group_no"]

        pay_resp = self.client.post(
            f"/api/v1/payment-groups/{group_no}/pay/",
            {"channel": "WECHAT_MINI"},
            format="json",
            HTTP_IDEMPOTENCY_KEY=uuid4().hex,
        )
        self.assertEqual(pay_resp.status_code, 200, pay_resp.data)

        callback = self.client.post(
            "/api/v1/callback/wechat/pay/",
            {
                "payment_no": group_no,
                "transaction_id": f"txn-{uuid4().hex[:12]}",
                "amount": 4000,
                "trade_state": "SUCCESS",
            },
            format="json",
        )
        self.assertEqual(callback.status_code, 200, callback.data)

        group = PaymentGroup.objects.get(group_no=group_no)
        self.assertEqual(group.status, PaymentGroup.Status.PAID)
        for order in Order.objects.filter(payment_group=group):
            self.assertEqual(order.status, Order.Status.PENDING_ACCEPT)
            self.assertEqual(order.paid_amount, order.payable_amount)

    def test_group_payment_awards_points_per_order(self):
        idem = uuid4().hex
        response = self.client.post(
            "/api/v1/orders/batch/", self._batch_payload(), format="json", HTTP_IDEMPOTENCY_KEY=idem
        )
        group_no = response.data["data"]["group_no"]
        self.client.post(
            f"/api/v1/payment-groups/{group_no}/pay/",
            {"channel": "WECHAT_MINI"},
            format="json",
            HTTP_IDEMPOTENCY_KEY=uuid4().hex,
        )
        self.client.post(
            "/api/v1/callback/wechat/pay/",
            {
                "payment_no": group_no,
                "transaction_id": f"txn-{uuid4().hex[:12]}",
                "amount": 4000,
                "trade_state": "SUCCESS",
            },
            format="json",
        )
        account = UserPointAccount.objects.get(user=self.consumer)
        # 每消费1元=1积分，共4000分=40元
        self.assertEqual(account.balance, 40)
