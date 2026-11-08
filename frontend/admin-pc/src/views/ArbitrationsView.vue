<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, ApiError, type ArbitrationDetail, type ArbitrationRow, type Page } from '../api'
import ModalShell from '../components/ModalShell.vue'
import { formatDateTime, formatMoney } from '../format'

const route = useRoute()
const router = useRouter()
const rows = ref<ArbitrationRow[]>([])
const page = ref<Page>({ page: 1, page_size: 20, total: 0, has_more: false })
const status = ref(String(route.query.status ?? ''))
const loading = ref(false)
const error = ref('')
const current = ref<ArbitrationRow | null>(null)
const liability = ref('MERCHANT')
const refundAmount = ref(0)
const ruling = ref('')
const submitting = ref(false)
const detail = ref<ArbitrationDetail | null>(null)
const detailError = ref('')

async function openDetail(row: ArbitrationRow) {
  detailError.value = ''
  detail.value = null
  try {
    detail.value = await api.arbitrationDetail(row.id)
  } catch (exc) {
    detailError.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '加载详情失败'
  }
}

async function load(target = 1) {
  loading.value = true
  error.value = ''
  router.replace({
    query: {
      ...(status.value ? { status: status.value } : {}),
      ...(target > 1 ? { page: String(target) } : {}),
    },
  })
  try {
    const result = await api.arbitrations({ status: status.value, page: target, page_size: 20 })
    rows.value = result.items
    page.value = result.page
  } catch (exc) {
    error.value = exc instanceof ApiError ? exc.message : '加载失败'
  } finally {
    loading.value = false
  }
}

function openRule(row: ArbitrationRow) {
  current.value = row
  liability.value = row.liability === 'UNDECIDED' ? 'MERCHANT' : row.liability
  refundAmount.value = row.amount
  ruling.value = ''
}

async function submitRule() {
  if (!current.value || !ruling.value.trim()) return
  submitting.value = true
  error.value = ''
  try {
    await api.ruleArbitration(current.value.id, {
      liability: liability.value,
      refund_amount: refundAmount.value,
      ruling: ruling.value.trim(),
    })
    current.value = null
    await load(page.value.page)
  } catch (exc) {
    error.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '裁定失败'
  } finally {
    submitting.value = false
  }
}

onMounted(() => load(Number(route.query.page ?? 1)))
</script>

<template>
  <h1>仲裁处理</h1>
  <div class="toolbar">
    <label class="field">
      <span>状态</span>
      <select v-model="status">
        <option value="">全部</option>
        <option v-for="value in ['PENDING', 'EVIDENCE', 'PROCESSING', 'DECIDED', 'CLOSED']" :key="value" :value="value">
          {{ value }}
        </option>
      </select>
    </label>
    <button class="primary" :disabled="loading" @click="load()">查询</button>
  </div>

  <div v-if="error" class="error" role="alert">{{ error }}</div>
  <div class="card" style="padding: 0">
    <table>
      <thead>
        <tr>
          <th>案号</th>
          <th>售后单</th>
          <th>订单</th>
          <th>争议金额</th>
          <th>状态</th>
          <th>责任方</th>
          <th>截止时间</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.id">
          <td>{{ row.case_no }}</td>
          <td>{{ row.after_sale_no }}</td>
          <td>#{{ row.order_id }}</td>
          <td class="money">{{ formatMoney(row.amount) }}</td>
          <td><span class="tag">{{ row.status }}</span></td>
          <td>{{ row.liability }}</td>
          <td>{{ formatDateTime(row.deadline_at) }}</td>
          <td>
            <button class="text" @click="openDetail(row)">详情</button>
            <button
              class="text"
              style="margin-left: 8px"
              :disabled="row.status === 'DECIDED' || row.status === 'CLOSED'"
              @click="openRule(row)"
            >
              裁定
            </button>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-if="!rows.length" class="empty">{{ loading ? '加载中…' : '暂无仲裁案件' }}</div>
  </div>
  <div class="pager">
    <button class="text" :disabled="page.page <= 1" @click="load(page.page - 1)">上一页</button>
    <span>第 {{ page.page }} 页 · 共 {{ page.total }} 条</span>
    <button class="text" :disabled="!page.has_more" @click="load(page.page + 1)">下一页</button>
  </div>

  <ModalShell v-if="detail" :title="`仲裁详情 · ${detail.case_no}`" @close="detail = null">
    <h2>仲裁详情 · {{ detail.case_no }}</h2>
    <div class="detail-grid">
      <span>售后单</span><b>{{ detail.after_sale.after_sale_no }}</b>
      <span>用户</span><b>{{ detail.after_sale.user_name }}（#{{ detail.after_sale.user_id }}）</b>
      <span>商户</span><b>{{ detail.after_sale.merchant_name }}</b>
      <span>类型</span><b>{{ detail.after_sale.type }}</b>
      <span>申请金额</span><b>{{ formatMoney(detail.after_sale.request_amount) }}</b>
      <span>商户处理</span><b>{{ detail.after_sale.merchant_decision }} {{ detail.after_sale.merchant_reason }}</b>
      <span>问题描述</span><b>{{ detail.after_sale.description || '-' }}</b>
    </div>
    <div>
      <h3 style="font-size: 14px; margin: 8px 0">举证材料</h3>
      <div v-if="detail.after_sale.evidence.length" class="evidence-list">
        <a v-for="item in detail.after_sale.evidence" :key="item" :href="item" target="_blank">{{ item }}</a>
      </div>
      <div v-else class="muted">双方尚未上传举证材料</div>
    </div>
    <div class="toolbar" style="margin: 0">
      <button class="text" @click="detail = null">关闭</button>
    </div>
  </ModalShell>

  <ModalShell v-if="detailError" title="加载失败" @close="detailError = ''">
    <h2>加载失败</h2>
    <div class="error" role="alert">{{ detailError }}</div>
    <button class="text" @click="detailError = ''">关闭</button>
  </ModalShell>

  <ModalShell v-if="current" :title="`仲裁裁定 · ${current.case_no}`" @close="current = null">
    <h2>仲裁裁定 · {{ current.case_no }}</h2>
    <label class="field">
      <span>责任方</span>
      <select v-model="liability">
        <option value="MERCHANT">商户责任</option>
        <option value="USER">用户责任</option>
        <option value="SHARED">双方共担</option>
        <option value="PLATFORM">平台责任</option>
      </select>
    </label>
    <label class="field">
      <span>退款金额（分）</span>
      <input v-model.number="refundAmount" name="refund_amount" type="number" inputmode="numeric" min="0" :max="current.amount" />
    </label>
    <label class="field">
      <span>裁定说明</span>
      <textarea v-model="ruling" rows="3" placeholder="请填写裁定说明…" />
    </label>
    <div v-if="liability === 'USER'" class="error" role="alert">用户责任不得退款，退款金额应为 0</div>
    <div class="toolbar" style="margin: 0">
      <button class="primary" :disabled="submitting || !ruling.trim()" @click="submitRule">提交裁定</button>
      <button class="text" @click="current = null">取消</button>
    </div>
  </ModalShell>
</template>
