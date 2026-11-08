"""平台商城装修：底部导航、微页面与组件校验。"""

import re

from django.db import transaction
from django.utils import timezone

from apps.common.api import ApiError

from .media_services import ensure_media_url
from .models import DecoPage, MediaAsset, StoreNavItem
from .services import log_operation, require_platform_admin

FUNCTION_PAGES = {
    "HOME",
    "CATEGORY",
    "CART",
    "ORDERS",
    "ME",
    "SEARCH",
    "MERCHANT_LIST",
}
LINK_TYPES = set(StoreNavItem.LinkType.values)
COMPONENT_TYPES = {
    "AD",
    "CAROUSEL",
    "IMAGE_HOTSPOT",
    "PRODUCT",
    "SEARCH",
    "LOCATION",
    "DIVIDER",
    "LINK",
}
SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,39}$")
COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")


def _image(url, required=False):
    if not url:
        if required:
            raise ApiError("VALIDATION_ERROR", "图片不能为空", 422)
        return ""
    return ensure_media_url(url, kinds=(MediaAsset.Kind.IMAGE,))


def validate_link(link_type, link_value=""):
    """校验内部链接目标，禁止任意外部 URL。"""
    if link_type not in LINK_TYPES:
        raise ApiError("VALIDATION_ERROR", "链接类型非法", 422)
    value = str(link_value or "").strip()
    if link_type == StoreNavItem.LinkType.FUNCTION:
        if value not in FUNCTION_PAGES:
            raise ApiError("VALIDATION_ERROR", "功能页面取值非法", 422)
        return value
    if not value:
        raise ApiError("VALIDATION_ERROR", "链接目标不能为空", 422)

    if link_type == StoreNavItem.LinkType.MICRO_PAGE:
        if not DecoPage.objects.filter(slug=value).exists():
            raise ApiError("VALIDATION_ERROR", "微页面不存在", 422)
        return value
    try:
        target_id = int(value)
    except ValueError:
        raise ApiError("VALIDATION_ERROR", "链接目标必须为数字 ID", 422) from None

    if link_type == StoreNavItem.LinkType.CATEGORY:
        from apps.catalog.models import Category

        if not Category.objects.filter(pk=target_id).exists():
            raise ApiError("VALIDATION_ERROR", "类目不存在", 422)
    elif link_type == StoreNavItem.LinkType.MERCHANT:
        from apps.merchants.models import Merchant

        if not Merchant.objects.filter(pk=target_id).exists():
            raise ApiError("VALIDATION_ERROR", "商户不存在", 422)
    elif link_type == StoreNavItem.LinkType.PRODUCT:
        from apps.catalog.models import Product

        if not Product.objects.filter(pk=target_id).exists():
            raise ApiError("VALIDATION_ERROR", "商品不存在", 422)
    else:
        raise ApiError("VALIDATION_ERROR", "链接类型非法", 422)
    return str(target_id)


def _validate_component_link(config):
    link = config.get("link") or {}
    if not link:
        return
    link_type = link.get("type")
    link_value = link.get("value", "")
    validate_link(link_type, link_value)


def _validate_color(value, field):
    if value and not COLOR_PATTERN.match(str(value)):
        raise ApiError("VALIDATION_ERROR", f"{field} 需为 #RRGGBB", 422)


