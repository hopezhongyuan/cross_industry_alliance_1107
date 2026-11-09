"""购物车服务：支持跨商户，按商户分组展示。"""

from collections import defaultdict
from typing import Optional

from django.db import transaction

from apps.catalog.models import Product, ProductSku
from apps.common.api import ApiError

from .models import CartItem

MAX_QUANTITY = 99


def _get_product(product_id: int) -> Product:
    product = Product.objects.select_related("merchant").filter(pk=product_id, status=Product.Status.ON_SALE).first()
    if product is None:
        raise ApiError("PRODUCT_NOT_AVAILABLE", "商品不存在或已下架", 409)
    return product


def _get_sku(product: Product, sku_id: Optional[int]) -> Optional[ProductSku]:
    if sku_id is None:
        return None
    sku = ProductSku.objects.filter(pk=sku_id, product=product).first()
    if sku is None:
        raise ApiError("SKU_NOT_FOUND", "规格不存在或不属于该商品", 409)
    return sku


def _check_stock(sku: Optional[ProductSku], quantity: int) -> None:
    if sku is not None and sku.available_stock < quantity:
        raise ApiError(
            "STOCK_NOT_ENOUGH",
            f"库存不足，当前可售 {sku.available_stock}",
            409,
            {"available_stock": sku.available_stock},
        )


def add_cart_item(user, product_id: int, sku_id: Optional[int] = None, quantity: int = 1):
    product = _get_product(product_id)
    sku = _get_sku(product, sku_id)
    _check_stock(sku, quantity)

    with transaction.atomic():
        item = CartItem.objects.select_for_update().filter(user=user, product=product, sku=sku).first()
        if item is None:
            _check_stock(sku, quantity)
            return CartItem.objects.create(
                user=user, merchant=product.merchant, product=product, sku=sku, quantity=quantity
            )
        new_quantity = item.quantity + quantity
        if new_quantity > MAX_QUANTITY:
            raise ApiError("VALIDATION_ERROR", f"单规格数量上限 {MAX_QUANTITY}", 422)
        _check_stock(sku, new_quantity)
        item.quantity = new_quantity
        item.selected = True
        item.save(update_fields=["quantity", "selected", "updated_at"])
        return item


def update_cart_item(user, item_id: int, quantity=None, selected=None):
    item = CartItem.objects.filter(pk=item_id, user=user).select_related("sku").first()
    if item is None:
        raise ApiError("NOT_FOUND", "购物车项不存在", 404)
    if quantity is not None:
        _check_stock(item.sku, quantity)
        item.quantity = quantity
    if selected is not None:
        item.selected = selected
    item.save(update_fields=["quantity", "selected", "updated_at"])
    return item


def delete_cart_item(user, item_id: int) -> None:
    deleted, _ = CartItem.objects.filter(pk=item_id, user=user).delete()
    if not deleted:
        raise ApiError("NOT_FOUND", "购物车项不存在", 404)


def serialize_cart(user) -> dict:
    items = CartItem.objects.filter(user=user).select_related("product", "sku", "merchant").order_by("-created_at")
    groups_map = defaultdict(list)
    merchant_names = {}
    for item in items:
        groups_map[item.merchant_id].append(item)
        merchant_names[item.merchant_id] = item.merchant.name

    groups = []
    total_selected_count = 0
    total_selected_amount = 0
    for merchant_id, merchant_items in groups_map.items():
        selected_count = 0
        selected_amount = 0
        rows = []
        for item in merchant_items:
            price = item.sku.price if item.sku else item.product.price
            amount = price * item.quantity
            if item.selected:
                selected_count += item.quantity
                selected_amount += amount
            rows.append(
                {
                    "id": item.id,
                    "merchant_id": item.merchant_id,
                    "product_id": item.product_id,
                    "sku_id": item.sku_id,
                    "title": item.product.title,
                    "cover_url": item.product.cover_url,
                    "spec": item.sku.spec_json if item.sku else {},
                    "price_amount": price,
                    "quantity": item.quantity,
                    "selected": item.selected,
                    "available_stock": item.sku.available_stock if item.sku else None,
                }
            )
        groups.append(
            {
                "merchant_id": merchant_id,
                "merchant_name": merchant_names[merchant_id],
                "items": rows,
                "selected_count": selected_count,
                "selected_amount": selected_amount,
            }
        )
        total_selected_count += selected_count
        total_selected_amount += selected_amount

    return {
        "groups": groups,
        "total_selected_count": total_selected_count,
        "total_selected_amount": total_selected_amount,
    }
