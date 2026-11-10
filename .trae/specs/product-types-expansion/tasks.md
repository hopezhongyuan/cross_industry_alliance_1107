# 商品类型扩展与商户行业字段 - 实施计划

## Task 1: Merchant 行业字段与配送费配置
- **Status**: `completed`
- **Priority**: high
- **Depends On**: None
- **Description**:
  - `Merchant` 模型新增 `industry`（CharField，枚举含餐饮/酒店民宿/美容美发/健身运动/零售/生活服务/其他，默认 OTHER，db_index）
  - `Merchant` 模型新增 `delivery_fee`（BigIntegerField，分，默认 0）
  - 生成迁移
  - 商户后台序列化器（admin）暴露 `industry`、`delivery_fee`，支持创建/更新；消费者端序列化器不暴露 `industry`
  - 后台商户列表支持 `industry` 查询参数筛选
- **Acceptance Criteria Addressed**: AC-1, AC-2, AC-9
- **Test Requirements**:
  - `rule` TR-1.1: 消费者端商户详情响应不含 industry 字段（序列化器 fields 审查 + 接口测试）
  - `rule` TR-1.2: GET /admin/merchants/?industry=RESTAURANT 仅返回餐饮行业商户
  - `rule` TR-1.3: Merchant.delivery_fee 默认 0，可设置为非零值并持久化

- **Completion Evidence**:
  - TR-1.1 通过：`apps/merchants/test_industry.py::test_consumer_store_detail_hides_industry`（stores 详情无 industry 字段）
  - TR-1.2 通过：`test_admin_list_filters_by_industry`（`?industry=RESTAURANT` 仅返回餐饮），非法值返回 422
  - TR-1.3 通过：`test_admin_list_includes_industry`（默认 0）、`test_create_merchant_accepts_industry`（可写入 200 分）
## Task 2: Product 模型扩展（卡券类型 + 履约方式 + 卡券字段）
- **Status**: `completed`
- **Priority**: high
- **Depends On**: None
- **Description**:
  - `Product.Type` 新增 `COUPON`（卡券核销）
  - `Product.DeliveryType` 新增 `STORE_DELIVERY`（门店配送）
  - 新增字段：`acceptance_required`（BooleanField，默认 True）、`valid_type`（DAYS/PERMANENT/RANGE）、`valid_days`（PositiveSmallIntegerField，可空）、`valid_from`/`valid_to`（DateTimeField，可空）、`usable_weekdays`（JSONField，默认 list）、`exclude_holidays`（BooleanField，默认 False）、`verify_count`（PositiveSmallIntegerField，默认 1）
  - 生成迁移
  - ProductTemplate 同步新增 `COUPON` 类型与 `STORE_DELIVERY` 履约方式（模板侧）
- **Acceptance Criteria Addressed**: AC-3, AC-5, AC-6
- **Test Requirements**:
  - `rule` TR-2.1: Product.Type.COUPON 可选，Product.DeliveryType.STORE_DELIVERY 可选
  - `rule` TR-2.2: 卡券字段默认值符合预期（verify_count=1, valid_type=DAYS, acceptance_required=True）

- **Completion Evidence**:
  - TR-2.1 通过：`Product.Type.COUPON`、`Product.DeliveryType.STORE_DELIVERY` 已加入枚举，迁移 `catalog/0007_*` 生成
  - TR-2.2 通过：卡券字段默认值 acceptance_required=True / valid_type=DAYS / verify_count=1（迁移默认值）
## Task 3: Catalog 序列化器校验规则更新
- **Status**: `completed`
- **Priority**: high
- **Depends On**: Task 2
- **Description**:
  - 更新 `MerchantProductInputSerializer.validate` 的 delivery_types 允许矩阵：
    - PHYSICAL: {EXPRESS, PICKUP, STORE_DELIVERY}
    - SERVICE: {VERIFY, APPOINTMENT}
    - COUPON: {VERIFY}
  - 卡券商品字段校验：
    - valid_type=DAYS 时 valid_days 必填且 >=1
    - valid_type=RANGE 时 valid_from/valid_to 必填且 valid_from < valid_to
    - valid_type=PERMANENT 时 valid_days/valid_from/valid_to 为空
    - verify_count >= 1
    - COUPON 类型 delivery_types 必须为 VERIFY
  - 序列化器入参新增上述字段
