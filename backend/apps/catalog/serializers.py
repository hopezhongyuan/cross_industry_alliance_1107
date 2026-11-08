from datetime import timedelta

from django.db.models import F
from django.utils import timezone
from rest_framework import serializers

from .models import (
    Category,
    MerchantProductCategory,
    Product,
    ProductSku,
    ProductTemplate,
    ServiceSlot,
)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "parent", "name", "icon_url", "level", "sort")


class AdminCategorySerializer(serializers.ModelSerializer):
    parent_name = serializers.CharField(source="parent.name", read_only=True, default="")

    class Meta:
        model = Category
        fields = ("id", "parent", "parent_name", "name", "icon_url", "level", "sort", "status")


class AdminCategoryInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=40)
    parent_id = serializers.IntegerField(required=False, allow_null=True)
    icon_url = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")
    sort = serializers.IntegerField(required=False, default=0)
    status = serializers.ChoiceField(choices=Category.Status.choices, required=False, default=Category.Status.ENABLED)

    def validate_icon_url(self, value):
        from apps.governance.media_services import ensure_media_url
        from apps.governance.models import MediaAsset

        return ensure_media_url(value, kinds=(MediaAsset.Kind.IMAGE,))


class MerchantProductCategorySerializer(serializers.ModelSerializer):
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = MerchantProductCategory
        fields = ("id", "name", "sort", "status", "product_count")

    def get_product_count(self, obj):
        return obj.products.count()


class MerchantProductCategoryInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=40)
    sort = serializers.IntegerField(required=False, default=0)
    status = serializers.ChoiceField(
        choices=MerchantProductCategory.Status.choices,
        required=False,
        default=MerchantProductCategory.Status.ENABLED,
    )


class ProductSkuSerializer(serializers.ModelSerializer):
    available_stock = serializers.IntegerField(read_only=True)

    class Meta:
        model = ProductSku
        fields = ("id", "sku_code", "spec_json", "price", "available_stock")


class ServiceSlotSerializer(serializers.ModelSerializer):
    remaining = serializers.IntegerField(read_only=True)

    class Meta:
        model = ServiceSlot
        fields = ("id", "slot_date", "start_time", "end_time", "capacity", "remaining", "status")


class ProductSerializer(serializers.ModelSerializer):
    merchant_name = serializers.CharField(source="merchant.name", read_only=True)
    merchant_address = serializers.CharField(source="merchant.address", read_only=True, default="")
    merchant_phone = serializers.CharField(source="merchant.contact_phone", read_only=True, default="")
    category_name = serializers.CharField(source="category.name", read_only=True, default="")
    type_label = serializers.CharField(source="get_type_display", read_only=True)
    skus = ProductSkuSerializer(many=True, read_only=True)
    slots = serializers.SerializerMethodField()
    refund_policy = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            "id",
            "merchant_id",
            "merchant_name",
            "merchant_address",
            "merchant_phone",
            "category_id",
            "category_name",
            "type",
            "type_label",
            "title",
            "subtitle",
            "cover_url",
            "images",
            "description",
            "price",
            "original_price",
            "status",
            "verify_days",
            "appointment_required",
            "delivery_types",
            "sold_count",
            "skus",
            "slots",
            "refund_policy",
        )

    def get_slots(self, obj):
        if not obj.appointment_required:
            return []
        today = timezone.localdate()
        slots = obj.slots.filter(
            slot_date__gte=today,
            slot_date__lte=today + timedelta(days=7),
            status=ServiceSlot.Status.OPEN,
            reserved_count__lt=F("capacity"),
        ).order_by("slot_date", "start_time")[:20]
        return ServiceSlotSerializer(slots, many=True).data

    def get_refund_policy(self, obj):
        if obj.type == Product.Type.SERVICE:
            return "未核销、有效期内可退"
        return "未发货可退，已签收按售后规则处理"


class ProductListSerializer(serializers.ModelSerializer):
    merchant_name = serializers.CharField(source="merchant.name", read_only=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "merchant_id",
            "merchant_name",
            "type",
            "title",
            "subtitle",
            "cover_url",
            "price",
            "original_price",
            "sold_count",
            "delivery_types",
        )


class MerchantProductSkuInputSerializer(serializers.Serializer):
    sku_code = serializers.CharField(max_length=40)
    spec = serializers.JSONField(required=False, default=dict)
    price_amount = serializers.IntegerField(min_value=1)
    stock = serializers.IntegerField(min_value=0, default=0)


