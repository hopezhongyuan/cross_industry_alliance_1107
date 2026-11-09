"""商户商品发布、编辑与上下架服务。"""

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.common.api import ApiError
from apps.governance.media_services import ensure_media_url
from apps.governance.models import AuditTask, MediaAsset
from apps.governance.services import log_operation, require_platform_admin
from apps.merchants.services import get_merchant_manager

from .models import MerchantProductCategory, Product, ProductSku

PRODUCT_EDITABLE_STATUSES = {
    Product.Status.DRAFT,
    Product.Status.ON_SALE,
    Product.Status.OFF_SALE,
    Product.Status.REJECTED,
}


def _create_audit_task(product: Product) -> AuditTask:
    return AuditTask.objects.create(
        biz_type=AuditTask.BizType.PRODUCT,
        biz_id=product.id,
        status=AuditTask.Status.PENDING,
    )


def _sync_skus(product: Product, items: list) -> None:
    existing = {sku.sku_code: sku for sku in product.skus.select_for_update()}
    incoming = {item["sku_code"] for item in items}
    for item in items:
        sku = existing.get(item["sku_code"])
        if sku is None:
            ProductSku.objects.create(
                product=product,
                sku_code=item["sku_code"],
                spec_json=item.get("spec") or {},
                price=item["price_amount"],
                stock=item["stock"],
            )
            continue
        sku.spec_json = item.get("spec") or {}
        sku.price = item["price_amount"]
        sku.stock = item["stock"]
        sku.version += 1
        sku.save(update_fields=["spec_json", "price", "stock", "version", "updated_at"])

    from apps.orders.models import CartItem, OrderItem

    for code, sku in existing.items():
        if code in incoming:
            continue
        if OrderItem.objects.filter(sku=sku).exists() or CartItem.objects.filter(sku=sku).exists():
            raise ApiError("PRODUCT_STATE_CONFLICT", f"规格 {code} 已被订单或购物车引用，不能删除", 409)
        sku.delete()


def _merchant_category(merchant, category_id):
    if category_id is None:
        return None
    category = MerchantProductCategory.objects.filter(pk=category_id, merchant=merchant).first()
    if category is None:
        raise ApiError("VALIDATION_ERROR", "商户分类不存在或不属于当前商户", 422)
    return category


def _ensure_product_code_unique(merchant, code: str, exclude_id=None):
    if not code:
        return
    queryset = Product.objects.filter(merchant=merchant, product_code=code)
    if exclude_id is not None:
        queryset = queryset.exclude(pk=exclude_id)
    if queryset.exists():
        raise ApiError("PRODUCT_STATE_CONFLICT", f"商品编码 {code} 已存在", 409)


def _product_fields(data: dict, merchant_category=None) -> dict:
    return {
        "category": data["category"],
        "merchant_category": merchant_category,
        "product_code": data.get("product_code", ""),
        "type": data["type"],
        "title": data["title"],
        "subtitle": data.get("subtitle", ""),
        "cover_url": data.get("cover_url", ""),
        "images": data.get("images", []),
        "description": data.get("description", ""),
        "price": data["price_amount"],
        "original_price": data.get("original_price_amount", 0),
        "verify_days": data.get("verify_days", 30),
        "appointment_required": data.get("appointment_required", False),
        "delivery_types": data["delivery_types"],
    }


def create_merchant_category(user, data: dict, request=None):
    merchant = get_merchant_manager(user)
    name = data["name"].strip()
    if MerchantProductCategory.objects.filter(merchant=merchant, name=name).exists():
        raise ApiError("VALIDATION_ERROR", "分类名称已存在", 422)
    category = MerchantProductCategory.objects.create(
        merchant=merchant,
        name=name,
        sort=data.get("sort", 0),
        status=data.get("status", MerchantProductCategory.Status.ENABLED),
    )
    log_operation(
        operator=user,
        action="MERCHANT_CATEGORY_CREATE",
        biz_type="MERCHANT_PRODUCT_CATEGORY",
        biz_id=category.id,
        after={"name": category.name},
        request=request,
    )
    return category


def update_merchant_category(user, category_id: int, data: dict, request=None):
    merchant = get_merchant_manager(user)
    name = data["name"].strip()
    with transaction.atomic():
        category = MerchantProductCategory.objects.select_for_update().filter(pk=category_id, merchant=merchant).first()
        if category is None:
            raise ApiError("NOT_FOUND", "分类不存在", 404)
        if MerchantProductCategory.objects.filter(merchant=merchant, name=name).exclude(pk=category.pk).exists():
            raise ApiError("VALIDATION_ERROR", "分类名称已存在", 422)
        category.name = name
        category.sort = data.get("sort", category.sort)
        category.status = data.get("status", category.status)
        category.save(update_fields=["name", "sort", "status", "updated_at"])
    log_operation(
        operator=user,
        action="MERCHANT_CATEGORY_UPDATE",
        biz_type="MERCHANT_PRODUCT_CATEGORY",
        biz_id=category.id,
        after={"name": category.name, "status": category.status},
        request=request,
    )
    return category


