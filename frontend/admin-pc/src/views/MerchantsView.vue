<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, ApiError, type AdminMerchantRow, type MerchantSummary } from '../api'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import PageHeader from '../components/PageHeader.vue'
import PaginationBar from '../components/PaginationBar.vue'
import StatusTag from '../components/StatusTag.vue'
import { formatMoney } from '../format'

const route = useRoute()
const router = useRouter()

const STATUS_OPTIONS = [
  { value: '', label: '全部状态' },
  { value: 'ACTIVE', label: '营业中' },
  { value: 'PENDING', label: '待审核' },
  { value: 'RESTING', label: '停业' },
  { value: 'BANNED', label: '已封禁' },
  { value: 'REJECTED', label: '审核驳回' },
]

const rows = ref<AdminMerchantRow[]>([])
const summary = ref<MerchantSummary>({ total: 0, active: 0, pending: 0, resting: 0, banned: 0, rejected: 0 })
const page = ref({ page: 1, page_size: 20, total: 0, has_more: false })
const status = ref(String(route.query.status ?? ''))
const keyword = ref(String(route.query.q ?? ''))
const loading = ref(false)
const error = ref('')
const message = ref('')

const actionRow = ref<AdminMerchantRow | null>(null)
const actionStatus = ref<'ACTIVE' | 'RESTING' | 'BANNED'>('RESTING')
const submitting = ref(false)

function formatRate(rate: number | null | undefined): string {
  return `${((rate ?? 0) * 100).toFixed(1)}%`
}

async function load(target = 1, size = page.value.page_size) {
  loading.value = true
  error.value = ''
  message.value = ''
  router.replace({
    query: {
      ...(status.value ? { status: status.value } : {}),
      ...(keyword.value.trim() ? { q: keyword.value.trim() } : {}),
      ...(target > 1 ? { page: String(target) } : {}),
    },
  })
  try {
    const result = await api.adminMerchants({
      status: status.value,
      q: keyword.value.trim(),
      page: target,
      page_size: size,
    })
    rows.value = result.items
    summary.value = result.summary
    page.value = result.page
  } catch (exc) {
    error.value = exc instanceof ApiError ? exc.message : '加载失败'
  } finally {
    loading.value = false
  }
}

function reset() {
  status.value = ''
  keyword.value = ''
  load(1)
}

function openAction(row: AdminMerchantRow, target: 'ACTIVE' | 'RESTING' | 'BANNED') {
  actionRow.value = row
  actionStatus.value = target
}

async function submitAction(reason: string) {
  if (!actionRow.value) return
  submitting.value = true
  error.value = ''
  try {
    await api.changeMerchantStatus(actionRow.value.id, actionStatus.value, reason)
    actionRow.value = null
    message.value = '商户状态已更新'
    await load(page.value.page)
  } catch (exc) {
    error.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '操作失败'
  } finally {
    submitting.value = false
  }
}

function actionTitle(): string {
  if (actionStatus.value === 'BANNED') return '封禁商户'
  if (actionStatus.value === 'RESTING') return '停业商户'
  return '恢复营业'
}

onMounted(() => load(Number(route.query.page ?? 1)))
</script>

<template>
  <PageHeader title="商户管理" description="平台商户检索、状态管理与定位维护；停业与封禁会立即停止新订单。">
    <template #actions>
      <button class="primary" @click="router.push('/merchants/new')">新建商户</button>
    </template>
  </PageHeader>

  <div class="metric-strip">
    <div class="metric"><small>商户总数</small><b>{{ summary.total }}</b></div>
    <div class="metric"><small>营业中</small><b>{{ summary.active }}</b></div>
    <div class="metric"><small>待审核</small><b>{{ summary.pending }}</b></div>
    <div class="metric"><small>停业 / 封禁</small><b>{{ summary.resting + summary.banned }}</b></div>
  </div>

  <div class="toolbar">
    <label class="field">
      <span>状态</span>
      <select v-model="status" @change="load(1)">
        <option v-for="item in STATUS_OPTIONS" :key="item.value" :value="item.value">{{ item.label }}</option>
      </select>
    </label>
    <label class="field">
      <span>关键词</span>
      <input v-model="keyword" name="q" autocomplete="off" placeholder="商户名称 / 编号 / 电话…" @keyup.enter="load(1)" />
    </label>
    <button class="primary" :disabled="loading" @click="load(1)">查询</button>
    <button class="outline" @click="reset">重置</button>
  </div>

  <div v-if="error" class="error" role="alert">{{ error }}</div>
  <div v-if="message" class="notice" aria-live="polite">{{ message }}</div>

  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>商户</th>
          <th>类目 / 区域</th>
          <th>状态</th>
          <th class="money">佣金率</th>
          <th class="money">今日订单</th>
          <th class="money">累计结算</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.id">
          <td class="cell-main">
            {{ row.name }}
            <div class="muted">{{ row.merchant_no }} · {{ row.contact_phone || '未留电话' }}</div>
          </td>
          <td>
            {{ row.category_name || '未分类' }}
            <div class="muted">{{ row.city }}{{ row.district }}</div>
          </td>
          <td><StatusTag :status="row.status" /></td>
          <td class="money">{{ formatRate(row.commission_rate) }}</td>
          <td class="money">{{ row.today_orders }}</td>
          <td class="money">{{ formatMoney(row.settled_amount) }}</td>
          <td>
            <div class="actions">
              <button class="text" @click="router.push(`/merchants/${row.id}`)">详情</button>
              <button
                v-if="row.status === 'PENDING' || row.status === 'REJECTED'"
                class="text"
                @click="router.push('/audits')"
              >
                去审核
              </button>
              <button v-if="row.status === 'ACTIVE'" class="text" @click="openAction(row, 'RESTING')">停业</button>
              <button v-if="row.status === 'ACTIVE'" class="danger" @click="openAction(row, 'BANNED')">封禁</button>
              <button
                v-if="row.status === 'RESTING' || row.status === 'BANNED'"
                class="text"
                @click="openAction(row, 'ACTIVE')"
              >
                {{ row.status === 'BANNED' ? '解除封禁' : '恢复营业' }}
              </button>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-if="!rows.length" class="empty">{{ loading ? '加载中…' : '该条件下暂无商户' }}</div>
  </div>

  <PaginationBar
    :page="page.page"
    :page-size="page.page_size"
    :total="page.total"
    @change="(payload) => load(payload.page, payload.pageSize)"
  />

  <ConfirmDialog
    v-if="actionRow"
    :title="actionTitle()"
    :message="`${actionRow.name} · ${actionStatus === 'ACTIVE' ? '恢复后商户可重新接单。' : '停业与封禁立即停止新订单；在途订单与售后不自动取消。'}`"
    reason-label="变更原因"
    reason-required
    :danger="actionStatus === 'BANNED'"
    :busy="submitting"
    @confirm="submitAction"
    @close="actionRow = null"
  />
</template>