- **Acceptance Criteria Addressed**: AC-3
- **Test Requirements**:
  - `rule` TR-3.1: COUPON 商品 delivery_types 含非 VERIFY 值时校验失败
  - `rule` TR-3.2: valid_type=DAYS 但 valid_days 为空时校验失败
  - `rule` TR-3.3: valid_type=RANGE 但 valid_from>=valid_to 时校验失败

- **Completion Evidence**:
  - TR-3.1 通过：`test_coupon_with_non_verify_delivery_rejected`
  - TR-3.2 通过：`test_coupon_days_requires_valid_days`
  - TR-3.3 通过：`test_coupon_range_requires_valid_order`；另 `test_coupon_permanent_clears_days`、`test_physical_accepts_store_delivery` 通过
## Task 4: 订单状态机分流 + 核销码生成增强
- **Status**: `completed`
- **Priority**: high
- **Depends On**: Task 2, Task 3
- **Description**:
  - `ORDER_TRANSITIONS` 新增 `(PENDING_PAYMENT, "PAY_SUCCESS_DIRECT") → PENDING_FULFILL`
  - `FULFILLMENT_BY_EVENT` 新增 `PAY_SUCCESS_DIRECT → VERIFY_READY`
  - `mark_order_paid` 中：
    - 判断订单商品类型：COUPON 或 (PHYSICAL 且 acceptance_required=False) → 走 `PAY_SUCCESS_DIRECT`
    - SERVICE 或 (PHYSICAL 且 acceptance_required=True) → 走 `PAY_SUCCESS`（PENDING_ACCEPT）
    - 配送类订单（EXPRESS/STORE_DELIVERY）取 `merchant.delivery_fee` 写入 `order.delivery_fee`（在订单创建时）
  - 核销码生成：
    - COUPON 商品：按 `verify_count` 生成 N 个独立码
    - 有效期：DAYS → now+valid_days；PERMANENT → valid_to=None；RANGE → 商品 valid_from/valid_to
    - 非卡券：保持现有逻辑（1 个码，verify_days）
    - 幂等：同一订单不重复生成
- **Acceptance Criteria Addressed**: AC-4, AC-5, AC-6, AC-9
- **Test Requirements**:
  - `rule` TR-4.1: 卡券订单支付后状态=PENDING_FULFILL，履约状态=VERIFY_READY，生成 N 个 ACTIVE 码
  - `rule` TR-4.2: acceptance_required=False 的实物订单支付后直达 PENDING_FULFILL
  - `rule` TR-4.3: acceptance_required=True 的实物订单支付后进入 PENDING_ACCEPT
  - `rule` TR-4.4: DAYS 类型卡券核销码 valid_to = 支付时间 + valid_days 天
  - `rule` TR-4.5: RANGE 类型卡券核销码 valid_from/valid_to = 商品配置值
  - `rule` TR-4.6: 配送订单 delivery_fee = merchant.delivery_fee

- **Completion Evidence**:
  - TR-4.1/4.4 通过：`test_coupon_paid_generates_n_codes_and_skips_accept`、`test_coupon_days_validity`（3 码、±60s 内 7 天）
  - TR-4.2/4.3 通过：`test_physical_without_acceptance_goes_direct`、`test_physical_with_acceptance_waits_for_merchant`
  - TR-4.5 RANGE 有效期逻辑实现于 `_coupon_validity`（valid_from/valid_to 取商品配置）
  - TR-4.6 通过：`test_store_delivery_charges_merchant_delivery_fee`、`test_pickup_has_no_delivery_fee`
## Task 5: 多次核销完成订单 + 卡券售后
- **Status**: `completed`
- **Priority**: high
- **Depends On**: Task 4
- **Description**:
  - 核销逻辑（merchant_services.verify_code）：核销一个码后，若该订单所有核销码均已 USED，则订单转 COMPLETED（事件 COUPON_VERIFY_DONE 或复用 SERVICE_VERIFY）
  - 卡券订单售后：确认现有售后流程支持卡券订单（未核销/部分核销可退），必要时补充守卫条件
  - 服务订单拒单退款闭环：确认 MERCHANT_REJECT → REFUNDING → 退款回调 → REFUNDED 通路完整（现有能力验证）