def delete_merchant_category(user, category_id: int, request=None):
    merchant = get_merchant_manager(user)
    with transaction.atomic():
        category = MerchantProductCategory.objects.select_for_update().filter(pk=category_id, merchant=merchant).first()
        if category is None:
            raise ApiError("NOT_FOUND", "分类不存在", 404)
        if category.products.exists():
            raise ApiError("PRODUCT_STATE_CONFLICT", "分类下仍有商品，不能删除", 409)
        log_operation(
            operator=user,
            action="MERCHANT_CATEGORY_DELETE",
            biz_type="MERCHANT_PRODUCT_CATEGORY",
            biz_id=category.id,
            before={"name": category.name},
            request=request,
        )
        category.delete()


def create_merchant_product(user, data: dict, idempotency_key: str, request=None):
    """商户发布商品：创建商品与 SKU，同时生成审核任务。"""
    merchant = get_merchant_manager(user)
    if not idempotency_key:
        raise ApiError("VALIDATION_ERROR", "缺少 Idempotency-Key", 422)
    existing = Product.objects.filter(create_idempotency_key=idempotency_key).first()
    if existing is not None:
        return existing, False
    try:
        with transaction.atomic():
            merchant_category = _merchant_category(merchant, data.get("merchant_category_id"))
            _ensure_product_code_unique(merchant, data.get("product_code", ""))
            product = Product.objects.create(
                merchant=merchant,
                status=Product.Status.PENDING_AUDIT,
                submitted_at=timezone.now(),
                create_idempotency_key=idempotency_key,
                **_product_fields(data, merchant_category),
            )
            _sync_skus(product, data["skus"])
            audit_task = _create_audit_task(product)
            log_operation(
                operator=user,
                action="PRODUCT_SUBMIT",
                biz_type="PRODUCT",
                biz_id=product.id,
                after={"title": product.title, "audit_task_id": audit_task.id, "sku_count": len(data["skus"])},
                request=request,
            )
    except IntegrityError:
        existing = Product.objects.filter(create_idempotency_key=idempotency_key).first()
        if existing is not None:
            return existing, False
        raise
    return product, True


def update_merchant_product(user, product_id: int, data: dict, request=None):
    """商户编辑商品；价格/主图/类目变更或驳回后编辑会重新进入审核。"""
    merchant = get_merchant_manager(user)
    version = data.get("version")
    if version is None:
        raise ApiError("VALIDATION_ERROR", "缺少 version", 422)
    with transaction.atomic():
        product = Product.objects.select_for_update().filter(pk=product_id, merchant=merchant).first()
        if product is None:
            raise ApiError("NOT_FOUND", "商品不存在", 404)
        if product.status not in PRODUCT_EDITABLE_STATUSES:
            raise ApiError("PRODUCT_STATE_CONFLICT", f"商品处于 {product.status}，暂不可编辑", 409)
        if version != product.version:
            raise ApiError("PRODUCT_STATE_CONFLICT", "商品已被其他操作修改，请刷新后重试", 409)

        merchant_category = _merchant_category(merchant, data.get("merchant_category_id"))
        _ensure_product_code_unique(merchant, data.get("product_code", ""), exclude_id=product.id)

        significant = (
            data["price_amount"] != product.price
            or data.get("cover_url", "") != product.cover_url
            or data["category"].id != product.category_id
        )
        needs_audit = product.status == Product.Status.REJECTED or significant

        for field, value in _product_fields(data, merchant_category).items():
            setattr(product, field, value)
        _sync_skus(product, data["skus"])

        product.version += 1
        if needs_audit:
            product.status = Product.Status.PENDING_AUDIT
            product.submitted_at = timezone.now()
            product.audited_at = None
            product.reject_reason = ""
            audit_task = _create_audit_task(product)
            audit_task_id = audit_task.id
        else:
            audit_task_id = None
        product.save()
    log_operation(
        operator=user,
        action="PRODUCT_UPDATE",
        biz_type="PRODUCT",
        biz_id=product.id,
        after={
            "status": product.status,
            "version": product.version,
            "reaudit": needs_audit,
            "audit_task_id": audit_task_id,
        },
        request=request,
    )
    return product


