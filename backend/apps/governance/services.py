"""治理服务：平台权限校验、操作日志与规则版本发布。"""

from django.db import transaction
from django.utils import timezone

from apps.common.api import ApiError
from apps.common.utils import generate_no

from .models import OperationLog, RuleVersion


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
