<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, ApiError, type AdminOrderRow, type Page } from '../api'

const rows = ref<AdminOrderRow[]>([])
const page = ref<Page>({ page: 1, page_size: 20, total: 0, has_more: false })
const status = ref('')
const orderNo = ref('')
const loading = ref(false)
const error = ref('')
const actionOrder = ref<AdminOrderRow | null>(null)
const actionType = ref<'FREEZE' | 'UNFREEZE'>('FREEZE')
const reason = ref('')
const submitting = ref(false)

async function load(target = 1) {
  loading.value = true
  error.value = ''
  try {
    const result = await api.adminOrders({
      status: status.value,
      order_no: orderNo.value,
      page: target,
      page_size: 20,
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

onMounted(() => load())
</script>

<template>
  <h1>订单监控</h1>
  <div class="toolbar">
    <label class="field">
      <span>状态</span>
      <select v-model="status">
        <option value="">全部</option>
        <option v-for="value in ['PENDING_PAYMENT', 'PENDING_ACCEPT', 'PENDING_FULFILL', 'FULFILLING', 'COMPLETED', 'AFTER_SALE', 'REFUNDING', 'REFUNDED', 'CLOSED']" :key="value" :value="value">
          {{ value }}
        </option>
      </select>
    </label>
    <label class="field">
      <span>订单号</span>
      <input v-model="orderNo" placeholder="模糊搜索" />
    </label>
    <button class="primary" :disabled="loading" @click="load()">查询</button>
  </div>

  <div v-if="error" class="error">{{ error }}</div>
  <div class="card" style="padding: 0">
    <table>
      <thead>
        <tr>
          <th>订单号</th>
          <th>商户</th>
          <th>类型</th>
          <th>状态</th>
          <th>实付</th>
          <th>已退</th>
          <th>创建时间</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.id">
          <td>{{ row.order_no }}</td>
          <td>{{ row.merchant_name }}</td>
          <td>{{ row.order_type }}</td>
          <td><span class="tag">{{ row.status }}</span></td>
          <td>{{ (row.paid_amount / 100).toFixed(2) }}</td>
          <td>{{ (row.refunded_amount / 100).toFixed(2) }}</td>
          <td>{{ row.created_at }}</td>
          <td>
            <button class="text" @click="openAction(row, 'FREEZE')">冻结</button>
            <button class="text" style="margin-left: 8px" @click="openAction(row, 'UNFREEZE')">解冻</button>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-if="!rows.length" class="empty">{{ loading ? '加载中…' : '暂无订单' }}</div>
  </div>
  <div class="pager">
    <button class="text" :disabled="page.page <= 1" @click="load(page.page - 1)">上一页</button>
    <span>第 {{ page.page }} 页 · 共 {{ page.total }} 条</span>
    <button class="text" :disabled="!page.has_more" @click="load(page.page + 1)">下一页</button>
  </div>

  <div v-if="actionOrder" class="modal-mask" @click.self="actionOrder = null">
    <div class="modal">
      <h2>{{ actionType === 'FREEZE' ? '冻结结算' : '解冻结算' }}</h2>
      <div class="field">
        <span>订单号</span>
        <input :value="actionOrder.order_no" disabled />
      </div>
      <label class="field">
        <span>原因</span>
        <textarea v-model="reason" rows="3" placeholder="必填" />
      </label>
      <div class="toolbar" style="margin: 0">
        <button class="primary" :disabled="submitting || !reason.trim()" @click="submitAction">确认</button>
        <button class="text" @click="actionOrder = null">取消</button>
      </div>
    </div>
  </div>
</template>
