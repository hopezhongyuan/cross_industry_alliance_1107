# 商品类型扩展与商户行业字段 - 独立评审

- [x] CP-R1: 消费者端商户接口不返回 industry；后台接口返回且支持按 industry 筛选
  - **Type**: `rule`
  - **Covers**: AC-1, AC-2
  - **Evidence**: `apps/merchants/test_industry.py` 5 项通过；Store/Merchant 序列化器 fields 审查

- [x] CP-R2: COUPON 商品仅允许 VERIFY，卡券有效期配置非法时校验拒绝
  - **Type**: `rule`
  - **Covers**: AC-3
  - **Evidence**: `apps/catalog/test_product_types.py` 6 项通过

- [x] CP-R3: 卡券支付直达待核销并生成 N 个独立码；免接单实物直达待履约；需接单实物进入待接单
  - **Type**: `rule`
  - **Covers**: AC-4, AC-5, AC-6
  - **Evidence**: `apps/orders/test_product_types.py` 通过；`_generate_coupon_codes` 幂等

- [x] CP-R4: 卡券最后一次核销完成订单；卡券未核销可售后；服务拒单退款闭环
  - **Type**: `rule`
  - **Covers**: AC-7, AC-8, AC-10
  - **Evidence**: `test_coupon_verify_completes_on_last_code`、`test_coupon_order_allows_after_sale_before_verify`、`test_coupon_arbitration_reject_returns_to_pending_fulfill`、`test_m2_flow.py` 拒单退款

- [x] CP-R5: 配送类订单按商户配送费计费，金额全为整数分
  - **Type**: `rule`
  - **Covers**: AC-9
  - **Evidence**: `test_store_delivery_charges_merchant_delivery_fee`、`test_pickup_has_no_delivery_fee`；`delivery_fee` 为 BigIntegerField

- [x] CP-R6: make verify 全绿且 CI success
  - **Type**: `rule`
  - **Covers**: AC-11
  - **Evidence**: 本地 270 passed / 91.72%；CI run 42728320098 success（首版），最终提交 39396e3 由 CI 复跑

## Review History

### Review R1
- **Result**: `fail`
- **Evidence**: 独立评审者阅读 11 个后端文件与契约片段，运行新增测试 14 passed、`make verify` 258 passed；AC-1..AC-11 字面检查通过，但发现 5 项 actionable 缺陷。
- **Findings**:
  - F1（High，actionable）：卡券核销分支未校验订单状态，售后中仍可核销，且单码卡券会触发 `InvalidTransition` → 500。
  - F2（High，actionable）：卡券履约完成前部分退款会迁到 COMPLETED 但不建结算项、不作废剩余码，导致资金悬空且再核销 500。
  - F3（High，actionable）：商品模板侧 `allowed` 矩阵缺 COUPON 导致 KeyError 500，STORE_DELIVERY 被误拒；模板卡券字段未透传，与 `p0-api.yaml` 不一致。
  - F4（Medium，actionable）：免接单实物订单履约状态被置为 VERIFY_READY，应为 NOT_STARTED/PICKUP_READY。
  - F5（Medium，actionable）：核销未校验 `valid_from`，RANGE 卡券生效前可核销。
  - F6（Medium，advisory）：`verify_count` 未乘购买数量，多商品组合仅取首个快照，语义未定义。
  - F7（Advisory）：下单未校验订单类型是否在商品 delivery_types 内；建单时 `merchant_income_amount` 未含配送费。
- **Recommended Issues**: I-1..I-7，见 tasks.md

### Review R2
- **Result**: `fail`
- **Evidence**: 评审者阅读 bedeb19 全量 diff，运行 `pytest apps/{orders,catalog,merchants,payments,aftersales}` 与 `make verify`（267 passed / 91.66%）。I-1..I-5、I-7 判定 fixed；I-6 部分 fixed（数量已乘，但多张不同卡券共用首个有效期）。
- **Findings**:
  - N-1（High，actionable）：仲裁驳回对卡券订单走 `ARBITRATION_REJECT → COMPLETED`，绕过待核销状态，剩余码无法核销、货款滞留。
  - N-2（Medium，actionable）：已完成卡券订单可提交部分售后申请，但商户同意时被全额退款守卫拦截（申请可建、审批必败）。
  - N-3（Medium，advisory）：部分核销后仍按全额退款，已消费码不扣减（规则 TBD，已在契约标注）。
  - N-4（Low，actionable）：多张不同卡券同单时核销码有效期统一取首个快照。
  - N-5（Low，actionable）：ProductTemplate 响应 schema 缺 acceptance_required / valid_* / verify_count。
- **Recommended Issues**: I-8..I-12，见 tasks.md

### Review R3
- **Result**: `pass`
- **Evidence**: 评审者复查 39396e3，运行 `pytest apps/{aftersales,orders,payments}`（79 passed）、`apps/catalog`（39 passed）与 `make verify`（270 passed / 91.72%，lint/check/schema-check/contract-check 全绿）。
- **N-1 fixed**：卡券且无结算项时仲裁驳回改走 `MERCHANT_REJECT_BACK_TO_FULFILL`；实测部分核销 1/3 后仲裁驳回可继续核销至完成并生成结算项；已完成卡券仍走 `ARBITRATION_REJECT`。
- **N-2 fixed**：全额退款守卫下沉为「卡券且无结算项」；实测已完成卡券部分售后商户同意成功。
- **N-3 fixed**：部分核销退款规则以 TBD 标注，未臆造。
- **N-4 fixed**：核销码按商品快照分组，各自使用自身有效期（实测 5 码 7/30 天）。
- **N-5 fixed**：ProductTemplate 响应契约补齐新字段。
- **Advisory（不阻塞）**：
  - A1 `test_completed_coupon_allows_partial_after_sale` 未断言商户同意退款结果（行为已实测正确，测试可加强）。
  - A2 TBD 说明仅写于 Input schema 的 verify_count，ProductTemplate 响应描述未标。
  - A3 openapi.yaml 无模板响应 schema 属既有空白，非本次引入。
  - A4 既有范围外：部分核销后按全额退款（TBD）、RANGE 卡券过期商品仍可下单。
