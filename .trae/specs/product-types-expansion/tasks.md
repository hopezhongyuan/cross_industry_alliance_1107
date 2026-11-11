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
- **Status**: `completed`
- **Completion Evidence**:
  - TR-9.1 通过：`make verify` exit 0（258 passed，覆盖率 91.41%）
  - TR-9.2 通过：CI run 42728320098 conclusion=success
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

## Issue I-1: 卡券核销缺少订单状态守卫
- **Status**: `completed`
- **Completion Evidence**:
  - TR-I-1.1 通过：`test_coupon_verify_blocked_while_after_sale`（409 且码仍 ACTIVE）
- **Priority**: high
- **Depends On**: None
- **Discovered By**: Review R1 (F1)
- **Description**:
  - `verify_code` 卡券分支在标记核销码前必须校验 `order.status == PENDING_FULFILL`，否则 409 且不解码
- **Acceptance Criteria Addressed**: AC-7, AC-10
- **Test Requirements**:
  - `rule` TR-I-1.1: 售后中卡券订单核销返回 409，核销码仍为 ACTIVE

## Issue I-2: 卡券履约前部分退款导致资金悬空
- **Status**: `completed`
- **Completion Evidence**:
  - TR-I-2.1 通过：`test_coupon_partial_refund_rejected_before_verify`（409 REFUND_AMOUNT_EXCEEDED）；全额退款作废码逻辑保留
- **Priority**: high
- **Depends On**: None
- **Discovered By**: Review R1 (F2)
- **Description**:
  - 卡券订单在未完成（PENDING_FULFILL/AFTER_SALE）时只允许全额退款，部分退款 409；全额退款作废剩余码（已实现）
- **Acceptance Criteria Addressed**: AC-10
- **Test Requirements**:
  - `rule` TR-I-2.1: 卡券未完成订单部分退款被拒 409；全额退款成功且剩余码 INVALID

## Issue I-3: 模板侧 COUPON / STORE_DELIVERY 与卡券字段未对齐
- **Status**: `completed`
- **Completion Evidence**:
  - TR-I-3.1 通过：`AdminTemplateTypeTests` 3 项（COUPON 模板合法、实物+门店配送合法、COUPON 拒绝非 VERIFY）；模板字段经 `_template_fields` / `_apply_coupon_fields` / adopt 透传
- **Priority**: high
- **Depends On**: None
- **Discovered By**: Review R1 (F3)
- **Description**:
  - 模板序列化器 allowed 补 COUPON / PHYSICAL+STORE_DELIVERY，缺失类型不再 KeyError
  - 模板入参与 `_template_fields`、`sync_template`、adopt 透传 acceptance_required 与卡券字段
- **Acceptance Criteria Addressed**: AC-3, AC-11
- **Test Requirements**:
  - `rule` TR-I-3.1: 创建 COUPON 模板不再 500；认领后的商品带出卡券配置

## Issue I-4: 免接单实物履约状态错误
- **Status**: `completed`
- **Completion Evidence**:
  - TR-I-4.1 通过：`test_physical_without_acceptance_goes_direct` 断言 fulfillment_status=NOT_STARTED；`_direct_fulfillment_status` 按订单类型分流
- **Priority**: medium
- **Depends On**: None
- **Discovered By**: Review R1 (F4)
- **Description**:
  - `PAY_SUCCESS_DIRECT` 按订单类型设置履约状态：COUPON→VERIFY_READY；实物→按 EXPRESS/PICKUP/STORE_DELIVERY 分别 NOT_STARTED/PICKUP_READY/NOT_STARTED
- **Acceptance Criteria Addressed**: AC-4
- **Test Requirements**:
  - `rule` TR-I-4.1: 免接单实物快递单支付后 fulfillment_status=NOT_STARTED

## Issue I-5: 核销未校验生效时间
- **Status**: `completed`
- **Completion Evidence**:
  - TR-I-5.1 通过：`test_coupon_range_valid_from_blocks_early_verify`（409）
- **Priority**: medium
- **Depends On**: None
- **Discovered By**: Review R1 (F5)
- **Description**:
  - 核销前校验 `valid_from`，未生效返回 409
- **Acceptance Criteria Addressed**: AC-6
- **Test Requirements**:
  - `rule` TR-I-5.1: RANGE 卡券未到生效日核销被拒

## Issue I-6: 核销码数量未按购买数量计算（语义 TBD）
- **Status**: `completed`
- **Completion Evidence**:
  - TR-I-6.1 通过：`test_coupon_codes_multiplied_by_quantity`（2 件 × 3 次 = 6 码）
- **Priority**: medium
- **Depends On**: None
- **Discovered By**: Review R1 (F6)
- **Description**:
  - 按 `sum(verify_count × quantity)` 生成核销码；契约补 TBD 说明（部分核销退款规则未定）
- **Acceptance Criteria Addressed**: AC-5
- **Test Requirements**:
  - `rule` TR-I-6.1: 购买 2 件、每件 3 次核销的卡券订单生成 6 个码

## Issue I-7: 下单未校验履约方式 + 建单商家分账未含配送费
- **Status**: `completed`
- **Completion Evidence**:
  - TR-I-7.1 通过：`test_order_type_must_match_product_delivery_types`（409）；TR-I-7.2 通过：`test_delivery_fee_included_in_merchant_income`
- **Priority**: low
- **Depends On**: None
- **Discovered By**: Review R1 (F7)
- **Description**:
  - 下单校验所选 order_type 对应履约方式在商品 delivery_types 中，否则 409
  - 建单 `merchant_income_amount` 含 delivery_fee，与结算口径一致
