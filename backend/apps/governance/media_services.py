"""素材库：上传校验、引用检查与 URL 合法性。"""

import os

from django.conf import settings

from apps.common.api import ApiError

from .models import MediaAsset

IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}
VIDEO_EXTENSIONS = {"mp4", "webm", "mov", "m4v"}


def media_kind(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower().lstrip(".")
    if ext in IMAGE_EXTENSIONS:
        return MediaAsset.Kind.IMAGE
    if ext in VIDEO_EXTENSIONS:
        return MediaAsset.Kind.VIDEO
    raise ApiError("VALIDATION_ERROR", "仅支持 jpg/png/webp/gif 图片或 mp4/webm/mov 视频", 422)


def validate_upload(file) -> str:
    kind = media_kind(file.name)
    limit = settings.MEDIA_MAX_IMAGE_SIZE if kind == MediaAsset.Kind.IMAGE else settings.MEDIA_MAX_VIDEO_SIZE
    if file.size > limit:
        raise ApiError("VALIDATION_ERROR", f"文件超过大小限制（{limit // (1024 * 1024)}MB）", 422)
    return kind


def asset_url(asset: MediaAsset) -> str:
    return asset.file.url if asset.file else ""


def ensure_media_url(url: str, kinds=None) -> str:
    """业务字段只允许引用素材库中的文件，禁止外部 URL。"""
    if not url:
        return ""
    prefix = settings.MEDIA_URL
    if not url.startswith(prefix):
        raise ApiError("VALIDATION_ERROR", "请从素材库选择素材，不允许外部 URL", 422)
    name = url[len(prefix) :]
    asset = MediaAsset.objects.filter(file=name).first()
    if asset is None:
        raise ApiError("VALIDATION_ERROR", "素材不存在，请重新选择", 422)
    if kinds and asset.kind not in kinds:
        raise ApiError("VALIDATION_ERROR", "素材类型不匹配", 422)
    return url


def asset_reference_count(asset: MediaAsset) -> int:
    from apps.catalog.models import Category, Product, ProductTemplate
    from apps.governance.models import ContentItem
    from apps.ledger.models import WithdrawalOrder
    from apps.merchants.models import Merchant, MerchantQualification

    url = asset_url(asset)
    count = 0
    count += Product.objects.filter(cover_url=url).count()
    for images in Product.objects.exclude(images=None).values_list("images", flat=True):
        if url in (images or []):
            count += 1
    count += ProductTemplate.objects.filter(cover_url=url).count()
    for images in ProductTemplate.objects.exclude(images=None).values_list("images", flat=True):
        if url in (images or []):
            count += 1
    count += Category.objects.filter(icon_url=url).count()
    count += Merchant.objects.filter(logo_url=url).count()
    count += MerchantQualification.objects.filter(file_url=url).count()
    count += WithdrawalOrder.objects.filter(voucher_url=url).count()
    count += ContentItem.objects.filter(image_url=url).count()
    return count
