from decimal import Decimal

from django.conf import settings
from rest_framework import serializers

from apps.catalog.models import Category

from .models import Merchant, MerchantQualification, MerchantStaff
from .services import resolve_commission_rate


class MerchantSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True, default="")

    class Meta:
        model = Merchant
        fields = (
            "id",
            "merchant_no",
            "name",
            "short_name",
            "category_id",
            "category_name",
            "logo_url",
            "description",
            "contact_phone",
            "city",
            "district",
            "address",
            "lng",
            "lat",
            "business_hours",
            "status",
            "opened_at",
        )


class MerchantSelfProfileSerializer(serializers.ModelSerializer):
    """商户端自身资料：不含敏感资质与佣金信息。"""

    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Merchant
        fields = (
            "id",
            "merchant_no",
            "name",
            "short_name",
            "logo_url",
            "description",
            "contact_phone",
            "province",
            "city",
            "district",
            "address",
            "lng",
            "lat",
            "business_hours",
            "status",
            "status_label",
            "opened_at",
        )


class StoreSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True, default="")
    distance_meters = serializers.SerializerMethodField()

    class Meta:
        model = Merchant
        fields = (
            "id",
            "merchant_no",
            "name",
            "logo_url",
            "category_id",
            "category_name",
            "address",
            "city",
            "district",
            "lng",
            "lat",
            "distance_meters",
            "business_hours",
            "status",
        )

    def get_distance_meters(self, obj):
        return getattr(obj, "distance_meters", None)


class AdminMerchantSerializer(serializers.ModelSerializer):
    """平台商户列表行：佣金率返回生效值（商户覆盖优先，类目默认兜底）。"""

    category_name = serializers.CharField(source="category.name", read_only=True, default="")
    commission_rate = serializers.SerializerMethodField()
    today_orders = serializers.IntegerField(read_only=True, default=0)
    settled_amount = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Merchant
        fields = (
            "id",
            "merchant_no",
            "name",
            "short_name",
            "category_id",
            "category_name",
            "contact_phone",
            "city",
            "district",
            "status",
            "commission_rate",
            "settlement_cycle_days",
            "today_orders",
            "settled_amount",
            "created_at",
        )

    def get_commission_rate(self, obj):
        return float(resolve_commission_rate(obj))


class AdminMerchantQualificationSerializer(serializers.ModelSerializer):
    type_label = serializers.CharField(source="get_type_display", read_only=True)

    class Meta:
        model = MerchantQualification
        fields = ("id", "type", "type_label", "file_url", "expire_at", "audit_status", "reject_reason")


class AdminMerchantStaffSerializer(serializers.ModelSerializer):
    nickname = serializers.CharField(source="user.nickname", read_only=True, default="")
    role_label = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = MerchantStaff
        fields = ("id", "user_id", "nickname", "role", "role_label", "status", "joined_at")


class AdminMerchantDetailSerializer(AdminMerchantSerializer):
    commission_override = serializers.DecimalField(
        source="commission_rate", max_digits=5, decimal_places=4, allow_null=True, read_only=True
    )
    qualifications = AdminMerchantQualificationSerializer(many=True, read_only=True)
    staff = AdminMerchantStaffSerializer(many=True, read_only=True)
    balances = serializers.SerializerMethodField()
    bank_last4 = serializers.SerializerMethodField()
    gmv_total = serializers.IntegerField(read_only=True, default=0)

    class Meta(AdminMerchantSerializer.Meta):
        fields = AdminMerchantSerializer.Meta.fields + (
            "logo_url",
            "description",
            "province",
            "address",
            "lng",
            "lat",
            "business_hours",
            "opened_at",
            "commission_override",
            "qualifications",
            "staff",
            "balances",
            "bank_last4",
            "gmv_total",
        )

    def get_balances(self, obj):
        account = getattr(obj, "account", None)
        return {
            "pending_amount": account.pending_balance if account else 0,
            "frozen_amount": account.frozen_balance if account else 0,
            "available_amount": account.available_balance if account else 0,
            "withdrawing_amount": account.withdrawing_balance if account else 0,
        }

    def get_bank_last4(self, obj):
        bank_info = obj.bank_info or {}
        card_no = str(bank_info.get("card_no", "")).strip()
        return card_no[-4:] if card_no else ""


class MerchantStatusInputSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=(Merchant.Status.ACTIVE, Merchant.Status.RESTING, Merchant.Status.BANNED))
    reason = serializers.CharField(max_length=200)


class AdminMerchantLocationInputSerializer(serializers.Serializer):
    """平台设置商户真实坐标，统一使用高德 GCJ-02。"""

    lng = serializers.DecimalField(
        max_digits=9,
        decimal_places=6,
        min_value=Decimal("-180"),
        max_value=Decimal("180"),
    )
    lat = serializers.DecimalField(
        max_digits=9,
        decimal_places=6,
        min_value=Decimal("-90"),
        max_value=Decimal("90"),
    )
    province = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    city = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    district = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    address = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class AdminMerchantQualificationInputSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=MerchantQualification.Type.choices)
    file_url = serializers.CharField(max_length=300)
    expire_at = serializers.DateField(required=False, allow_null=True)

    def validate_file_url(self, value):
        from apps.governance.media_services import ensure_media_url

        return ensure_media_url(value)


class AdminMerchantCreateInputSerializer(serializers.Serializer):
    """平台创建商户：固定直接营业，必须绑定已有负责人。"""

    name = serializers.CharField(max_length=80)
    short_name = serializers.CharField(max_length=40, required=False, allow_blank=True, default="")
    category_id = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), source="category")
    contact_phone = serializers.CharField(max_length=20)
    province = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    city = serializers.CharField(max_length=32)
    district = serializers.CharField(max_length=32)
    address = serializers.CharField(max_length=200)
    lng = serializers.DecimalField(
        max_digits=9,
        decimal_places=6,
        required=False,
        allow_null=True,
        min_value=Decimal("-180"),
        max_value=Decimal("180"),
    )
    lat = serializers.DecimalField(
        max_digits=9,
        decimal_places=6,
        required=False,
        allow_null=True,
        min_value=Decimal("-90"),
        max_value=Decimal("90"),
    )
    business_hours = serializers.JSONField(required=False, default=dict)
    commission_rate = serializers.DecimalField(
        max_digits=5,
        decimal_places=4,
        required=False,
        allow_null=True,
        min_value=Decimal("0"),
        max_value=Decimal("1"),
    )
    settlement_cycle_days = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=360,
        default=settings.DEFAULT_SETTLEMENT_CYCLE_DAYS,
    )
    bank_info = serializers.JSONField(required=False, default=dict)
    qualifications = AdminMerchantQualificationInputSerializer(many=True, required=False, default=list)
    owner_phone = serializers.CharField(max_length=20)

    def validate_bank_info(self, value):
        if not value:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("bank_info 必须是对象")
        return {key: str(value[key]) for key in ("bank", "card_no") if value.get(key)}

    def validate_owner_phone(self, value):
        from apps.accounts.models import AppUser

        phone = value.strip()
        if not AppUser.objects.filter(phone=phone, status=AppUser.Status.ACTIVE).exists():
            raise serializers.ValidationError("负责人手机号未注册或已停用，请先让负责人登录一次")
        return phone
