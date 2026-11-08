"""平台后台资金路由：结算、提现、冻结与对账。"""

from django.urls import path

from .views import (
    AdminOrderFreezeView,
    AdminReconciliationView,
    AdminSettlementBatchListView,
    AdminSettlementPublishView,
    AdminWithdrawalPayoutView,
    AdminWithdrawalRejectView,
)

urlpatterns = [
    path("settlements/", AdminSettlementBatchListView.as_view(), name="admin-settlements"),
    path(
        "settlements/<int:pk>/publish/",
        AdminSettlementPublishView.as_view(),
        name="admin-settlement-publish",
    ),
    path("withdrawals/<int:pk>/payout/", AdminWithdrawalPayoutView.as_view(), name="admin-withdrawal-payout"),
    path("withdrawals/<int:pk>/reject/", AdminWithdrawalRejectView.as_view(), name="admin-withdrawal-reject"),
    path("orders/<int:pk>/freeze/", AdminOrderFreezeView.as_view(), name="admin-order-freeze"),
    path("reconciliation/", AdminReconciliationView.as_view(), name="admin-reconciliation"),
]
