"""积分服务层单元测试。"""

from django.test import TestCase

from apps.accounts.models import AppUser
from apps.points.models import PointsConfig, PointTransaction
from apps.points.services import (
    PointsError,
    adjust_by_admin,
    award_for_order_payment,
    award_for_register,
    award_for_review,
    get_or_create_account,
    post_point_transaction,
    share,
    signin,
)


class PointsServiceTests(TestCase):
    def setUp(self):
        self.user = AppUser.objects.create_user(phone="13900000701", password="pass12345")

    def test_post_increases_balance_and_total_earned(self):
        txn = post_point_transaction(
            user_id=self.user.id,
            biz_type=PointTransaction.BizType.CONSUMPTION,
            delta=100,
            idempotency_key="test:1",
        )
        self.assertEqual(txn.balance_after, 100)
        account = get_or_create_account(self.user.id)
        self.assertEqual(account.balance, 100)
        self.assertEqual(account.total_earned, 100)
        self.assertEqual(account.total_spent, 0)

    def test_post_decreases_balance_and_total_spent(self):
        post_point_transaction(
            user_id=self.user.id,
            biz_type=PointTransaction.BizType.CONSUMPTION,
            delta=100,
            idempotency_key="test:earn",
        )
        txn = post_point_transaction(
            user_id=self.user.id,
            biz_type=PointTransaction.BizType.ADMIN_ADJUST,
            delta=-30,
            idempotency_key="test:spend",
        )
        self.assertEqual(txn.balance_after, 70)
        account = get_or_create_account(self.user.id)
        self.assertEqual(account.balance, 70)
        self.assertEqual(account.total_spent, 30)

    def test_idempotency_returns_same_txn(self):
        txn1 = post_point_transaction(
            user_id=self.user.id,
            biz_type=PointTransaction.BizType.SIGNIN,
            delta=5,
            idempotency_key="idem:1",
        )
        txn2 = post_point_transaction(
            user_id=self.user.id,
            biz_type=PointTransaction.BizType.SIGNIN,
            delta=5,
            idempotency_key="idem:1",
        )
        self.assertEqual(txn1.id, txn2.id)
        account = get_or_create_account(self.user.id)
        self.assertEqual(account.balance, 5)
        self.assertEqual(PointTransaction.objects.count(), 1)

    def test_negative_balance_raises(self):
        with self.assertRaises(PointsError):
            post_point_transaction(
                user_id=self.user.id,
                biz_type=PointTransaction.BizType.ADMIN_ADJUST,
                delta=-1,
                idempotency_key="neg:1",
            )

    def test_zero_delta_raises(self):
        with self.assertRaises(PointsError):
            post_point_transaction(
                user_id=self.user.id,
                biz_type=PointTransaction.BizType.ADMIN_ADJUST,
                delta=0,
                idempotency_key="zero:1",
            )

    def test_award_for_order_payment(self):
        PointsConfig.objects.update_or_create(singleton_key="default", defaults={"consumption_rate": 100})
        txn = award_for_order_payment(self.user.id, order_no="O001", paid_amount=2580, order_id=1)
        self.assertIsNotNone(txn)
        self.assertEqual(txn.delta, 25)  # 2580 // 100 = 25
        account = get_or_create_account(self.user.id)
        self.assertEqual(account.balance, 25)

    def test_award_for_order_payment_respects_max(self):
        PointsConfig.objects.update_or_create(
            singleton_key="default", defaults={"consumption_rate": 1, "consumption_max_per_order": 50}
        )
        txn = award_for_order_payment(self.user.id, order_no="O002", paid_amount=10000, order_id=2)
        self.assertEqual(txn.delta, 50)

    def test_award_for_order_payment_disabled_returns_none(self):
        PointsConfig.objects.update_or_create(singleton_key="default", defaults={"enabled": False})
        self.assertIsNone(award_for_order_payment(self.user.id, order_no="O003", paid_amount=1000, order_id=3))

    def test_signin_once_per_day(self):
        txn1 = signin(self.user.id)
        txn2 = signin(self.user.id)
        self.assertEqual(txn1.id, txn2.id)  # 幂等
        account = get_or_create_account(self.user.id)
        self.assertEqual(account.balance, 5)

    def test_share_daily_limit(self):
        PointsConfig.objects.update_or_create(
            singleton_key="default", defaults={"share_points": 2, "share_daily_limit": 2}
        )
        t1 = share(self.user.id, "PRODUCT", 1)
        t2 = share(self.user.id, "PRODUCT", 2)
        t3 = share(self.user.id, "MERCHANT", 3)
        self.assertIsNotNone(t1)
        self.assertIsNotNone(t2)
        self.assertIsNone(t3)  # 超过上限
        account = get_or_create_account(self.user.id)
        self.assertEqual(account.balance, 4)

    def test_award_for_register(self):
        txn = award_for_register(self.user.id)
        self.assertEqual(txn.delta, 50)
        # 幂等：重复注册不重复发
        award_for_register(self.user.id)
        account = get_or_create_account(self.user.id)
        self.assertEqual(account.balance, 50)
        self.assertEqual(PointTransaction.objects.count(), 1)

    def test_award_for_review(self):
        txn = award_for_review(self.user.id, order_id=99)
        self.assertEqual(txn.delta, 3)
        # 幂等
        award_for_review(self.user.id, order_id=99)
        self.assertEqual(PointTransaction.objects.count(), 1)

    def test_adjust_by_admin(self):
        award_for_register(self.user.id)  # 50
        txn = adjust_by_admin(user_id=self.user.id, delta=-20, reason="测试扣减", operator_name="admin")
        self.assertEqual(txn.balance_after, 30)
        self.assertEqual(txn.operator_name, "admin")

    def test_adjust_by_admin_requires_reason(self):
        from apps.common.api import ApiError

        with self.assertRaises(ApiError):
            adjust_by_admin(user_id=self.user.id, delta=10, reason="")
