<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, ApiError, type Page, type WithdrawalRow } from '../api'

const rows = ref<WithdrawalRow[]>([])
const page = ref<Page>({ page: 1, page_size: 20, total: 0, has_more: false })
const status = ref('')
const loading = ref(false)
const error = ref('')
const paying = ref<WithdrawalRow | null>(null)
const rejecting = ref<WithdrawalRow | null>(null)
const voucherNo = ref('')
const voucherUrl = ref('https://example.com/voucher.png')
const paidAt = ref(new Date().toISOString())
const rejectReason = ref('')
const submitting = ref(false)

async function load(target = 1) {
  loading.value = true
  error.value = ''
  try {
    const result = await api.withdrawals({ status: status.value, page: target, page_size: 20 })
    rows.value = result.items
    page.value = result.page
  } catch (exc) {
    error.value = exc instanceof ApiError ? exc.message : '加载失败'
  } finally {
    loading.value = false
  }
}

function openPayout(row: WithdrawalRow) {
  paying.value = row
  voucherNo.value = ''
}

async function submitPayout() {
  if (!paying.value || !voucherNo.value.trim()) return
  submitting.value = true
  error.value = ''
  try {
    await api.payoutWithdrawal(paying.value.id, {
      voucher_no: voucherNo.value.trim(),
      voucher_url: voucherUrl.value.trim(),
      paid_at: paidAt.value,
    })
    paying.value = null
    await load(page.value.page)
  } catch (exc) {
    error.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '打款失败'
  } finally {
    submitting.value = false
  }
}

async function submitReject() {
  if (!rejecting.value || !rejectReason.value.trim()) return
  submitting.value = true
  error.value = ''
  try {
    await api.rejectWithdrawal(rejecting.value.id, rejectReason.value.trim())
    rejecting.value = null
    rejectReason.value = ''
    await load(page.value.page)
  } catch (exc) {
    error.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '驳回失败'
  } finally {
    submitting.value = false
  }
}

onMounted(() => load())
</script>

<template>
  <h1>提现处理</h1>
  <div class="toolbar">
    <label class="field">
      <span>状态</span>
      <select v-model="status">
        <option value="">全部</option>
        <option v-for="value in ['REQUESTED', 'APPROVED', 'PAYING', 'PAID', 'REJECTED', 'FAILED']" :key="value" :value="value">
          {{ value }}
        </option>
      </select>
    </label>
    <button class="primary" :disabled="loading" @click="load()">查询</button>
  </div>
  <div v-if="error" class="error">{{ error }}</div>
  <div class="card" style="padding: 0">
    <table>
      <thead>
        <tr>
          <th>提现单号</th>
          <th>商户</th>
          <th>金额</th>
          <th>实付</th>
          <th>状态</th>
          <th>申请时间</th>
          <th>回单号</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.id">
          <td>{{ row.withdrawal_no }}</td>
          <td>#{{ row.merchant_id }}</td>
          <td>{{ (row.amount / 100).toFixed(2) }}</td>
          <td>{{ (row.net_amount / 100).toFixed(2) }}</td>
          <td><span class="tag" :class="{ ok: row.status === 'PAID', danger: row.status === 'REJECTED' }">{{ row.status }}</span></td>
          <td>{{ row.requested_at ?? '-' }}</td>
          <td>{{ row.voucher_no || '-' }}</td>
          <td>
            <button
              class="text"
              :disabled="!['REQUESTED', 'APPROVED', 'PAYING'].includes(row.status)"
              @click="openPayout(row)"
            >
              打款
            </button>
            <button
              class="danger"
              style="margin-left: 8px"
              :disabled="!['REQUESTED', 'APPROVED', 'PAYING'].includes(row.status)"
              @click="rejecting = row; rejectReason = ''"
            >
              驳回
            </button>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-if="!rows.length" class="empty">{{ loading ? '加载中…' : '暂无提现单' }}</div>
  </div>
  <div class="pager">
    <button class="text" :disabled="page.page <= 1" @click="load(page.page - 1)">上一页</button>
    <span>第 {{ page.page }} 页 · 共 {{ page.total }} 条</span>
    <button class="text" :disabled="!page.has_more" @click="load(page.page + 1)">下一页</button>
  </div>

  <div v-if="paying" class="modal-mask" @click.self="paying = null">
    <div class="modal">
      <h2>确认打款 · {{ paying.withdrawal_no }}</h2>
      <label class="field"><span>银行回单号</span><input v-model="voucherNo" placeholder="必填" /></label>
      <label class="field"><span>回单地址</span><input v-model="voucherUrl" /></label>
      <label class="field"><span>打款时间</span><input v-model="paidAt" /></label>
      <div class="toolbar" style="margin: 0">
        <button class="primary" :disabled="submitting || !voucherNo.trim()" @click="submitPayout">确认打款</button>
        <button class="text" @click="paying = null">取消</button>
      </div>
    </div>
  </div>

  <div v-if="rejecting" class="modal-mask" @click.self="rejecting = null">
    <div class="modal">
      <h2>驳回提现 · {{ rejecting.withdrawal_no }}</h2>
      <label class="field"><span>驳回原因</span><textarea v-model="rejectReason" rows="3" placeholder="必填" /></label>
      <div class="toolbar" style="margin: 0">
        <button class="primary" :disabled="submitting || !rejectReason.trim()" @click="submitReject">确认驳回</button>
        <button class="text" @click="rejecting = null">取消</button>
      </div>
    </div>
  </div>
</template>
