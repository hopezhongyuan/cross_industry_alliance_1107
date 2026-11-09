<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, ApiError, type AdminOrderDetail, type AdminOrderRow, type Page } from '../api'
import ModalShell from '../components/ModalShell.vue'
import PageHeader from '../components/PageHeader.vue'
import PaginationBar from '../components/PaginationBar.vue'
import StatusTag from '../components/StatusTag.vue'
import { formatDateTime, formatMoney } from '../format'

const ORDER_STATUS: Record<string, string> = {
  PENDING_PAYMENT: '待支付',
  PENDING_ACCEPT: '待接单',
  PENDING_FULFILL: '待履约',
  FULFILLING: '履约中',
  COMPLETED: '已完成',
  AFTER_SALE: '售后中',
  REFUNDING: '退款中',
  REFUNDED: '已退款',
  CLOSED: '已关闭',
}

const route = useRoute()
const router = useRouter()
const rows = ref<AdminOrderRow[]>([])
const page = ref<Page>({ page: 1, page_size: 20, total: 0, has_more: false })
const status = ref(String(route.query.status ?? ''))
const orderNo = ref(String(route.query.order_no ?? ''))
const loading = ref(false)
const error = ref('')
const actionOrder = ref<AdminOrderRow | null>(null)
const actionType = ref<'FREEZE' | 'UNFREEZE'>('FREEZE')
const reason = ref('')
const submitting = ref(false)
const detail = ref<AdminOrderDetail | null>(null)
const detailLoading = ref(false)
const detailError = ref('')

async function load(target = 1, size = page.value.page_size) {
  loading.value = true
  error.value = ''
  router.replace({
    query: {
      ...(status.value ? { status: status.value } : {}),
      ...(orderNo.value ? { order_no: orderNo.value } : {}),
      ...(target > 1 ? { page: String(target) } : {}),
    },
  })
  try {
    const result = await api.adminOrders({
      status: status.value,
      order_no: orderNo.value,
      page: target,
      page_size: size,
    })
    rows.value = result.items
    page.value = result.page
  } catch (exc) {
    error.value = exc instanceof ApiError ? exc.message : '加载失败'
  } finally {
    loading.value = false
  }
}

function openAction(row: AdminOrderRow, type: 'FREEZE' | 'UNFREEZE') {
  actionOrder.value = row
  actionType.value = type
  reason.value = ''
}

async function openDetail(row: AdminOrderRow) {
  detail.value = null
  detailError.value = ''
  detailLoading.value = true
  try {
    detail.value = await api.adminOrderDetail(row.id)
  } catch (exc) {
    detailError.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '加载订单详情失败'
  } finally {
    detailLoading.value = false
  }
}

function rateText(rate: number): string {
  return `${(rate * 100).toFixed(1)}%`
}

async function submitAction() {
  if (!actionOrder.value || !reason.value.trim()) return
  submitting.value = true
  error.value = ''
  try {
    await api.freezeOrder(actionOrder.value.id, actionType.value, reason.value.trim())
    actionOrder.value = null
    await load(page.value.page)
  } catch (exc) {
    error.value = exc instanceof ApiError ? exc.message : '操作失败'
  } finally {
    submitting.value = false
  }
}

onMounted(() => load(Number(route.query.page ?? 1)))
</script>

