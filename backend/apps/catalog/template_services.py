"""平台商品模板：发布、分发、认领与同步。"""

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.common.api import ApiError
from apps.governance.media_services import ensure_media_url
from apps.governance.models import MediaAsset
from apps.governance.services import log_operation
from apps.merchants.models import Merchant
from apps.merchants.services import get_merchant_manager

from .merchant_services import _sync_skus
from .models import Product, ProductTemplate, TemplateAdoption


def visible_templates(merchant):
    return (
        ProductTemplate.objects.filter(status=ProductTemplate.Status.PUBLISHED)
        .filter(Q(scope=ProductTemplate.Scope.ALL) | Q(scope=ProductTemplate.Scope.SELECTED, target_merchants=merchant))
        .distinct()
    )


def _validate_media(data):
    if data.get("cover_url"):
        ensure_media_url(data["cover_url"], kinds=(MediaAsset.Kind.IMAGE,))
    for url in data.get("images", []) or []:
        ensure_media_url(url, kinds=(MediaAsset.Kind.IMAGE,))


def _template_fields(data):
    return {
        "title": data["title"],
        "subtitle": data.get("subtitle", ""),
        "type": data["type"],
        "category": data.get("category"),
        "cover_url": data.get("cover_url", ""),
        "images": data.get("images", []),
        "description": data.get("description", ""),
        "price": data.get("price_amount", 0),
        "original_price": data.get("original_price_amount", 0),
        "verify_days": data.get("verify_days", 30),
        "appointment_required": data.get("appointment_required", False),
        "delivery_types": data.get("delivery_types", []),
        "skus": data.get("skus", []),
    }


def create_template(admin_user, data, request=None):
    from apps.governance.services import require_platform_admin

    require_platform_admin(admin_user)
    if data.get("category") and data["category"].children.exists():
        raise ApiError("VALIDATION_ERROR", "请选择二级类目", 422)
    _validate_media(data)
    with transaction.atomic():
        template = ProductTemplate.objects.create(
            status=data.get("status", ProductTemplate.Status.DRAFT),
            scope=data.get("scope", ProductTemplate.Scope.NONE),
            published_at=timezone.now() if data.get("status") == ProductTemplate.Status.PUBLISHED else None,
            created_by_name=getattr(admin_user, "nickname", "") or getattr(admin_user, "phone", ""),
            **_template_fields(data),
        )
        merchant_ids = data.get("merchant_ids") or []
        if merchant_ids:
            template.target_merchants.set(Merchant.objects.filter(pk__in=merchant_ids))
        log_operation(
            operator=admin_user,
            action="PRODUCT_TEMPLATE_CREATE",
            biz_type="PRODUCT_TEMPLATE",
            biz_id=template.id,
            after={"template_no": template.template_no, "scope": template.scope},
            request=request,
        )
    return template


def update_template(admin_user, template_id, data, request=None):
    from apps.governance.services import require_platform_admin

    require_platform_admin(admin_user)
    if data.get("category") and data["category"].children.exists():
        raise ApiError("VALIDATION_ERROR", "请选择二级类目", 422)
    _validate_media(data)
    with transaction.atomic():
        template = ProductTemplate.objects.select_for_update().filter(pk=template_id).first()
        if template is None:
            raise ApiError("NOT_FOUND", "模板不存在", 404)
        for field, value in _template_fields(data).items():
            setattr(template, field, value)
        template.status = data.get("status", template.status)
        template.scope = data.get("scope", template.scope)
        template.published_at = (
            template.published_at or timezone.now()
            if template.status == ProductTemplate.Status.PUBLISHED
            else template.published_at
        )
        template.save()
        merchant_ids = data.get("merchant_ids")
        if merchant_ids is not None:
            template.target_merchants.set(Merchant.objects.filter(pk__in=merchant_ids))
        log_operation(
            operator=admin_user,
            action="PRODUCT_TEMPLATE_UPDATE",
            biz_type="PRODUCT_TEMPLATE",
            biz_id=template.id,
            after={"status": template.status, "scope": template.scope},
            request=request,
        )
    return template


def sync_template(admin_user, template_id, merchant_ids=None, request=None):
    """手动同步模板资料到已认领商品（按 SKU 编码增量更新）。"""
    from apps.governance.services import require_platform_admin

    require_platform_admin(admin_user)
    with transaction.atomic():
        template = ProductTemplate.objects.filter(pk=template_id).first()
        if template is None:
            raise ApiError("NOT_FOUND", "模板不存在", 404)
        adoptions = template.adoptions.select_related("product").filter(product__isnull=False)
        if merchant_ids:
            adoptions = adoptions.filter(merchant_id__in=merchant_ids)
        synced = 0
        for adoption in adoptions:
            product = adoption.product
            product.title = template.title
            product.subtitle = template.subtitle
            product.type = template.type
            product.category = template.category
            product.cover_url = template.cover_url
            product.images = template.images
            product.description = template.description
            product.price = template.price
            product.original_price = template.original_price
            product.verify_days = template.verify_days
            product.appointment_required = template.appointment_required
            product.delivery_types = template.delivery_types
            product.version += 1
            product.save()
            sku_items = [
                {
                    "sku_code": sku["sku_code"],
                    "spec": sku.get("spec") or {},
                    "price_amount": sku["price_amount"],
                    "stock": sku.get("stock", 0),
                }
                for sku in template.skus
            ]
            if sku_items:
                _sync_skus(product, sku_items)
            synced += 1
        log_operation(
            operator=admin_user,
            action="PRODUCT_TEMPLATE_SYNC",
            biz_type="PRODUCT_TEMPLATE",
            biz_id=template.id,
            after={"synced": synced},
            request=request,
        )
    return synced


def adopt_template(user, template_id, listed=True, request=None):
    merchant = get_merchant_manager(user)
    with transaction.atomic():
        template = visible_templates(merchant).filter(pk=template_id).first()
        if template is None:
            raise ApiError("NOT_FOUND", "模板不存在或未分发给你", 404)
        adoption = TemplateAdoption.objects.filter(template=template, merchant=merchant).first()
        if adoption and adoption.product:
            return adoption.product, False
        product = Product.objects.create(
            merchant=merchant,
            template=template,
            category=template.category,
            type=template.type,
            title=template.title,
            subtitle=template.subtitle,
            cover_url=template.cover_url,
            images=template.images,
            description=template.description,
            price=template.price,
            original_price=template.original_price,
            verify_days=template.verify_days,
            appointment_required=template.appointment_required,
            delivery_types=template.delivery_types,
            status=Product.Status.ON_SALE if listed else Product.Status.OFF_SALE,
            audited_at=timezone.now(),
        )
        for sku in template.skus:
            product.skus.create(
                sku_code=sku["sku_code"],
                spec_json=sku.get("spec") or {},
                price=sku["price_amount"],
                stock=sku.get("stock", 0),
            )
        TemplateAdoption.objects.update_or_create(
            template=template,
            merchant=merchant,
            defaults={"product": product},
        )
        log_operation(
            operator=user,
            action="PRODUCT_TEMPLATE_ADOPT",
            biz_type="PRODUCT",
            biz_id=product.id,
            after={"template_no": template.template_no, "listed": listed},
            request=request,
        )
    return product, True