- **Acceptance Criteria Addressed**: AC-9
- **Test Requirements**:
  - `rule` TR-I-7.1: PICKUP 专用商品下 STORE_DELIVERY 订单返回 409
  - `rule` TR-I-7.2: 配送订单建单时 merchant_income_amount 含配送费

## Issue I-8: 仲裁驳回绕过卡券待核销状态
- **Status**: `completed`
- **Priority**: high
- **Depends On**: None
- **Discovered By**: Review R2 (N-1)
- **Description**:
  - 卡券未履约完成（无结算项）时仲裁驳回改为 `MERCHANT_REJECT_BACK_TO_FULFILL`，其余仍 `ARBITRATION_REJECT`
- **Acceptance Criteria Addressed**: AC-7, AC-10
- **Test Requirements**:
  - `rule` TR-I-8.1: 卡券售后转仲裁、裁定用户责任后订单回到 PENDING_FULFILL 且可核销
- **Completion Evidence**:
  - TR-I-8.1 通过：`test_coupon_arbitration_reject_returns_to_pending_fulfill`

## Issue I-9: 已完成卡券部分售后审批失败
- **Status**: `completed`
- **Priority**: medium
- **Depends On**: None
- **Discovered By**: Review R2 (N-2)
- **Description**:
  - 退款守卫改为「卡券且无结算项」才要求全额，已完成卡券允许部分退款
- **Acceptance Criteria Addressed**: AC-10
- **Test Requirements**:
  - `rule` TR-I-9.1: 全部核销后的卡券订单可提交部分售后
- **Completion Evidence**:
  - TR-I-9.1 通过：`test_completed_coupon_allows_partial_after_sale`；原 `test_coupon_partial_refund_rejected_before_verify` 仍通过

## Issue I-10: 多卡券商品共用首个有效期
- **Status**: `completed`
- **Priority**: low
- **Depends On**: None
- **Discovered By**: Review R2 (N-4)
- **Description**:
  - 按商品快照分组生成核销码，每组使用各自 valid_type/valid_days
- **Acceptance Criteria Addressed**: AC-5, AC-6
- **Test Requirements**:
  - `rule` TR-I-10.1: 同单两种卡券（7 天 3 次 / 30 天 2 次）生成 5 码且有效期分别为 7/30 天
- **Completion Evidence**:
  - TR-I-10.1 通过：`test_coupon_codes_use_each_product_validity`

## Issue I-11: ProductTemplate 响应 schema 缺字段
- **Status**: `completed`
- **Priority**: low
- **Depends On**: None
- **Discovered By**: Review R2 (N-5)
- **Description**:
  - 契约 ProductTemplate 补 acceptance_required、valid_type/valid_days/valid_from/valid_to、usable_weekdays、exclude_holidays、verify_count
- **Acceptance Criteria Addressed**: AC-11
- **Test Requirements**:
  - `rule` TR-I-11.1: schema-check 通过且字段与实现一致
- **Completion Evidence**:
  - TR-I-11.1 通过：`make schema-check` 通过；schema.d.ts 已重新生成

## Issue I-12: 部分核销后超额退款规则未定义
- **Status**: `completed`
- **Priority**: low
- **Depends On**: None
- **Discovered By**: Review R2 (N-3)
- **Description**:
  - 规则 TBD：在契约 `verify_count` 描述中标注「部分核销后的退款金额规则待确认」，不臆造规则
- **Acceptance Criteria Addressed**: AC-10
- **Test Requirements**:
  - `rule` TR-I-12.1: 契约存在 TBD 说明且 contract-check 通过
- **Completion Evidence**:
  - TR-I-12.1 通过：p0-api.yaml verify_count description 含 TBD，contract-check 通过

## Issue I-13: 部分核销后的退款金额比例（原 TBD）
- **Status**: `completed`
- **Priority**: high
- **Depends On**: None
- **Discovered By**: Review R3 (A4) / 用户指定处理
- **Description**:
  - 规则落地：待核销卡券可退金额 = 实付 × 未核销码数 ÷ 总码数（向下取整）
  - 部分退款成功后作废剩余 ACTIVE 码，订单按已核销部分 COMPLETED 并生成结算项
  - 契约移除 TBD，写入规则
- **Acceptance Criteria Addressed**: AC-7, AC-10
- **Test Requirements**:
  - `rule` TR-I-13.1: 3 码核销 1 个后可退 = 实付×2÷3；申请全额被拒 409
  - `rule` TR-I-13.2: 按可退金额申请并商户同意后，剩余 2 码 INVALID、订单 COMPLETED、结算项 refund_amount 一致
- **Completion Evidence**:
  - TR-I-13.1/13.2 通过：`test_partially_verified_coupon_refunds_unverified_portion`

## Issue I-14: RANGE 卡券过期后仍可下单（原 TBD）
- **Status**: `completed`
- **Priority**: medium
- **Depends On**: None
- **Discovered By**: Review R3 (A4) / 用户指定处理
- **Description**:
  - 下单校验：COUPON 且 valid_type=RANGE 且 valid_to 已过 → 409 PRODUCT_NOT_AVAILABLE
- **Acceptance Criteria Addressed**: AC-3
- **Test Requirements**:
  - `rule` TR-I-14.1: 过期 RANGE 卡券下单返回 409
- **Completion Evidence**:
  - TR-I-14.1 通过：`test_expired_range_coupon_cannot_be_ordered`
