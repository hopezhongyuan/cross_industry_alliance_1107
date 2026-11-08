"""订单商品行分账与退款冲回。

金额全部为整数「分」。佣金只按商品实付计算，配送费 100% 归商家。
拆分采用最大余数法，保证各行合计与订单合计一致、无尾差。
"""

from decimal import ROUND_HALF_UP, Decimal
from typing import List, Optional

from apps.common.api import ApiError

from .models import OrderItem


def allocate_amount(total: int, weights: List[int], caps: Optional[List[int]] = None) -> List[int]:
    """按权重将整数金额分配到各行，返回与 weights 等长的列表。"""
    if total <= 0 or not weights:
        return [0 for _ in weights]
    total_weight = sum(max(weight, 0) for weight in weights)
    if total_weight <= 0:
        return [0 for _ in weights]

    raw = [Decimal(total) * Decimal(max(weight, 0)) / Decimal(total_weight) for weight in weights]
    base = [int(value) for value in raw]
    remaining = total - sum(base)
    ranked = sorted(
        range(len(weights)),
        key=lambda index: (-(raw[index] - Decimal(base[index])), index),
    )
    for index in ranked:
        if remaining <= 0:
            break
        if caps is not None and base[index] >= caps[index]:
            continue
        base[index] += 1
        remaining -= 1
    return base


def build_line_split(paid_amounts: List[int], rate) -> tuple:
    """返回（各行平台分账, 订单佣金合计）。"""
    total_paid = sum(paid_amounts)
    total_commission = int((Decimal(total_paid) * Decimal(rate)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    platforms = allocate_amount(total_commission, paid_amounts)
    return platforms, total_commission


def sync_order_income(order, save: bool = True) -> None:
    """按初始分账与累计退款重算订单当前平台/商家分账。"""
    order.platform_income_amount = order.commission_amount - order.platform_refund_amount
    order.merchant_income_amount = (
        order.product_amount - order.commission_amount + order.delivery_fee - order.merchant_refund_amount
    )
    if save:
        order.save(
            update_fields=[
                "platform_income_amount",
                "merchant_income_amount",
                "platform_refund_amount",
                "merchant_refund_amount",
                "refunded_amount",
                "updated_at",
            ]
        )


def apply_refund(order, amount: int, order_item=None, funding: str = "MERCHANT") -> dict:
    """将退款金额落到商品行，并冲回平台佣金与商家应得。

    - 指定 order_item 时只退该行，退款不得超过该行剩余实付。
    - 未指定行时按各行剩余实付等比例分摊；超出商品部分的金额视为配送费退款。
    - funding=PLATFORM 时平台承担全部退款，商家分账不变。
    """
    items = list(OrderItem.objects.select_for_update().filter(order=order).order_by("id"))
    if not items:
        raise ApiError("ORDER_ITEM_NOT_FOUND", "订单没有商品行", 409)

    remaining = {item.id: max(item.paid_amount - item.refund_amount, 0) for item in items}
    if order_item is not None:
        target = next((item for item in items if item.id == order_item.id), None)
        if target is None or target.order_id != order.id:
            raise ApiError("ORDER_ITEM_NOT_FOUND", "订单行不存在", 404)
        if amount > remaining[target.id]:
            raise ApiError(
                "REFUND_AMOUNT_EXCEEDED",
                "退款金额超过该行可退金额",
                409,
                {"refundable_amount": remaining[target.id]},
            )
        product_refund = amount
        line_refunds = [amount if item.id == target.id else 0 for item in items]
    else:
        product_remaining = sum(remaining.values())
        product_refund = min(amount, product_remaining)
        line_refunds = allocate_amount(
            product_refund,
            [remaining[item.id] for item in items],
            caps=[remaining[item.id] for item in items],
        )

    platform_line_total = 0
    if funding == "PLATFORM":
        platform_refunds = line_refunds
        merchant_refunds = [0 for _ in items]
        platform_borne = amount
        merchant_borne = 0
    else:
        already_platform = sum(item.platform_refund_amount for item in items)
        cumulative_product_refund = sum(item.refund_amount for item in items) + product_refund
        target_platform = int(
            (Decimal(cumulative_product_refund) * Decimal(order.commission_rate)).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )
        platform_line_total = max(target_platform - already_platform, 0)
        platform_refunds = allocate_amount(platform_line_total, line_refunds)
        merchant_refunds = [
            line_refund - platform_refund for line_refund, platform_refund in zip(line_refunds, platform_refunds)
        ]
        platform_borne = platform_line_total
        merchant_borne = amount - platform_borne

    for item, line_refund, platform_refund, merchant_refund in zip(
        items, line_refunds, platform_refunds, merchant_refunds
    ):
        if line_refund <= 0:
            continue
        item.refund_amount += line_refund
        item.platform_refund_amount += platform_refund
        item.merchant_refund_amount += merchant_refund
        item.save(
            update_fields=[
                "refund_amount",
                "platform_refund_amount",
                "merchant_refund_amount",
                "updated_at",
            ]
        )

    order.refunded_amount += amount
    order.platform_refund_amount += platform_borne
    order.merchant_refund_amount += merchant_borne
    sync_order_income(order)

    return {
        "product_refund": product_refund,
        "delivery_refund": amount - product_refund,
        "platform_refund": platform_borne,
        "merchant_refund": merchant_borne,
        "platform_line_total": platform_line_total,
    }
