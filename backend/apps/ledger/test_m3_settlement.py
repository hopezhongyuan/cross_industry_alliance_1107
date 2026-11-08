"""M3 资金与结算闭环测试：批次、提现、冻结、对账与已结算退款。"""

from datetime import timedelta
from io import StringIO
from uuid import uuid4

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AppUser
from apps.aftersales.models import AfterSale
from apps.catalog.models import Category, Product, ProductSku
from apps.governance.models import RuleVersion
from apps.ledger.models import MerchantAccount, SettlementBatch, SettlementItem, WithdrawalOrder
from apps.ledger.services import create_settlement_batch
from apps.merchants.models import Merchant, MerchantStaff
from apps.orders.models import Order
from apps.payments.models import PaymentOrder, PlatformPaymentConfig


class M3SettlementTests(TestCase):
    def setUp(self):
        self.consumer = AppUser.objects.create_user(phone="13900000030", password="pass12345")
        self.staff = AppUser.objects.create_user(phone="13900000031", password="pass12345")
        self.admin = AppUser.objects.create_user(phone="13900000032", password="pass12345", is_staff=True)
        self.client = APIClient()
        self.client.force_authenticate(self.consumer)
        self.merchant_client = APIClient()
        self.merchant_client.force_authenticate(self.staff)
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(self.admin)

        self.category = Category.objects.create(name="M3 类目", commission_rate="0.0500")
        self.merchant = Merchant.objects.create(
            merchant_no="M300",
            name="M3 商户",
            category=self.category,
            status=Merchant.Status.ACTIVE,
            settlement_cycle_days=0,
        )
        MerchantStaff.objects.create(merchant=self.merchant, user=self.staff, role=MerchantStaff.Role.OWNER)
        self.product = Product.objects.create(
            merchant=self.merchant,
            category=self.category,
            type=Product.Type.PHYSICAL,
            title="M3 商品",
            price=1000,
            status=Product.Status.ON_SALE,
        )
        self.sku = ProductSku.objects.create(product=self.product, sku_code="M3-SKU", price=1000, stock=10)

    def _completed_order(self, quantity=1):
        payload = {
            "merchant_id": self.merchant.id,
            "order_type": "EXPRESS",
            "items": [{"product_id": self.product.id, "sku_id": self.sku.id, "quantity": quantity}],
            "contact": {"name": "张三", "phone": "13800138000", "address_detail": "测试地址"},
        }
        response = self.client.post("/api/v1/orders/", payload, format="json", HTTP_IDEMPOTENCY_KEY=uuid4().hex)
        self.assertEqual(response.status_code, 201, response.data)
        order = Order.objects.get(pk=response.data["data"]["id"])

        pay = self.client.post(f"/api/v1/orders/{order.id}/pay/", {}, format="json", HTTP_IDEMPOTENCY_KEY=uuid4().hex)
        self.assertEqual(pay.status_code, 200, pay.data)
        payment = PaymentOrder.objects.get(order=order)
        self.assertEqual(
            self.client.post(
                "/api/v1/callback/wechat/pay/",
                {
                    "payment_no": payment.payment_no,
                    "transaction_id": f"txn-{uuid4().hex[:12]}",
                    "amount": payment.amount,
                    "trade_state": "SUCCESS",
                },
                format="json",
            ).status_code,
            200,
        )
        self.merchant_client.post(f"/api/v1/merchant/orders/{order.id}/accept/", {}, format="json")
        self.merchant_client.post(f"/api/v1/merchant/orders/{order.id}/ship/", {}, format="json")
        self.assertEqual(self.client.post(f"/api/v1/orders/{order.id}/confirm/", {}, format="json").status_code, 200)
        order.refresh_from_db()
        return order

    def _due_item(self, quantity=1):
        order = self._completed_order(quantity=quantity)
        SettlementItem.objects.filter(order=order).update(due_at=timezone.now() - timedelta(minutes=1))
        return order, SettlementItem.objects.get(order=order)

    def _publish(self):
        batch = create_settlement_batch()
        if batch is None:
            batch = SettlementBatch.objects.first()
        response = self.admin_client.post(f"/api/v1/admin/settlements/{batch.id}/publish/", {}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        return batch

    def _withdraw(self, amount):
        response = self.merchant_client.post(
            "/api/v1/merchant/withdrawals/",
            {"amount": amount},
            format="json",
            HTTP_IDEMPOTENCY_KEY=uuid4().hex,
        )
        return response

    def _audit(self):
        call_command("audit_ledger", stdout=StringIO())

    def test_batch_scans_due_items_and_publish_splits_commission(self):
        order, item = self._due_item()
        batch = create_settlement_batch()
        self.assertIsNotNone(batch)
        self.assertEqual(batch.status, SettlementBatch.Status.PENDING)
        self.assertEqual(batch.net_amount, 950)
        item.refresh_from_db()
        self.assertEqual(item.batch_id, batch.id)

        published = self._publish()
        published.refresh_from_db()
        item.refresh_from_db()
        account = MerchantAccount.objects.get(merchant=self.merchant)
        self.assertEqual(published.status, SettlementBatch.Status.PUBLISHED)
        self.assertEqual(published.total_amount, 1000)
        self.assertEqual(published.commission_amount, 50)
        self.assertEqual(item.status, SettlementItem.Status.SETTLED)
        self.assertEqual(account.pending_balance, 0)
        self.assertEqual(account.available_balance, 950)
        self._audit()

        self._publish()
        self.assertEqual(MerchantAccount.objects.get(merchant=self.merchant).available_balance, 950)

    def test_batch_command_creates_batch(self):
        self._due_item()
        out = StringIO()
        call_command("create_settlement_batches", stdout=out)
        self.assertIn("created=1", out.getvalue())
        self.assertEqual(SettlementBatch.objects.count(), 1)

    def test_close_expired_orders_releases_resources(self):
        payload = {
            "merchant_id": self.merchant.id,
            "order_type": "EXPRESS",
            "items": [{"product_id": self.product.id, "sku_id": self.sku.id, "quantity": 1}],
            "contact": {"name": "张三", "phone": "13800138000", "address_detail": "测试地址"},
        }
        response = self.client.post("/api/v1/orders/", payload, format="json", HTTP_IDEMPOTENCY_KEY=uuid4().hex)
        self.assertEqual(response.status_code, 201, response.data)
        order = Order.objects.get(pk=response.data["data"]["id"])
        Order.objects.filter(pk=order.pk).update(expire_at=timezone.now() - timedelta(minutes=1))
        self.sku.refresh_from_db()
        self.assertEqual(self.sku.locked_stock, 1)

        out = StringIO()
        call_command("close_expired_orders", stdout=out)
        self.assertIn("closed=1", out.getvalue())
        order.refresh_from_db()
        self.sku.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CLOSED)
        self.assertEqual(self.sku.locked_stock, 0)

    def test_frozen_item_is_excluded_until_unfrozen(self):
        order, item = self._due_item()
        applied = self.client.post(
            "/api/v1/after-sales/",
            {"order_id": order.id, "type": "REFUND_ONLY", "reason_code": "OTHER", "request_amount": 500},
            format="json",
        )
        self.assertEqual(applied.status_code, 201, applied.data)
        item.refresh_from_db()
        self.assertEqual(item.status, SettlementItem.Status.FROZEN)
        self.assertIsNone(create_settlement_batch())

        after_sale = AfterSale.objects.get(pk=applied.data["data"]["id"])
        self.merchant_client.post(
            f"/api/v1/merchant/after-sales/{after_sale.id}/decision/",
            {"decision": "REJECT", "reason": "不成立"},
            format="json",
        )
        item.refresh_from_db()
        self.assertEqual(item.status, SettlementItem.Status.PENDING)
        self.assertIsNotNone(create_settlement_batch())

    def test_withdrawal_request_reject_and_payout(self):
        self._due_item()
        self._publish()

        requested = self._withdraw(300)
        self.assertEqual(requested.status_code, 201, requested.data)
        withdrawal = WithdrawalOrder.objects.get(pk=requested.data["data"]["id"])
        account = MerchantAccount.objects.get(merchant=self.merchant)
        self.assertEqual(account.available_balance, 650)
        self.assertEqual(account.withdrawing_balance, 300)

        rejected = self.admin_client.post(
            f"/api/v1/admin/withdrawals/{withdrawal.id}/reject/", {"reason": "账户信息不符"}, format="json"
        )
        self.assertEqual(rejected.status_code, 200, rejected.data)
        account.refresh_from_db()
        withdrawal.refresh_from_db()
        self.assertEqual(withdrawal.status, WithdrawalOrder.Status.REJECTED)
        self.assertEqual(account.available_balance, 950)
        self.assertEqual(account.withdrawing_balance, 0)

        second = self._withdraw(300)
        self.assertEqual(second.status_code, 201, second.data)
        paid = self.admin_client.post(
            f"/api/v1/admin/withdrawals/{second.data['data']['id']}/payout/",
            {
                "voucher_no": "BANK-001",
                "voucher_url": "https://example.com/voucher.png",
                "paid_at": timezone.now().isoformat(),
            },
            format="json",
        )
        self.assertEqual(paid.status_code, 200, paid.data)
        account.refresh_from_db()
        self.assertEqual(paid.data["data"]["status"], WithdrawalOrder.Status.PAID)
        self.assertEqual(account.available_balance, 650)
        self.assertEqual(account.withdrawing_balance, 0)
        self._audit()

    def test_withdrawal_over_balance_rejected(self):
        self._due_item()
        self._publish()
        response = self._withdraw(1000)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "WITHDRAW_BALANCE_NOT_ENOUGH")

    def test_withdrawal_request_is_idempotent(self):
        self._due_item()
        self._publish()
        key = uuid4().hex
        first = self.merchant_client.post(
            "/api/v1/merchant/withdrawals/", {"amount": 200}, format="json", HTTP_IDEMPOTENCY_KEY=key
        )
        second = self.merchant_client.post(
            "/api/v1/merchant/withdrawals/", {"amount": 200}, format="json", HTTP_IDEMPOTENCY_KEY=key
        )
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(second.status_code, 201, second.data)
        self.assertEqual(first.data["data"]["id"], second.data["data"]["id"])
        self.assertEqual(WithdrawalOrder.objects.count(), 1)
        self.assertEqual(MerchantAccount.objects.get(merchant=self.merchant).available_balance, 750)

    def test_statements_and_account_summary(self):
        order, _ = self._due_item()
        self._publish()

        statements = self.merchant_client.get("/api/v1/merchant/statements/")
        self.assertEqual(statements.status_code, 200, statements.data)
        self.assertEqual(statements.data["data"]["page"]["total"], 1)
        self.assertEqual(statements.data["data"]["items"][0]["order_no"], order.order_no)
        self.assertEqual(statements.data["data"]["items"][0]["net_amount"], 950)

        account = self.merchant_client.get("/api/v1/merchant/account/")
        self.assertEqual(account.status_code, 200, account.data)
        self.assertEqual(account.data["data"]["available_balance"], 950)

        filtered = self.merchant_client.get("/api/v1/merchant/statements/?status=SETTLED")
        self.assertEqual(filtered.data["data"]["page"]["total"], 1)

    def test_admin_freeze_and_unfreeze_settlement(self):
        order, item = self._due_item()
        frozen = self.admin_client.post(
            f"/api/v1/admin/orders/{order.id}/freeze/",
            {"action": "FREEZE", "reason": "客诉核查"},
            format="json",
            HTTP_IDEMPOTENCY_KEY=uuid4().hex,
        )
        self.assertEqual(frozen.status_code, 200, frozen.data)
        item.refresh_from_db()
        account = MerchantAccount.objects.get(merchant=self.merchant)
        self.assertEqual(item.status, SettlementItem.Status.FROZEN)
        self.assertEqual(account.frozen_balance, 1000)
        self.assertEqual(account.pending_balance, 0)

        unfrozen = self.admin_client.post(
            f"/api/v1/admin/orders/{order.id}/freeze/",
            {"action": "UNFREEZE", "reason": "核查通过"},
            format="json",
            HTTP_IDEMPOTENCY_KEY=uuid4().hex,
        )
        self.assertEqual(unfrozen.status_code, 200, unfrozen.data)
        item.refresh_from_db()
        account.refresh_from_db()
        self.assertEqual(item.status, SettlementItem.Status.PENDING)
        self.assertEqual(account.pending_balance, 1000)
        self._audit()

    def test_reconciliation_reports_no_diff(self):
        self._due_item()
        self._publish()
        response = self.admin_client.get(f"/api/v1/admin/reconciliation/?date={timezone.localdate().isoformat()}")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["data"]["unresolved_count"], 0)

    def test_settled_order_refund_deducts_available_and_reverses_commission(self):
        order, _ = self._due_item()
        self._publish()

        applied = self.client.post(
            "/api/v1/after-sales/",
            {"order_id": order.id, "type": "REFUND_ONLY", "reason_code": "SERVICE_ISSUE", "request_amount": 500},
            format="json",
        )
        self.assertEqual(applied.status_code, 201, applied.data)
        after_sale = AfterSale.objects.get(pk=applied.data["data"]["id"])
        self.assertEqual(after_sale.status, AfterSale.Status.APPLIED)

        decided = self.merchant_client.post(
            f"/api/v1/merchant/after-sales/{after_sale.id}/decision/",
            {"decision": "AGREE", "approved_amount": 500, "reason": "赔付"},
            format="json",
        )
        self.assertEqual(decided.status_code, 200, decided.data)
        order.refresh_from_db()
        item = SettlementItem.objects.get(order=order)
        account = MerchantAccount.objects.get(merchant=self.merchant)
        self.assertEqual(order.refunded_amount, 500)
        self.assertEqual(item.refund_amount, 500)
        self.assertEqual(item.commission_amount, 25)
        self.assertEqual(account.available_balance, 475)
        self._audit()

    def test_admin_only_operations_require_staff(self):
        order, _ = self._due_item()
        batch = create_settlement_batch()
        for url, payload in (
            (f"/api/v1/admin/settlements/{batch.id}/publish/", {}),
            (f"/api/v1/admin/orders/{order.id}/freeze/", {"action": "FREEZE", "reason": "x"}),
        ):
            response = self.client.post(url, payload, format="json", HTTP_IDEMPOTENCY_KEY=uuid4().hex)
            self.assertEqual(response.status_code, 403, url)
        self.assertEqual(self.client.get("/api/v1/admin/logs/").status_code, 403)
        self.assertEqual(
            self.client.get(f"/api/v1/admin/reconciliation/?date={timezone.localdate().isoformat()}").status_code,
            403,
        )

    def test_operation_log_written_on_publish(self):
        self._due_item()
        self._publish()
        response = self.admin_client.get("/api/v1/admin/logs/?biz_type=SETTLEMENT_BATCH")
        self.assertEqual(response.status_code, 200, response.data)
        actions = [item["action"] for item in response.data["data"]["items"]]
        self.assertIn("SETTLEMENT_PUBLISH", actions)

    def test_rule_version_publish_retires_previous(self):
        first = self.admin_client.put("/api/v1/admin/rules/", {"snapshot": {"n": 1}, "remark": "v1"}, format="json")
        self.assertEqual(first.status_code, 200, first.data)
        second = self.admin_client.put("/api/v1/admin/rules/", {"snapshot": {"n": 2}, "remark": "v2"}, format="json")
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(RuleVersion.objects.filter(status=RuleVersion.Status.ACTIVE).count(), 1)
        self.assertEqual(RuleVersion.objects.get(status=RuleVersion.Status.RETIRED).snapshot_json, {"n": 1})

    def test_payment_config_write_and_read_without_secrets(self):
        response = self.admin_client.put(
            "/api/v1/admin/payment-configs/WECHAT_MINI/",
            {
                "merchant_no": "1900000001",
                "api_v3_key": "k" * 32,
                "private_key": "PRIVATE-PEM",
                "platform_cert": "CERT-PEM",
                "app_id": "wx123",
                "notify_url": "https://example.com/notify",
                "enabled": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        config = PlatformPaymentConfig.objects.get(channel="WECHAT_MINI")
        self.assertEqual(config.api_v3_key, "k" * 32)
        self.assertEqual(config.private_key, "PRIVATE-PEM")

        read = self.admin_client.get("/api/v1/admin/payment-configs/WECHAT_MINI/")
        self.assertEqual(read.status_code, 200, read.data)
        self.assertNotIn("api_v3_key", read.data["data"])
        self.assertNotIn("private_key", read.data["data"])
        self.assertEqual(read.data["data"]["merchant_no"], "1900000001")
