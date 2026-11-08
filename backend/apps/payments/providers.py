"""微信支付适配层：M1 仅 Mock，真实 V3 联调在 M5。"""

from django.conf import settings

from apps.common.api import ApiError


def create_prepay(payment) -> dict:
    if settings.WECHAT_MOCK_MODE:
        return {
            "prepay_id": f"mock_{payment.payment_no}",
            "pay_params": {"mock": True},
        }
    raise ApiError("WECHAT_PAY_NOT_CONFIGURED", "真实微信支付未接入（M5）", 503)


def refund_payment(payment, refund_no: str, amount: int) -> str:
    if settings.WECHAT_MOCK_MODE:
        return f"mock_refund_{refund_no}"
    raise ApiError("WECHAT_REFUND_NOT_CONFIGURED", "真实微信退款未接入（M5）", 503)
