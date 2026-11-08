"""回填订单商品行分账与订单分账汇总。"""

from decimal import ROUND_HALF_UP, Decimal

from django.db import migrations


def allocate_amount(total, weights):
    if total <= 0 or not weights:
        return [0 for _ in weights]
    total_weight = sum(max(weight, 0) for weight in weights)
    if total_weight <= 0:
        return [0 for _ in weights]
    raw = [Decimal(total) * Decimal(max(weight, 0)) / Decimal(total_weight) for weight in weights]
    base = [int(value) for value in raw]
    remaining = total - sum(base)
    ranked = sorted(range(len(weights)), key=lambda index: (-(raw[index] - Decimal(base[index])), index))
    for index in ranked:
        if remaining <= 0:
            break
        base[index] += 1
        remaining -= 1
    return base


def backfill(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    SettlementItem = apps.get_model("ledger", "SettlementItem")

    for order in Order.objects.iterator():
        items = list(order.items.all().order_by("id"))
        rate = Decimal(order.commission_rate)
        if not items:
            order.platform_income_amount = order.commission_amount
            order.merchant_income_amount = order.product_amount - order.commission_amount + order.delivery_fee
            order.save(update_fields=["platform_income_amount", "merchant_income_amount"])
            continue

        amounts = [item.amount for item in items]
        platforms = allocate_amount(order.commission_amount, amounts)
        for item, platform_amount in zip(items, platforms):
            item.paid_amount = item.amount
            item.commission_rate = rate
            item.platform_amount = platform_amount
            item.merchant_amount = item.amount - platform_amount
            item.save(
                update_fields=[
                    "paid_amount",
                    "commission_rate",
                    "platform_amount",
                    "merchant_amount",
                ]
            )

        refunded = order.refunded_amount
        product_refund = min(refunded, order.product_amount)
        line_refunds = allocate_amount(product_refund, amounts)
        platform_total = int(
            (Decimal(product_refund) * rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        )
        line_platforms = allocate_amount(platform_total, line_refunds)
        for item, line_refund, platform_refund in zip(items, line_refunds, line_platforms):
            item.refund_amount = line_refund
            item.platform_refund_amount = platform_refund
            item.merchant_refund_amount = line_refund - platform_refund
            item.save(
                update_fields=[
                    "refund_amount",
                    "platform_refund_amount",
                    "merchant_refund_amount",
                ]
            )

        order.platform_refund_amount = platform_total
        order.merchant_refund_amount = refunded - platform_total
        order.platform_income_amount = order.commission_amount - platform_total
        order.merchant_income_amount = (
            order.product_amount
            - order.commission_amount
            + order.delivery_fee
            - order.merchant_refund_amount
        )
        order.save(
            update_fields=[
                "platform_refund_amount",
                "merchant_refund_amount",
                "platform_income_amount",
                "merchant_income_amount",
            ]
        )

        item = SettlementItem.objects.filter(order_id=order.id).first()
        if item is not None and item.status != "SETTLED":
            item.commission_amount = order.platform_income_amount
            item.refund_amount = order.refunded_amount
            item.net_amount = order.merchant_income_amount
            item.save(update_fields=["commission_amount", "refund_amount", "net_amount", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0004_order_merchant_income_amount_and_more"),
        ("ledger", "0003_withdrawalorder_idempotency_key"),
    ]

    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