def _validate_component(component_type, config):
    if component_type == "AD":
        _image(config.get("image"), required=True)
        _validate_component_link(config)
        height = int(config.get("height", 180))
        if not 80 <= height <= 600:
            raise ApiError("VALIDATION_ERROR", "广告高度需在 80–600", 422)
    elif component_type == "CAROUSEL":
        images = config.get("images") or []
        if not images or len(images) > 8:
            raise ApiError("VALIDATION_ERROR", "轮播图需 1–8 张", 422)
        for item in images:
            _image(item.get("image"), required=True)
            _validate_component_link(item)
        interval = int(config.get("interval", 4))
        if not 2 <= interval <= 10:
            raise ApiError("VALIDATION_ERROR", "轮播间隔需在 2–10 秒", 422)
    elif component_type == "IMAGE_HOTSPOT":
        _image(config.get("image"), required=True)
        hotspots = config.get("hotspots") or []
        if len(hotspots) > 10:
            raise ApiError("VALIDATION_ERROR", "热区最多 10 个", 422)
        for hotspot in hotspots:
            try:
                x = float(hotspot.get("x", 0))
                y = float(hotspot.get("y", 0))
                width = float(hotspot.get("w", 0))
                height = float(hotspot.get("h", 0))
            except (TypeError, ValueError):
                raise ApiError("VALIDATION_ERROR", "热区坐标格式错误", 422) from None
            if min(x, y, width, height) < 0 or x + width > 100 or y + height > 100:
                raise ApiError("VALIDATION_ERROR", "热区需在图片范围内（百分比）", 422)
            _validate_component_link(hotspot)
    elif component_type == "PRODUCT":
        source = config.get("source", "MANUAL")
        if source not in {"MANUAL", "CATEGORY", "MERCHANT"}:
            raise ApiError("VALIDATION_ERROR", "商品来源非法", 422)
        if source == "MANUAL":
            from apps.catalog.models import Product

            ids = config.get("product_ids") or []
            if not ids:
                raise ApiError("VALIDATION_ERROR", "请选择商品", 422)
            if not Product.objects.filter(pk__in=ids).count() == len(set(ids)):
                raise ApiError("VALIDATION_ERROR", "商品不存在", 422)
        elif source == "CATEGORY":
            from apps.catalog.models import Category

            if not Category.objects.filter(pk=config.get("category_id")).exists():
                raise ApiError("VALIDATION_ERROR", "类目不存在", 422)
        else:
            from apps.merchants.models import Merchant

            if not Merchant.objects.filter(pk=config.get("merchant_id")).exists():
                raise ApiError("VALIDATION_ERROR", "商户不存在", 422)
        if config.get("layout", "GRID") not in {"GRID", "LIST"}:
            raise ApiError("VALIDATION_ERROR", "商品布局非法", 422)
        if int(config.get("columns", 2)) not in {2, 3}:
            raise ApiError("VALIDATION_ERROR", "商品列数需为 2 或 3", 422)
        if not 1 <= int(config.get("limit", 6)) <= 20:
            raise ApiError("VALIDATION_ERROR", "商品数量需在 1–20", 422)
    elif component_type == "SEARCH":
        if len(config.get("hot_keywords") or []) > 8:
            raise ApiError("VALIDATION_ERROR", "热搜词最多 8 个", 422)
        if config.get("style", "DEFAULT") not in {"DEFAULT", "COMPACT"}:
            raise ApiError("VALIDATION_ERROR", "搜索框样式非法", 422)
    elif component_type == "LOCATION":
        radius = int(config.get("radius", 3000))
        if not 500 <= radius <= 10000:
            raise ApiError("VALIDATION_ERROR", "定位半径需在 500–10000 米", 422)
    elif component_type == "DIVIDER":
        if config.get("style", "LINE") not in {"LINE", "BLANK"}:
            raise ApiError("VALIDATION_ERROR", "辅助线样式非法", 422)
        _validate_color(config.get("color"), "辅助线颜色")
        _validate_color(config.get("background"), "辅助线背景")
        if not 1 <= int(config.get("height", 1)) <= 80:
            raise ApiError("VALIDATION_ERROR", "辅助线高度需在 1–80", 422)
    elif component_type == "LINK":
        if config.get("layout", "CARD") not in {"CARD", "TEXT"}:
            raise ApiError("VALIDATION_ERROR", "链接样式非法", 422)
        _validate_component_link(config)
        if not (config.get("link") or {}).get("type"):
            raise ApiError("VALIDATION_ERROR", "链接组件必须配置跳转", 422)
        if config.get("image"):
            _image(config["image"])
    else:
        raise ApiError("VALIDATION_ERROR", "组件类型非法", 422)


def validate_components(components):
    if not isinstance(components, list):
        raise ApiError("VALIDATION_ERROR", "components 需为数组", 422)
    if len(components) > 40:
        raise ApiError("VALIDATION_ERROR", "组件最多 40 个", 422)
    normalized = []
    for index, component in enumerate(components):
        if not isinstance(component, dict):
            raise ApiError("VALIDATION_ERROR", "组件格式错误", 422)
        component_type = component.get("type")
        if component_type not in COMPONENT_TYPES:
            raise ApiError("VALIDATION_ERROR", "组件类型非法", 422)
        config = component.get("config") or {}
        if not isinstance(config, dict):
            raise ApiError("VALIDATION_ERROR", "组件配置需为对象", 422)
        _validate_component(component_type, config)
        normalized.append(
            {
                "id": component.get("id") or f"c{index + 1}",
                "type": component_type,
                "config": config,
            }
        )
    return normalized


def replace_nav_items(admin_user, items, request=None):
    require_platform_admin(admin_user)
    if not isinstance(items, list):
        raise ApiError("VALIDATION_ERROR", "items 需为数组", 422)
    if not 1 <= len(items) <= 5:
        raise ApiError("VALIDATION_ERROR", "底部导航需 1–5 项", 422)
    normalized = []
    for item in items:
        title = str(item.get("title", "")).strip()
        if not title:
            raise ApiError("VALIDATION_ERROR", "导航名称不能为空", 422)
        _image(item.get("icon_selected"))
        _image(item.get("icon_unselected"))
        link_value = validate_link(item.get("link_type"), item.get("link_value"))
        normalized.append(
            {
                "title": title,
                "icon_selected": item.get("icon_selected", ""),
                "icon_unselected": item.get("icon_unselected", ""),
                "link_type": item.get("link_type"),
                "link_value": link_value,
                "status": item.get("status", StoreNavItem.Status.ENABLED),
            }
        )

    with transaction.atomic():
        StoreNavItem.objects.all().delete()
        for index, item in enumerate(normalized):
            StoreNavItem.objects.create(
                sort=index,
                updated_by_name=getattr(admin_user, "nickname", "") or getattr(admin_user, "phone", ""),
                **item,
            )
        log_operation(
            operator=admin_user,
            action="STOREFRONT_NAV_UPDATE",
            biz_type="STOREFRONT_NAV",
            after={"count": len(normalized)},
            request=request,
        )
    return list(StoreNavItem.objects.all())


