# 商品类型扩展与商户行业字段 - 产品需求文档

## Overview
- **Summary**: 扩展异业联盟商城的商品类型体系，新增「卡券核销商品」类型与「门店配送」履约方式，为实物商品增加接单可配置、配送费支持；同时为商户新增「行业」字段用于后台归类与统计。
- **Purpose**: 支撑酒店民宿（到店服务需商户审核）、卡券核销（直接出码、灵活有效期）、实物配送等多业态场景，并提供商户行业维度的后台运营能力。
- **Target Users**: 平台运营人员（后台）、商户（商品发布/订单履约）、消费者（下单/核销）。

## Goals
- 商户表新增「行业」字段，仅后台可见，支持按行业筛选与归类。
- 商品类型扩展为三类：实物商品（PHYSICAL）、到店服务（SERVICE）、卡券核销（COUPON）。
- 履约方式新增「门店配送」（STORE_DELIVERY）。
- 实物商品可配置是否需要商户接单。
- 配送费支持（规则从简：商户级固定配送费）。
- 卡券商品支付后直达待核销，生成 N 个独立核销码，支持灵活有效期与可用规则。
- 卡券商品允许售后退款。

## Non-Goals
- 不做动态行业字典管理（本期用枚举，含 OTHER 兜底）。
- 不做节假日系统判断（节假日不可用仅作为商品文案提示，由商户核销人员人工判断）。
- 不做配送范围、起送价、阶梯配送费等复杂配送规则。
- 不做卡券转赠、分享裂变。
- 不做多间夜/多份预约扩展（酒店场景沿用现有 Appointment 单时段模型）。

## Background & Context
- 现有 `Product.Type`：PHYSICAL / SERVICE；`Product.DeliveryType`：EXPRESS / PICKUP / VERIFY / APPOINTMENT。
- 现有订单状态机：PAY_SUCCESS 后所有订单进入 PENDING_ACCEPT（待接单）。
- 现有核销码：支付后为 PICKUP/SERVICE 订单生成 1 个核销码，有效期取商品 `verify_days`（天）。
- 现有 `Merchant` 有 `category`（主营类目，FK 到商品类目），无独立行业字段。
- 现有 `Order.delivery_fee` 字段存在，但创建订单时硬编码为 0。
- 硬规则：订单状态只能经 `transit_order` 变更；余额只能经 `post_transaction` 变更；金额存分。

## Functional Requirements

**商户行业**
- **FR-1**: Merchant 新增 `industry` 字段（枚举：餐饮/酒店民宿/美容美发/健身运动/零售/生活服务/其他），默认 OTHER，仅后台接口返回，消费者端不暴露。
- **FR-2**: 后台商户列表支持按 `industry` 筛选。

**商品类型与履约**
- **FR-3**: `Product.Type` 新增 `COUPON`（卡券核销）。
- **FR-4**: `Product.DeliveryType` 新增 `STORE_DELIVERY`（门店配送）。
- **FR-5**: 实物商品（PHYSICAL）支持 `PICKUP` / `EXPRESS` / `STORE_DELIVERY`；服务商品（SERVICE）支持 `VERIFY` / `APPOINTMENT`；卡券商品（COUPON）仅支持 `VERIFY`。
- **FR-6**: 实物商品新增 `acceptance_required`（是否需要商户接单）布尔字段，默认 True。
- **FR-7**: 商户新增 `delivery_fee`（配送费，分）字段，默认 0；配送类订单（EXPRESS/STORE_DELIVERY）下单时取商户 `delivery_fee` 计入订单 `delivery_fee`。

**卡券商品字段**
- **FR-8**: 卡券商品新增有效期配置：`valid_type`（DAYS 天有效 / PERMANENT 永久 / RANGE 固定时间段），配套 `valid_days` / `valid_from` / `valid_to`。
- **FR-9**: 卡券商品新增 `usable_weekdays`（可用星期，JSON 列表，1-7，空=不限制）与 `exclude_holidays`（法定节假日不可用，布尔，仅文案提示）。
- **FR-10**: 卡券商品新增 `verify_count`（可核销次数，正整数，默认 1）。

**订单与状态机**
- **FR-11**: 卡券订单支付成功后，跳过 PENDING_ACCEPT，直接进入 PENDING_FULFILL，履约状态置为 VERIFY_READY，并按 `verify_count` 生成 N 个独立核销码。
- **FR-12**: 实物订单：`acceptance_required=True` 时支付后进入 PENDING_ACCEPT；`False` 时直接进入 PENDING_FULFILL。
- **FR-13**: 服务订单：保持 PENDING_ACCEPT（商户审核），商户拒绝走 REFUNDING → 原路退款（现有能力，确认闭环）。
- **FR-14**: 核销码有效期按商品 `valid_type` 计算：DAYS → 支付时间+N天；PERMANENT → 不过期（valid_to=null）；RANGE → 商品配置的 valid_from/valid_to。
- **FR-15**: 卡券订单多次核销：每次核销一个独立码，最后一个码核销完成时订单转为 COMPLETED。
- **FR-16**: 卡券订单允许发起售后（未核销/部分核销可退），走现有售后流程。

