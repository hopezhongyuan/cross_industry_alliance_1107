"""结算、提现、账单与对账接口。"""

from django.db.models import Count
from django.utils.dateparse import parse_date
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated

from apps.common.api import ApiError, EnvelopeAPIView, EnvelopeResponse, ok, paginated
from apps.governance.services import require_platform_admin
from apps.merchants.services import get_active_staff_merchant

from .models import SettlementBatch, SettlementItem
from .serializers import (
    FreezeInputSerializer,
    PayoutInputSerializer,
    RejectInputSerializer,
    SettlementBatchSerializer,
    StatementItemSerializer,
    WithdrawalInputSerializer,
    WithdrawalSerializer,
)
from .services import (
    payout_withdrawal,
    publish_settlement_batch,
    reconciliation_report,
    reject_withdrawal,
    request_withdrawal,
    set_order_settlement_freeze,
)

STATEMENT_STATUSES = set(SettlementItem.Status.values)
BATCH_STATUSES = set(SettlementBatch.Status.values)


def _parse_date(value, field_name):
    parsed = parse_date(value)
    if parsed is None:
        raise ApiError("VALIDATION_ERROR", f"{field_name} 日期格式错误", 422)
    return parsed


@extend_schema(tags=["merchant"], request=WithdrawalInputSerializer, responses=EnvelopeResponse)
class MerchantWithdrawalCreateView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = WithdrawalInputSerializer

    def post(self, request):
        idempotency_key = request.headers.get("Idempotency-Key", "").strip()
        if not idempotency_key:
            raise ApiError("VALIDATION_ERROR", "缺少 Idempotency-Key", 422)
        serializer = WithdrawalInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        withdrawal = request_withdrawal(
            request.user, idempotency_key=idempotency_key, request=request, **serializer.validated_data
        )
        return ok(request, WithdrawalSerializer(withdrawal).data, status_code=201)


@extend_schema(tags=["merchant"], responses=EnvelopeResponse)
class MerchantStatementListView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = StatementItemSerializer

    def get(self, request):
        merchant = get_active_staff_merchant(request.user)
        queryset = (
            SettlementItem.objects.filter(merchant=merchant)
            .select_related("order")
            .order_by("-order_completed_at", "-id")
        )
        status = request.query_params.get("status")
        if status:
            if status not in STATEMENT_STATUSES:
                raise ApiError("VALIDATION_ERROR", "status 取值非法", 422)
            queryset = queryset.filter(status=status)
        date_from = request.query_params.get("dateFrom")
        if date_from:
            queryset = queryset.filter(order_completed_at__date__gte=_parse_date(date_from, "dateFrom"))
        date_to = request.query_params.get("dateTo")
        if date_to:
            queryset = queryset.filter(order_completed_at__date__lte=_parse_date(date_to, "dateTo"))
        return ok(request, paginated(request, queryset, StatementItemSerializer))


@extend_schema(tags=["admin"], responses=EnvelopeResponse)
class AdminSettlementBatchListView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SettlementBatchSerializer

    def get(self, request):
        require_platform_admin(request.user)
        queryset = SettlementBatch.objects.annotate(items_count=Count("items")).order_by("-created_at")
        status = request.query_params.get("status")
        if status:
            if status not in BATCH_STATUSES:
                raise ApiError("VALIDATION_ERROR", "status 取值非法", 422)
            queryset = queryset.filter(status=status)
        return ok(request, paginated(request, queryset, SettlementBatchSerializer))


@extend_schema(tags=["admin"], responses=EnvelopeResponse)
class AdminSettlementPublishView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SettlementBatchSerializer

    def post(self, request, pk):
        batch = publish_settlement_batch(pk, request.user, request=request)
        batch = SettlementBatch.objects.annotate(items_count=Count("items")).get(pk=batch.pk)
        return ok(request, SettlementBatchSerializer(batch).data)


@extend_schema(tags=["admin"], responses=EnvelopeResponse)
class AdminWithdrawalPayoutView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PayoutInputSerializer

    def post(self, request, pk):
        serializer = PayoutInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        withdrawal = payout_withdrawal(request.user, pk, request=request, **serializer.validated_data)
        return ok(request, WithdrawalSerializer(withdrawal).data)


@extend_schema(tags=["admin"], request=RejectInputSerializer, responses=EnvelopeResponse)
class AdminWithdrawalRejectView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = RejectInputSerializer

    def post(self, request, pk):
        serializer = RejectInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        withdrawal = reject_withdrawal(request.user, pk, serializer.validated_data["reason"], request=request)
        return ok(request, WithdrawalSerializer(withdrawal).data)


@extend_schema(tags=["admin"], request=FreezeInputSerializer, responses=EnvelopeResponse)
class AdminOrderFreezeView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = FreezeInputSerializer

    def post(self, request, pk):
        idempotency_key = request.headers.get("Idempotency-Key", "").strip()
        if not idempotency_key:
            raise ApiError("VALIDATION_ERROR", "缺少 Idempotency-Key", 422)
        serializer = FreezeInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = set_order_settlement_freeze(
            request.user,
            pk,
            serializer.validated_data["action"],
            serializer.validated_data["reason"],
            idempotency_key,
            request=request,
        )
        return ok(request, {"order_id": item.order_id, "status": item.status})


@extend_schema(tags=["admin"], responses=EnvelopeResponse)
class AdminReconciliationView(EnvelopeAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = EnvelopeResponse

    def get(self, request):
        require_platform_admin(request.user)
        date_value = request.query_params.get("date")
        if not date_value:
            raise ApiError("VALIDATION_ERROR", "缺少 date 参数", 422)
        return ok(request, reconciliation_report(_parse_date(date_value, "date")))


@extend_schema(tags=["merchant"], responses=EnvelopeResponse)
class MerchantAccountSummaryView(EnvelopeAPIView):
    """商户虚拟账户余额概览。"""

    permission_classes = [IsAuthenticated]
    serializer_class = EnvelopeResponse

    def get(self, request):
        from .services import ensure_account

        merchant = get_active_staff_merchant(request.user)
        account = ensure_account(merchant.id)
        return ok(
            request,
            {
                "merchant_id": merchant.id,
                "pending_balance": account.pending_balance,
                "frozen_balance": account.frozen_balance,
                "available_balance": account.available_balance,
                "withdrawing_balance": account.withdrawing_balance,
            },
        )