def create_page(admin_user, data, request=None):
    require_platform_admin(admin_user)
    slug = str(data["slug"]).strip()
    if not SLUG_PATTERN.match(slug):
        raise ApiError("VALIDATION_ERROR", "slug 需为 2–40 位小写字母、数字或连字符", 422)
    if DecoPage.objects.filter(slug=slug).exists():
        raise ApiError("VALIDATION_ERROR", "slug 已存在", 422)
    share_image = _image(data.get("share_image", ""))
    components = validate_components(data.get("draft_components", []))
    page = DecoPage.objects.create(
        slug=slug,
        title=data["title"],
        share_title=data.get("share_title", ""),
        share_image=share_image,
        draft_components=components,
        updated_by_name=getattr(admin_user, "nickname", "") or getattr(admin_user, "phone", ""),
    )
    log_operation(
        operator=admin_user,
        action="DECO_PAGE_CREATE",
        biz_type="DECO_PAGE",
        biz_id=page.id,
        after={"slug": page.slug, "components": len(components)},
        request=request,
    )
    return page


def update_page(admin_user, page_id, data, request=None):
    require_platform_admin(admin_user)
    with transaction.atomic():
        page = DecoPage.objects.select_for_update().filter(pk=page_id).first()
        if page is None:
            raise ApiError("NOT_FOUND", "微页面不存在", 404)
        slug = str(data["slug"]).strip()
        if not SLUG_PATTERN.match(slug):
            raise ApiError("VALIDATION_ERROR", "slug 需为 2–40 位小写字母、数字或连字符", 422)
        if DecoPage.objects.filter(slug=slug).exclude(pk=page.pk).exists():
            raise ApiError("VALIDATION_ERROR", "slug 已存在", 422)
        share_image = _image(data.get("share_image", ""))
        components = validate_components(data.get("draft_components", []))
        page.slug = slug
        page.title = data["title"]
        page.share_title = data.get("share_title", "")
        page.share_image = share_image
        page.draft_components = components
        page.updated_by_name = getattr(admin_user, "nickname", "") or getattr(admin_user, "phone", "")
        page.save()
    log_operation(
        operator=admin_user,
        action="DECO_PAGE_UPDATE",
        biz_type="DECO_PAGE",
        biz_id=page.id,
        after={"slug": page.slug, "components": len(components)},
        request=request,
    )
    return page


def publish_page(admin_user, page_id, request=None):
    require_platform_admin(admin_user)
    with transaction.atomic():
        page = DecoPage.objects.select_for_update().filter(pk=page_id).first()
        if page is None:
            raise ApiError("NOT_FOUND", "微页面不存在", 404)
        components = validate_components(page.draft_components)
        if not components:
            raise ApiError("VALIDATION_ERROR", "至少配置一个组件后才能发布", 422)
        page.published_components = components
        page.status = DecoPage.Status.PUBLISHED
        page.published_at = timezone.now()
        page.updated_by_name = getattr(admin_user, "nickname", "") or getattr(admin_user, "phone", "")
        page.save(update_fields=["published_components", "status", "published_at", "updated_by_name", "updated_at"])
    log_operation(
        operator=admin_user,
        action="DECO_PAGE_PUBLISH",
        biz_type="DECO_PAGE",
        biz_id=page.id,
        after={"slug": page.slug, "components": len(components)},
        request=request,
    )
    return page


def delete_page(admin_user, page_id, request=None):
    require_platform_admin(admin_user)
    page = DecoPage.objects.filter(pk=page_id).first()
    if page is None:
        raise ApiError("NOT_FOUND", "微页面不存在", 404)
    if StoreNavItem.objects.filter(link_type=StoreNavItem.LinkType.MICRO_PAGE, link_value=page.slug).exists():
        raise ApiError("VALIDATION_ERROR", "页面被底部导航引用，不能删除", 409)
    page.delete()
    log_operation(
        operator=admin_user,
        action="DECO_PAGE_DELETE",
        biz_type="DECO_PAGE",
        biz_id=page_id,
        before={"slug": page.slug},
        request=request,
    )


def public_nav():
    return StoreNavItem.objects.filter(status=StoreNavItem.Status.ENABLED).order_by("sort", "id")


def public_page(slug):
    return DecoPage.objects.filter(slug=slug, status=DecoPage.Status.PUBLISHED).first()