## Non-Functional Requirements
- **NFR-1**: 订单状态迁移只能经 `transit_order`，不新增旁路。
- **NFR-2**: 金额（配送费、商品价）一律存分，禁止 float。
- **NFR-3**: 核销码生成必须幂等（同一订单不重复生成）。
- **NFR-4**: 所有表结构变更必须生成迁移并提交。
- **NFR-5**: 契约 `p0-api.yaml` 与 `openapi.yaml` 同步更新。

## Constraints
- **Technical**: Django 4.2 + DRF；SQLite 开发 / MySQL 8 生产；Asia/Shanghai 时区。
- **Business**: 佣金率仍走 category/commission_rate，行业不影响佣金。
- **Dependencies**: 依赖现有订单状态机、核销码模型、售后流程。

## Assumptions
- 实物商品 `acceptance_required` 默认 True（保留现有商户接单行为）。
- 卡券商品 `acceptance_required` 强制 False（无需商户接单）。
- 服务商品 `acceptance_required` 强制 True（商户审核）。
- 配送费取商户级固定值，0 表示免配送费。
- 卡券核销码每个独立有效，互不影响；部分核销后剩余码仍可核销。

## Acceptance Criteria

### AC-1: 商户行业字段仅后台可见
- **Type**: `rule`
- **Given**: 商户存在 industry 字段
- **When**: 消费者端请求商户详情/列表
- **Then**: 响应中不包含 industry 字段
- **Pass Condition**: 消费者端序列化器 fields 不含 industry；后台序列化器含 industry
- **Evidence**: 代码审查 + 接口测试

### AC-2: 后台商户按行业筛选
- **Type**: `rule`
- **Given**: 存在不同行业的商户
- **When**: 后台 GET /admin/merchants/?industry=RESTAURANT
- **Then**: 仅返回行业为餐饮的商户
- **Pass Condition**: 列表过滤生效
- **Evidence**: 接口测试

### AC-3: 卡券商品类型存在且履约方式受限
- **Type**: `rule`
- **Given**: 创建 type=COUPON 的商品
- **When**: delivery_types 包含非 VERIFY 值
- **Then**: 序列化器校验拒绝
- **Pass Condition**: COUPON 仅允许 VERIFY
- **Evidence**: 序列化器单测

### AC-4: 实物商品接单可配置
- **Type**: `rule`
- **Given**: 实物商品 acceptance_required=False
- **When**: 用户支付该商品订单
- **Then**: 订单直接进入 PENDING_FULFILL（跳过 PENDING_ACCEPT）
- **Pass Condition**: 支付后状态 = PENDING_FULFILL
- **Evidence**: 订单流程测试

### AC-5: 卡券订单支付直达待核销并生成 N 个码
- **Type**: `rule`
- **Given**: 卡券商品 verify_count=3
- **When**: 用户支付成功
- **Then**: 订单状态=PENDING_FULFILL，履约状态=VERIFY_READY，生成 3 个 ACTIVE 核销码
- **Pass Condition**: VerifyCode 记录数 = 3 且 status=ACTIVE
- **Evidence**: 订单流程测试

### AC-6: 核销码有效期按 valid_type 计算
- **Type**: `rule`
- **Given**: 卡券商品 valid_type=DAYS, valid_days=7
- **When**: 支付成功生成核销码
- **Then**: 核销码 valid_to = 支付时间 + 7 天
- **Pass Condition**: valid_to 时间差在 7 天 ± 1 分钟
- **Evidence**: 单元测试

### AC-7: 卡券最后一次核销完成订单
- **Type**: `rule`
- **Given**: 卡券订单有 3 个核销码，已核销 2 个
- **When**: 核销第 3 个码
- **Then**: 订单状态转为 COMPLETED
- **Pass Condition**: 第 3 次核销后 order.status=COMPLETED
- **Evidence**: 核销流程测试

### AC-8: 服务订单商户拒单自动退款
- **Type**: `rule`
- **Given**: 服务订单处于 PENDING_ACCEPT
- **When**: 商户执行拒绝
- **Then**: 订单进入 REFUNDING 并触发原路退款
- **Pass Condition**: 退款单创建且订单最终 REFUNDED
- **Evidence**: 退款闭环测试（确认现有能力）

### AC-9: 配送费从商户配置计入订单
- **Type**: `rule`
- **Given**: 商户 delivery_fee=500（5元），实物商品走 STORE_DELIVERY
- **When**: 创建订单
- **Then**: order.delivery_fee=500，payable_amount 含配送费
- **Pass Condition**: 订单 delivery_fee 字段 = 商户配置值
- **Evidence**: 订单创建测试

### AC-10: 卡券订单允许售后
- **Type**: `rule`
- **Given**: 已支付的卡券订单（未核销或部分核销）
- **When**: 用户发起售后
- **Then**: 售后单创建成功，订单进入 AFTER_SALE
- **Pass Condition**: 售后流程可正常创建
- **Evidence**: 售后流程测试

### AC-11: 契约与迁移完整性
- **Type**: `rule`
- **Given**: 实现完成
- **When**: 运行 make verify
- **Then**: 全绿（lint/check/schema-check/contract-check/test）
- **Pass Condition**: make verify exit 0
- **Evidence**: CI 日志

## Open Questions
- 无（用户已确认全部 TBD：实物接单可配置、N 个独立码、节假日仅文案、配送费从简、卡券允许售后）
