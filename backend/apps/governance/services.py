"""治理服务：平台权限校验、操作日志、规则版本发布与审核决定。"""

from django.db import models, transaction
from django.utils import timezone

from apps.common.api import ApiError
from apps.common.utils import generate_no

from .media_services import ensure_media_url
from .models import AuditTask, MediaAsset, OperationLog, PlatformConfig, PopupAd, RuleVersion


def require_platform_admin(user):
    if not (getattr(user, "is_staff", False) or getattr(user, "is_superuser", False)):
        raise ApiError("PERMISSION_DENIED", "需要平台管理员权限", 403)


def log_operation(
    *,
    operator,
    action,
    biz_type="",
    biz_id=None,
    before=None,
    after=None,
    reason="",
    request=None,
):
    """追加操作日志；日志不可修改、不可删除。"""
    ip = None
    user_agent = ""
    if request is not None:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        ip = (forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")) or None
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:200]
    payload = dict(after or {})
    if reason:
        payload["reason"] = reason
    return OperationLog.objects.create(
        operator_id=getattr(operator, "id", None),
        operator_name=getattr(operator, "nickname", "") or getattr(operator, "phone", "") or "",
        action=action,
        biz_type=biz_type,
        biz_id=biz_id,
        before_json=before or {},
        after_json=payload,
        ip=ip,
        user_agent=user_agent,
    )


def publish_rule_version(admin_user, snapshot, effective_at=None, remark=""):
    """发布规则版本：旧版本置为 RETIRED，新版本置为 ACTIVE。"""
    require_platform_admin(admin_user)
    with transaction.atomic():
        RuleVersion.objects.filter(status=RuleVersion.Status.ACTIVE).update(
            status=RuleVersion.Status.RETIRED, updated_at=timezone.now()
        )
        version = RuleVersion.objects.create(
            version_no=generate_no("RV"),
            snapshot_json=snapshot,
            status=RuleVersion.Status.ACTIVE,
            effective_at=effective_at or timezone.now(),
            created_by_id=admin_user.id,
            created_by_name=getattr(admin_user, "nickname", "") or getattr(admin_user, "phone", ""),
            remark=remark,
        )
        log_operation(
            operator=admin_user,
            action="RULE_PUBLISH",
            biz_type="RULE_VERSION",
            biz_id=version.id,
            after={"version_no": version.version_no},
            reason=remark,
        )
    return version


def get_platform_config() -> PlatformConfig:
    """读取平台配置单例；不存在时创建默认配置。"""
    config = PlatformConfig.objects.filter(singleton_key="default").first()
    if config is None:
        config = PlatformConfig.objects.create(singleton_key="default")
    return config


def update_platform_config(admin_user, data: dict, request=None):
    """更新平台配置；密钥字段留空表示保持原值。"""
    require_platform_admin(admin_user)
    config = get_platform_config()
    logo_url = data.get("logo_url", "")
    if logo_url and logo_url != config.logo_url:
        ensure_media_url(logo_url, kinds=(MediaAsset.Kind.IMAGE,))

    before = {
        "platform_name": config.platform_name,
        "amap_enabled": config.amap_enabled,
    }
    for field in (
        "platform_name",
        "logo_url",
        "contact_phone",
        "company_name",
        "icp_no",
        "privacy_policy",
        "user_agreement",
        "agreement_version",
        "miniapp_app_id",
        "miniapp_original_id",
        "amap_js_key",
        "amap_enabled",
    ):
        if field in data:
            setattr(config, field, data[field])
    for secret_field in ("miniapp_app_secret", "amap_web_key", "amap_js_security_code"):
        value = data.get(secret_field, "")
        if value:
            setattr(config, secret_field, value)
    config.updated_by_name = getattr(admin_user, "nickname", "") or getattr(admin_user, "phone", "")
    config.save()
    log_operation(
        operator=admin_user,
        action="PLATFORM_CONFIG_UPDATE",
        biz_type="PLATFORM_CONFIG",
        biz_id=config.id,
        before=before,
        after={
            "platform_name": config.platform_name,
            "amap_enabled": config.amap_enabled,
            "miniapp_app_secret_configured": bool(config.miniapp_app_secret),
            "amap_web_key_configured": bool(config.amap_web_key),
            "amap_js_security_code_configured": bool(config.amap_js_security_code),
        },
        request=request,
    )
    return config