def set_product_sale_status(user, product_id: int, target: str, request=None):
    """上架/下架：ON_SALE ↔ OFF_SALE，均已审核通过的商品可直接切换。"""
    merchant = get_merchant_manager(user)
    if target not in (Product.Status.ON_SALE, Product.Status.OFF_SALE):
        raise ApiError("VALIDATION_ERROR", "status 取值非法", 422)
    with transaction.atomic():
        product = Product.objects.select_for_update().filter(pk=product_id, merchant=merchant).first()
        if product is None:
            raise ApiError("NOT_FOUND", "商品不存在", 404)
        allowed = {
            Product.Status.ON_SALE: Product.Status.OFF_SALE,
            Product.Status.OFF_SALE: Product.Status.ON_SALE,
        }
        if allowed.get(product.status) != target:
            raise ApiError("PRODUCT_STATE_CONFLICT", f"商品处于 {product.status}，不接受该操作", 409)
        if target == Product.Status.ON_SALE and product.off_sale_by == "PLATFORM":
            raise ApiError("PRODUCT_STATE_CONFLICT", "商品已被平台下架，暂不能重新上架", 409)
        product.status = target
        if target == Product.Status.OFF_SALE:
            product.off_sale_by = "MERCHANT"
            product.off_sale_reason = ""
            product.off_sale_at = timezone.now()
        else:
            product.off_sale_by = ""
            product.off_sale_reason = ""
            product.off_sale_at = None
        product.version += 1
        product.save(
            update_fields=[
                "status",
                "off_sale_by",
                "off_sale_reason",
                "off_sale_at",
                "version",
                "updated_at",
            ]
        )
    log_operation(
        operator=user,
        action="PRODUCT_OFF_SALE" if target == Product.Status.OFF_SALE else "PRODUCT_ON_SALE",
        biz_type="PRODUCT",
        biz_id=product.id,
        after={"status": target, "version": product.version},
        request=request,
    )
    return product


def admin_update_product(admin_user, product_id: int, data: dict, request=None):
    """平台编辑商户商品：直接生效，不重新进入审核。"""
    require_platform_admin(admin_user)
    with transaction.atomic():
        product = Product.objects.select_for_update().filter(pk=product_id).select_related("merchant_category").first()
        if product is None:
            raise ApiError("NOT_FOUND", "商品不存在", 404)
        new_cover = data.get("cover_url", "")
        if new_cover and new_cover != product.cover_url:
            ensure_media_url(new_cover, kinds=(MediaAsset.Kind.IMAGE,))
        for url in data.get("images", []) or []:
            if url not in (product.images or []):
                ensure_media_url(url, kinds=(MediaAsset.Kind.IMAGE,))
        fields = _product_fields(data, product.merchant_category)
        for field, value in fields.items():
            setattr(product, field, value)
        _sync_skus(product, data["skus"])
        product.version += 1
        product.save()
    log_operation(
        operator=admin_user,
        action="PRODUCT_ADMIN_UPDATE",
        biz_type="PRODUCT",
        biz_id=product.id,
        after={"status": product.status, "version": product.version},
        request=request,
    )
    return product


def admin_set_product_status(admin_user, product_id: int, action: str, reason: str, request=None):
    """平台违规下架 / 恢复上架。"""
    require_platform_admin(admin_user)
    with transaction.atomic():
        product = Product.objects.select_for_update().filter(pk=product_id).first()
        if product is None:
            raise ApiError("NOT_FOUND", "商品不存在", 404)
        if action == "FORCE_OFF":
            if product.status != Product.Status.ON_SALE:
                raise ApiError("PRODUCT_STATE_CONFLICT", "仅在售商品可以强制下架", 409)
            if not reason.strip():
                raise ApiError("VALIDATION_ERROR", "强制下架必须填写原因", 422)
            product.status = Product.Status.OFF_SALE
            product.off_sale_by = "PLATFORM"
            product.off_sale_reason = reason.strip()
            product.off_sale_at = timezone.now()
        elif action == "RESTORE":
            if product.status != Product.Status.OFF_SALE or product.off_sale_by != "PLATFORM":
                raise ApiError("PRODUCT_STATE_CONFLICT", "仅平台下架的商品可以恢复", 409)
            product.status = Product.Status.ON_SALE
            product.off_sale_by = ""
            product.off_sale_reason = ""
            product.off_sale_at = None
        else:
            raise ApiError("VALIDATION_ERROR", "action 取值非法", 422)
        product.version += 1
        product.save(
            update_fields=[
                "status",
                "off_sale_by",
                "off_sale_reason",
                "off_sale_at",
                "version",
                "updated_at",
            ]
        )
    log_operation(
        operator=admin_user,
        action="PRODUCT_FORCE_OFF" if action == "FORCE_OFF" else "PRODUCT_RESTORE",
        biz_type="PRODUCT",
        biz_id=product.id,
        before={"status": "ON_SALE" if action == "FORCE_OFF" else "OFF_SALE"},
        after={"status": product.status},
        reason=reason,
        request=request,
    )
    return product


def admin_batch_set_product_status(admin_user, product_ids, action: str, reason: str, request=None):
    """批量强制下架 / 恢复：逐条处理，返回每条结果，不做全量回滚。"""
    require_platform_admin(admin_user)
    results = []
    for product_id in product_ids:
        try:
            product = admin_set_product_status(admin_user, product_id, action, reason, request=request)
            results.append(
                {
                    "id": product_id,
                    "ok": True,
                    "status": product.status,
                    "off_sale_by": product.off_sale_by,
                    "error_code": "",
                    "error_message": "",
                }
            )
        except ApiError as exc:
            results.append(
                {
                    "id": product_id,
                    "ok": False,
                    "status": "",
                    "off_sale_by": "",
                    "error_code": exc.code,
                    "error_message": exc.message,
                }
            )
    return results