class MerchantProductInputSerializer(serializers.Serializer):
    """商户发布/编辑商品：提交即进入审核，支持多 SKU。"""

    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.filter(status=Category.Status.ENABLED), source="category"
    )
    merchant_category_id = serializers.IntegerField(required=False, allow_null=True)
    product_code = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    type = serializers.ChoiceField(choices=Product.Type.choices)
    title = serializers.CharField(max_length=120)
    subtitle = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    cover_url = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")
    images = serializers.ListField(child=serializers.CharField(max_length=300), required=False, default=list)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    price_amount = serializers.IntegerField(min_value=1)
    original_price_amount = serializers.IntegerField(min_value=0, required=False, default=0)
    verify_days = serializers.IntegerField(min_value=1, max_value=3650, required=False, default=30)
    appointment_required = serializers.BooleanField(required=False, default=False)
    delivery_types = serializers.ListField(
        child=serializers.ChoiceField(choices=Product.DeliveryType.choices), min_length=1
    )
    skus = MerchantProductSkuInputSerializer(many=True, min_length=1)
    version = serializers.IntegerField(min_value=0, required=False)

    def validate(self, attrs):
        category = attrs["category"]
        if category.children.exists():
            raise serializers.ValidationError("请选择二级类目")
        if category.parent_id and category.parent.status != Category.Status.ENABLED:
            raise serializers.ValidationError("上级类目已停用")
        allowed = {
            Product.Type.PHYSICAL: {Product.DeliveryType.EXPRESS, Product.DeliveryType.PICKUP},
            Product.Type.SERVICE: {Product.DeliveryType.VERIFY, Product.DeliveryType.APPOINTMENT},
        }
        deliveries = set(attrs["delivery_types"])
        if deliveries - allowed[attrs["type"]]:
            raise serializers.ValidationError("履约方式与商品类型不匹配")
        if attrs.get("appointment_required") and Product.DeliveryType.APPOINTMENT not in deliveries:
            raise serializers.ValidationError("需预约商品必须包含预约履约方式")
        codes = [sku["sku_code"] for sku in attrs["skus"]]
        if len(set(codes)) != len(codes):
            raise serializers.ValidationError("SKU 编码重复")
        return attrs


class MerchantSkuSerializer(ProductSkuSerializer):
    class Meta(ProductSkuSerializer.Meta):
        fields = ProductSkuSerializer.Meta.fields + ("stock",)


class MerchantProductListSerializer(serializers.ModelSerializer):
    total_stock = serializers.SerializerMethodField()
    merchant_category_name = serializers.CharField(source="merchant_category.name", read_only=True, default="")

    class Meta:
        model = Product
        fields = (
            "id",
            "product_code",
            "merchant_category_id",
            "merchant_category_name",
            "type",
            "title",
            "subtitle",
            "cover_url",
            "price",
            "status",
            "reject_reason",
            "total_stock",
            "sold_count",
            "delivery_types",
            "submitted_at",
            "updated_at",
            "off_sale_by",
            "off_sale_reason",
            "off_sale_at",
        )

    def get_total_stock(self, obj):
        return sum(sku.available_stock for sku in obj.skus.all())


class MerchantProductDetailSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True, default="")
    merchant_category_name = serializers.CharField(source="merchant_category.name", read_only=True, default="")
    type_label = serializers.CharField(source="get_type_display", read_only=True)
    skus = MerchantSkuSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "product_code",
            "category_id",
            "category_name",
            "merchant_category_id",
            "merchant_category_name",
            "type",
            "type_label",
            "title",
            "subtitle",
            "cover_url",
            "images",
            "description",
            "price",
            "original_price",
            "status",
            "reject_reason",
            "verify_days",
            "appointment_required",
            "delivery_types",
            "sold_count",
            "skus",
            "submitted_at",
            "audited_at",
            "version",
            "created_at",
            "updated_at",
            "off_sale_by",
            "off_sale_reason",
            "off_sale_at",
        )


class AdminProductDetailSerializer(serializers.ModelSerializer):
    merchant_name = serializers.CharField(source="merchant.name", read_only=True)
    merchant_no = serializers.CharField(source="merchant.merchant_no", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True, default="")
    merchant_category_name = serializers.CharField(source="merchant_category.name", read_only=True, default="")
    type_label = serializers.CharField(source="get_type_display", read_only=True)
    skus = MerchantSkuSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "product_code",
            "merchant_id",
            "merchant_name",
            "merchant_no",
            "category_id",
            "category_name",
            "merchant_category_id",
            "merchant_category_name",
            "type",
            "type_label",
            "title",
            "subtitle",
            "cover_url",
            "images",
            "description",
            "price",
            "original_price",
            "status",
            "reject_reason",
            "verify_days",
            "appointment_required",
            "delivery_types",
            "sold_count",
            "skus",
            "submitted_at",
            "audited_at",
            "version",
            "created_at",
        )


class AdminTemplateInputSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=120)
    subtitle = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    type = serializers.ChoiceField(choices=ProductTemplate.Type.choices)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.filter(status=Category.Status.ENABLED), source="category"
    )
    cover_url = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")
    images = serializers.ListField(child=serializers.CharField(max_length=300), required=False, default=list)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    price_amount = serializers.IntegerField(min_value=1)
    original_price_amount = serializers.IntegerField(min_value=0, required=False, default=0)
    verify_days = serializers.IntegerField(min_value=1, max_value=3650, required=False, default=30)
    appointment_required = serializers.BooleanField(required=False, default=False)
    delivery_types = serializers.ListField(
        child=serializers.ChoiceField(choices=Product.DeliveryType.choices), min_length=1
    )
    skus = MerchantProductSkuInputSerializer(many=True, min_length=1)
    status = serializers.ChoiceField(
        choices=ProductTemplate.Status.choices, required=False, default=ProductTemplate.Status.DRAFT
    )
    scope = serializers.ChoiceField(
        choices=ProductTemplate.Scope.choices, required=False, default=ProductTemplate.Scope.NONE
    )
    merchant_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)

    def validate(self, attrs):
        category = attrs["category"]
        if category.children.exists():
            raise serializers.ValidationError("请选择二级类目")
        if category.parent_id and category.parent.status != Category.Status.ENABLED:
            raise serializers.ValidationError("上级类目已停用")
        allowed = {
            ProductTemplate.Type.PHYSICAL: {Product.DeliveryType.EXPRESS, Product.DeliveryType.PICKUP},
            ProductTemplate.Type.SERVICE: {Product.DeliveryType.VERIFY, Product.DeliveryType.APPOINTMENT},
        }
        if set(attrs["delivery_types"]) - allowed[attrs["type"]]:
            raise serializers.ValidationError("履约方式与商品类型不匹配")
        codes = [sku["sku_code"] for sku in attrs["skus"]]
        if len(set(codes)) != len(codes):
            raise serializers.ValidationError("SKU 编码重复")
        return attrs


class AdminTemplateSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True, default="")
    target_merchant_ids = serializers.SerializerMethodField()
    adoption_count = serializers.SerializerMethodField()

    class Meta:
        model = ProductTemplate
        fields = (
            "id",
            "template_no",
            "title",
            "subtitle",
            "type",
            "category_id",
            "category_name",
            "cover_url",
            "images",
            "description",
            "price",
            "original_price",
            "verify_days",
            "appointment_required",
            "delivery_types",
            "skus",
            "status",
            "scope",
            "target_merchant_ids",
            "adoption_count",
            "published_at",
            "created_at",
        )

    def get_target_merchant_ids(self, obj):
        return list(obj.target_merchants.values_list("id", flat=True))

    def get_adoption_count(self, obj):
        return obj.adoptions.count()


class AdminProductListSerializer(serializers.ModelSerializer):
    merchant_name = serializers.CharField(source="merchant.name", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True, default="")

    class Meta:
        model = Product
        fields = (
            "id",
            "product_code",
            "title",
            "merchant_id",
            "merchant_name",
            "category_id",
            "category_name",
            "type",
            "price",
            "status",
            "sold_count",
            "off_sale_by",
            "off_sale_reason",
            "updated_at",
        )


class AdminProductStatusInputSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=("FORCE_OFF", "RESTORE"))
    reason = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class MerchantTemplateSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True, default="")
    adopted_product_id = serializers.SerializerMethodField()
    adopted_status = serializers.SerializerMethodField()

    class Meta:
        model = ProductTemplate
        fields = (
            "id",
            "template_no",
            "title",
            "subtitle",
            "type",
            "category_id",
            "category_name",
            "cover_url",
            "images",
            "description",
            "price",
            "original_price",
            "verify_days",
            "appointment_required",
            "delivery_types",
            "skus",
            "adopted_product_id",
            "adopted_status",
        )

    def _adoption(self, obj):
        merchant = self.context.get("merchant")
        if merchant is None:
            return None
        return obj.adoptions.filter(merchant=merchant).first()

    def get_adopted_product_id(self, obj):
        adoption = self._adoption(obj)
        return adoption.product_id if adoption else None

    def get_adopted_status(self, obj):
        adoption = self._adoption(obj)
        return adoption.product.status if adoption and adoption.product else ""