def decide_audit(admin_user, task_id: int, decision: str, reason: str = "", request=None):
    """审核决定：更新任务状态，并按业务类型联动商户/资质状态。"""
    require_platform_admin(admin_user)
    if decision not in ("APPROVE", "REJECT"):
        raise ApiError("VALIDATION_ERROR", "decision 取值非法", 422)
    if decision == "REJECT" and not reason.strip():
        raise ApiError("VALIDATION_ERROR", "驳回必须填写原因", 422)

    from apps.catalog.models import Product
    from apps.merchants.models import Merchant, MerchantQualification

    with transaction.atomic():
        task = AuditTask.objects.select_for_update().filter(pk=task_id).first()
        if task is None:
            raise ApiError("NOT_FOUND", "审核任务不存在", 404)
        if task.status not in (AuditTask.Status.PENDING, AuditTask.Status.PROCESSING):
            raise ApiError("AUDIT_STATE_CONFLICT", "任务已被处理", 409)

        before_status = task.status
        if task.biz_type == AuditTask.BizType.MERCHANT:
            merchant = Merchant.objects.select_for_update().filter(pk=task.biz_id).first()
            if merchant is None:
                raise ApiError("NOT_FOUND", "商户不存在", 404)
            if merchant.status not in (Merchant.Status.PENDING, Merchant.Status.REJECTED):
                raise ApiError(
                    "MERCHANT_STATE_CONFLICT",
                    f"商户处于 {merchant.status}，不接受审核决定",
                    409,
                )
            if decision == "APPROVE":
                merchant.status = Merchant.Status.ACTIVE
                update_fields = ["status", "updated_at"]
                if merchant.opened_at is None:
                    merchant.opened_at = timezone.now()
                    update_fields.append("opened_at")
                merchant.save(update_fields=update_fields)
                merchant.qualifications.filter(audit_status=MerchantQualification.AuditStatus.PENDING).update(
                    audit_status=MerchantQualification.AuditStatus.APPROVED, reject_reason=""
                )
            else:
                merchant.status = Merchant.Status.REJECTED
                merchant.save(update_fields=["status", "updated_at"])
                merchant.qualifications.filter(audit_status=MerchantQualification.AuditStatus.PENDING).update(
                    audit_status=MerchantQualification.AuditStatus.REJECTED, reject_reason=reason
                )
        elif task.biz_type == AuditTask.BizType.QUALIFICATION:
            qualification = MerchantQualification.objects.select_for_update().filter(pk=task.biz_id).first()
            if qualification is None:
                raise ApiError("NOT_FOUND", "资质材料不存在", 404)
            qualification.audit_status = (
                MerchantQualification.AuditStatus.APPROVED
                if decision == "APPROVE"
                else MerchantQualification.AuditStatus.REJECTED
            )
            qualification.reject_reason = "" if decision == "APPROVE" else reason
            qualification.save(update_fields=["audit_status", "reject_reason", "updated_at"])
        elif task.biz_type == AuditTask.BizType.PRODUCT:
            product = Product.objects.select_for_update().filter(pk=task.biz_id).first()
            if product is None:
                raise ApiError("NOT_FOUND", "商品不存在", 404)
            if product.status != Product.Status.PENDING_AUDIT:
                raise ApiError(
                    "PRODUCT_STATE_CONFLICT",
                    f"商品处于 {product.status}，不接受审核决定",
                    409,
                )
            product.status = Product.Status.ON_SALE if decision == "APPROVE" else Product.Status.REJECTED
            product.reject_reason = "" if decision == "APPROVE" else reason
            product.audited_at = timezone.now()
            product.version += 1
            product.save(update_fields=["status", "reject_reason", "audited_at", "version", "updated_at"])
        else:
            raise ApiError("VALIDATION_ERROR", "该审核类型尚未接入 P0", 422)

        task.status = AuditTask.Status.APPROVED if decision == "APPROVE" else AuditTask.Status.REJECTED
        task.decision = decision
        task.reason = reason
        task.assigned_to_id = admin_user.id
        task.assigned_to_name = getattr(admin_user, "nickname", "") or getattr(admin_user, "phone", "")
        task.handled_at = timezone.now()
        task.save(
            update_fields=[
                "status",
                "decision",
                "reason",
                "assigned_to_id",
                "assigned_to_name",
                "handled_at",
                "updated_at",
            ]
        )
        log_operation(
            operator=admin_user,
            action="AUDIT_DECIDE",
            biz_type=task.biz_type,
            biz_id=task.biz_id,
            before={"task_status": before_status},
            after={"task_status": task.status, "task_id": task.id, "decision": decision},
            reason=reason,
            request=request,
        )
    return task


