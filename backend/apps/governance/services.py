"""治理服务：平台权限校验、操作日志、规则版本发布与审核决定。"""

from django.db import transaction
from django.utils import timezone

from apps.common.api import ApiError
from apps.common.utils import generate_no

from .models import AuditTask, OperationLog, RuleVersion


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
