"""商户端资金路由：提现、账单、账户余额。"""

from django.urls import path

from .views import MerchantAccountSummaryView, MerchantStatementListView, MerchantWithdrawalCreateView

urlpatterns = [
    path("withdrawals/", MerchantWithdrawalCreateView.as_view(), name="merchant-withdrawal-create"),
    path("statements/", MerchantStatementListView.as_view(), name="merchant-statements"),
    path("account/", MerchantAccountSummaryView.as_view(), name="merchant-account-summary"),
]