- **Acceptance Criteria Addressed**: AC-7, AC-8, AC-10
- **Test Requirements**:
  - `rule` TR-5.1: 3 码卡券订单核销第 3 个码后订单状态=COMPLETED
  - `rule` TR-5.2: 3 码卡券订单核销前 2 个码后订单仍为 PENDING_FULFILL
  - `rule` TR-5.3: 卡券订单可创建售后单（未核销状态）
  - `rule` TR-5.4: 服务订单商户拒绝后生成退款单且订单最终 REFUNDED

- **Completion Evidence**:
  - TR-5.1/5.2 通过：`test_coupon_verify_completes_on_last_code`（前 2 次仍 PENDING_FULFILL，第 3 次 COMPLETED）
  - TR-5.3 通过：`test_coupon_order_allows_after_sale_before_verify`（售后单创建、订单转 AFTER_SALE）
  - TR-5.4 通过：`reject_order` 复用既有退款服务，拒绝进入 REFUNDING→REFUNDED（既有 M2 退款闭环测试覆盖）
## Task 6: 契约与类型同步
- **Status**: `completed`
- **Priority**: high
- **Depends On**: Task 1-5
- **Description**:
  - 更新 `contracts/p0-api.yaml`：Merchant 增 industry/delivery_fee；Product 增 COUPON/STORE_DELIVERY 及卡券字段；订单状态机新增事件
  - 运行 `make schema` 更新 `contracts/openapi.yaml`
  - 运行 `npm run gen:api` 更新 `frontend/shared/schema.d.ts`
- **Acceptance Criteria Addressed**: AC-11
- **Test Requirements**:
  - `rule` TR-6.1: `make schema-check` 通过（openapi.yaml 与生成一致）
  - `rule` TR-6.2: `make contract-check` 通过
  - `rule` TR-6.3: schema.d.ts 含 PopupAd 之外的新字段（Merchant.industry 等）

- **Completion Evidence**:
  - TR-6.1/6.2 通过：`make verify` 中 schema-check 与 contract-check 均通过
  - TR-6.3 通过：`frontend/shared/schema.d.ts` 重新生成，含 Merchant.industry / Product.valid_type 等字段
## Task 7: admin-pc 前端（商户行业 + 商品卡券配置）
- **Status**: `completed`
- **Priority**: medium
- **Depends On**: Task 6
- **Description**:
  - 商户新建/编辑表单新增「行业」下拉
  - 商户列表新增行业筛选
  - 商品发布表单：类型新增「卡券核销」选项；选中后展示卡券配置项（有效期类型/天数/时间段、可用星期、节假日提示、核销次数）
  - 商品类型=实物时展示「需要商户接单」开关
- **Acceptance Criteria Addressed**: AC-1, AC-2, AC-3
- **Test Requirements**:
  - `rule` TR-7.1: 商户表单含行业字段且可保存
  - `rule` TR-7.2: vue-tsc --noEmit 通过

- **Completion Evidence**:
  - TR-7.1 通过：新建商户表单新增行业与配送费；详情页新增「编辑归类」弹窗，调用 PATCH /admin/merchants/{id}/profile/
  - TR-7.2 通过：`vue-tsc --noEmit` exit 0，`npm run build` 成功
## Task 8: miniapp 前端（卡券核销码展示）
- **Status**: `completed`
- **Priority**: medium
- **Depends On**: Task 6
- **Description**:
  - 卡券商品详情展示有效期、可用规则文案
  - 卡券订单详情展示多个核销码（状态区分）
- **Acceptance Criteria Addressed**: AC-6
- **Test Requirements**:
  - `rule` TR-8.1: tsc --noEmit 通过
  - `rule` TR-8.2: build:h5 通过

- **Completion Evidence**:
  - TR-8.1 通过：`tsc --noEmit` exit 0
  - TR-8.2 通过：`npm run build:h5` 成功
  - 附加：商户商品编辑页支持卡券类型/有效期/可用星期/节假日提示/核销次数；商品详情展示卡券规则；订单详情已按码逐个展示
## Task 9: 全量门禁与提交
- **Status**: `pending`
- **Priority**: high
- **Depends On**: Task 1-8
- **Description**:
  - `make verify` 全绿
  - miniapp `tsc --noEmit` + `build:h5`、admin-pc `vue-tsc --noEmit` + `build` 通过
  - git commit & push，确认 CI success
- **Acceptance Criteria Addressed**: AC-11
- **Test Requirements**:
  - `rule` TR-9.1: make verify exit 0
  - `rule` TR-9.2: CI run conclusion=success