<template>
  <PageHeader title="订单监控" description="全平台订单检索与结算冻结；每笔订单有且仅有一个结算项。" />
  <div class="toolbar">
    <label class="field">
      <span>状态</span>
      <select v-model="status" @change="load(1)">
        <option value="">全部状态</option>
        <option v-for="(label, value) in ORDER_STATUS" :key="value" :value="value">{{ label }}</option>
      </select>
    </label>
    <label class="field">
      <span>订单号</span>
      <input v-model="orderNo" name="order_no" autocomplete="off" placeholder="输入订单号…" aria-label="订单号搜索" @keyup.enter="load(1)" />
    </label>
    <button class="primary" :disabled="loading" @click="load(1)">查询</button>
    <button class="outline" @click="orderNo = ''; status = ''; load(1)">重置</button>
  </div>

  <div v-if="error" class="error" role="alert">{{ error }}</div>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>订单号</th>
          <th>商户</th>
          <th>类型</th>
          <th>状态</th>
          <th class="money">实付</th>
          <th class="money">已退</th>
          <th>创建时间</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.id">
          <td>{{ row.order_no }}</td>
          <td>{{ row.merchant_name }}</td>
          <td>{{ row.order_type }}</td>
          <td><StatusTag :status="row.status" /></td>
          <td class="money">{{ formatMoney(row.paid_amount) }}</td>
          <td class="money">{{ formatMoney(row.refunded_amount) }}</td>
          <td>{{ formatDateTime(row.created_at) }}</td>
          <td>
            <div class="actions">
              <button class="text" @click="openDetail(row)">详情</button>
              <button class="text" @click="openAction(row, 'FREEZE')">冻结</button>
              <button class="text" @click="openAction(row, 'UNFREEZE')">解冻</button>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-if="!rows.length" class="empty">{{ loading ? '加载中…' : '暂无订单' }}</div>
  </div>
  <PaginationBar
    :page="page.page"
    :page-size="page.page_size"
    :total="page.total"
    @change="(payload) => load(payload.page, payload.pageSize)"
  />

  <ModalShell v-if="detailLoading || detail || detailError" title="订单详情" wide @close="detail = null; detailError = ''">
    <template v-if="detailLoading">
      <h2>订单详情</h2>
      <div class="muted">加载中…</div>
    </template>
    <template v-else-if="detailError">
      <h2>加载失败</h2>
      <div class="error" role="alert">{{ detailError }}</div>
      <button class="text" @click="detailError = ''">关闭</button>
    </template>
    <template v-else-if="detail">
      <h2>订单详情 · {{ detail.order_no }}</h2>
      <div class="detail-grid">
        <span>商户</span><b>{{ detail.merchant_name }}</b>
        <span>状态</span><b>{{ detail.status }}</b>
        <span>商品实付</span><b>{{ formatMoney(detail.product_amount) }}</b>
        <span>配送费</span><b>{{ formatMoney(detail.delivery_fee) }}</b>
        <span>已退款</span><b>{{ formatMoney(detail.refunded_amount) }}</b>
        <span>佣金率</span><b>{{ rateText(detail.commission_rate) }}</b>
        <span>平台分账</span><b>{{ formatMoney(detail.platform_income_amount) }}</b>
        <span>商家分账</span><b>{{ formatMoney(detail.merchant_income_amount) }}</b>
        <span>平台承担退款</span><b>{{ formatMoney(detail.platform_refund_amount) }}</b>
        <span>商家承担退款</span><b>{{ formatMoney(detail.merchant_refund_amount) }}</b>
      </div>

      <div class="section-title">商品行分账</div>
      <div class="card" style="padding: 0; overflow-x: auto">
        <table>
          <thead>
            <tr>
              <th>商品</th>
              <th class="money">数量</th>
              <th class="money">行实付</th>
              <th class="money">平台佣金</th>
              <th class="money">商家应得</th>
              <th class="money">退款</th>
              <th class="money">退款后平台</th>
              <th class="money">退款后商家</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in detail.items" :key="item.id">
              <td>{{ item.title }}</td>
              <td class="money">{{ item.quantity }}</td>
              <td class="money">{{ formatMoney(item.paid_amount) }}</td>
              <td class="money">{{ formatMoney(item.platform_amount) }}</td>
              <td class="money">{{ formatMoney(item.merchant_amount) }}</td>
              <td class="money">{{ formatMoney(item.refund_amount) }}</td>
              <td class="money">{{ formatMoney(item.platform_net_amount) }}</td>
              <td class="money">{{ formatMoney(item.merchant_net_amount) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="muted">规则：平台佣金按商品实付计算，配送费 100% 归商家；退款按行冲回。</div>
      <div class="toolbar" style="margin: 0">
        <button class="text" @click="detail = null">关闭</button>
      </div>
    </template>
  </ModalShell>

  <ModalShell v-if="actionOrder" :title="actionType === 'FREEZE' ? '冻结结算' : '解冻结算'" @close="actionOrder = null">
    <h2>{{ actionType === 'FREEZE' ? '冻结结算' : '解冻结算' }}</h2>
    <div class="field">
      <span>订单号</span>
      <input :value="actionOrder.order_no" disabled />
    </div>
    <label class="field">
      <span>原因</span>
      <textarea v-model="reason" rows="3" placeholder="请填写冻结原因…" />
    </label>
    <div class="toolbar" style="margin: 0">
      <button class="primary" :disabled="submitting || !reason.trim()" @click="submitAction">确认</button>
      <button class="text" @click="actionOrder = null">取消</button>
    </div>
  </ModalShell>
</template>