def batch_decide_audit(admin_user, task_ids, decision: str, reason: str = "", request=None):
    """批量审核：逐条独立事务处理，返回每条结果，部分失败不影响已成功项。"""
    require_platform_admin(admin_user)
    if decision not in ("APPROVE", "REJECT"):
        raise ApiError("VALIDATION_ERROR", "decision 取值非法", 422)
    if decision == "REJECT" and not reason.strip():
        raise ApiError("VALIDATION_ERROR", "批量驳回必须填写原因", 422)

    results = []
    for task_id in task_ids:
        try:
            task = decide_audit(admin_user, task_id, decision, reason, request=request)
            results.append(
                {
                    "id": task_id,
                    "ok": True,
                    "status": task.status,
                    "error_code": "",
                    "error_message": "",
                }
            )
        except ApiError as exc:
            results.append(
                {
                    "id": task_id,
                    "ok": False,
                    "status": "",
                    "error_code": exc.code,
                    "error_message": exc.message,
                }
            )
    return results


def get_current_popup():
    """返回当前生效的弹窗广告（优先级最高的一条），无则返回 None。

    条件：status=ENABLED、在投放时段内、未超展示上限。
    """
    now = timezone.now()
    qs = PopupAd.objects.filter(status=PopupAd.Status.ENABLED)
    qs = qs.filter(start_at__isnull=True) | qs.filter(start_at__lte=now)
    qs = qs.filter(end_at__isnull=True) | qs.filter(end_at__gte=now)
    qs = qs.filter(models.Q(max_impressions=0) | models.Q(impression_count__lt=models.F("max_impressions")))
    return qs.order_by("-priority", "-created_at").first()


def increment_popup_impression(popup_id: int) -> None:
    """展示计数 +1（客户端上报展示时调用）。"""
    PopupAd.objects.filter(pk=popup_id).update(impression_count=models.F("impression_count") + 1)


def create_popup_ad(admin_user, data: dict, request=None):
    """创建弹窗广告。"""
    require_platform_admin(admin_user)
    popup = PopupAd.objects.create(
        title=data["title"],
        image_url=data["image_url"],
        link_url=data.get("link_url", ""),
        frequency=data.get("frequency", PopupAd.Frequency.ONCE_PER_DAY),
        priority=data.get("priority", 0),
        start_at=data.get("start_at"),
        end_at=data.get("end_at"),
        max_impressions=data.get("max_impressions", 0),
        created_by_id=admin_user.id,
        created_by_name=getattr(admin_user, "nickname", "") or getattr(admin_user, "phone", ""),
    )
    log_operation(
        operator=admin_user,
        action="POPUP_CREATE",
        biz_type="POPUP_AD",
        biz_id=popup.id,
        after={"title": popup.title, "frequency": popup.frequency},
        request=request,
    )
    return popup


def update_popup_status(admin_user, popup_id: int, action: str, request=None):
    """上下架弹窗广告。action: enable / disable。"""
    require_platform_admin(admin_user)
    popup = PopupAd.objects.filter(pk=popup_id).first()
    if popup is None:
        raise ApiError("NOT_FOUND", "弹窗广告不存在", 404)
    if action == "enable":
        popup.status = PopupAd.Status.ENABLED
    elif action == "disable":
        popup.status = PopupAd.Status.DISABLED
    else:
        raise ApiError("VALIDATION_ERROR", f"未知操作 {action}", 422)
    popup.save(update_fields=["status", "updated_at"])
    log_operation(
        operator=admin_user,
        action=f"POPUP_{action.upper()}",
        biz_type="POPUP_AD",
        biz_id=popup.id,
        after={"status": popup.status},
        request=request,
    )
    return popup
