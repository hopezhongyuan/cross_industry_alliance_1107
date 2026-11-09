<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, ApiError, type AdminMerchantDetail, type AdminProductDetail, type AuditTaskRow } from '../api'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import ModalShell from '../components/ModalShell.vue'
import PageHeader from '../components/PageHeader.vue'
import PaginationBar from '../components/PaginationBar.vue'
import StatusTag from '../components/StatusTag.vue'
import { formatDateTime, formatMoney } from '../format'

const route = useRoute()
const router = useRouter()

const BIZ_LABEL: Record<string, string> = {
  MERCHANT: '商户入驻',
  PRODUCT: '商品上架',
  QUALIFICATION: '资质材料',
  REVIEW: '评价内容',
}

const STATUS_LABEL: Record<string, string> = {
  PENDING: '待审核',
  PROCESSING: '审核中',
  APPROVED: '已通过',
  REJECTED: '已驳回',
  CANCELLED: '已取消',
}

const tabs = [
  { value: 'MERCHANT', label: '商户入驻' },
  { value: 'PRODUCT', label: '商品上架' },
  { value: 'QUALIFICATION', label: '资质材料' },
]
const statusFilters = [
  { value: 'PENDING', label: '待审核' },
  { value: '', label: '全部' },
  { value: 'APPROVED', label: '已通过' },
  { value: 'REJECTED', label: '已驳回' },
]

const bizType = ref(String(route.query.biz_type ?? 'MERCHANT'))
const status = ref(String(route.query.status ?? 'PENDING'))
const rows = ref<AuditTaskRow[]>([])
const summary = ref<Record<string, number>>({})
const page = ref({ page: 1, page_size: 20, total: 0, has_more: false })
const loading = ref(false)
const error = ref('')

const viewRow = ref<AuditTaskRow | null>(null)
const merchantDetail = ref<AdminMerchantDetail | null>(null)
const productDetail = ref<AdminProductDetail | null>(null)
const detailLoading = ref(false)
const detailError = ref('')

const current = ref<AuditTaskRow | null>(null)
const decision = ref<'APPROVE' | 'REJECT'>('APPROVE')
const reason = ref('')
const submitting = ref(false)

const selected = ref<number[]>([])
const batch = ref<'APPROVE' | 'REJECT' | ''>('')
const batchSubmitting = ref(false)
const message = ref('')

const pendingRows = () =>
  rows.value.filter((row) => row.status === 'PENDING' || row.status === 'PROCESSING')

function toggleAll() {
  const pending = pendingRows()
  const allChecked = pending.length > 0 && pending.every((row) => selected.value.includes(row.id))
  selected.value = allChecked ? [] : pending.map((row) => row.id)
}

function toggleRow(id: number) {
  selected.value = selected.value.includes(id)
    ? selected.value.filter((item) => item !== id)
    : [...selected.value, id]
}

function tabCount(value: string): number {
  return summary.value[value] ?? 0
}

function statusClass(value: string): string {
  if (value === 'APPROVED') return 'tag ok'
  if (value === 'REJECTED') return 'tag danger'
  return 'tag'
}

async function load(target = 1, size = page.value.page_size) {
  loading.value = true
  error.value = ''
  selected.value = []
  router.replace({
    query: {
      ...(bizType.value ? { biz_type: bizType.value } : {}),
      ...(status.value ? { status: status.value } : {}),
      ...(target > 1 ? { page: String(target) } : {}),
    },
  })
  try {
    const result = await api.audits({ biz_type: bizType.value, status: status.value, page: target, page_size: size })
    rows.value = result.items
    summary.value = result.summary
    page.value = result.page
  } catch (exc) {
    error.value = exc instanceof ApiError ? exc.message : '加载失败'
  } finally {
    loading.value = false
  }
}

function selectTab(value: string) {
  bizType.value = value
  load(1)
}

function selectStatus(value: string) {
  status.value = value
  load(1)
}

async function openView(row: AuditTaskRow) {
  viewRow.value = row
  merchantDetail.value = null
  productDetail.value = null
  detailError.value = ''
  if (row.biz_type === 'MERCHANT') {
    detailLoading.value = true
    try {
      merchantDetail.value = await api.adminMerchantDetail(row.biz_id)
    } catch (exc) {
      detailError.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '加载商户资料失败'
    } finally {
      detailLoading.value = false
    }
    return
  }
  if (row.biz_type === 'PRODUCT') {
    detailLoading.value = true
    try {
      productDetail.value = await api.adminProductDetail(row.biz_id)
    } catch (exc) {
      detailError.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '加载商品资料失败'
    } finally {
      detailLoading.value = false
    }
  }
}

function closeView() {
  viewRow.value = null
  merchantDetail.value = null
  productDetail.value = null
  detailError.value = ''
}

function openDecision(row: AuditTaskRow, value: 'APPROVE' | 'REJECT') {
  current.value = row
  decision.value = value
  reason.value = ''
}

async function submitDecision() {
  if (!current.value) return
  if (decision.value === 'REJECT' && !reason.value.trim()) return
  submitting.value = true
  error.value = ''
  try {
    await api.decideAudit(current.value.id, decision.value, reason.value.trim())
    current.value = null
    await load(page.value.page)
  } catch (exc) {
    error.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '审核失败'
  } finally {
    submitting.value = false
  }
}

function openBatch(kind: 'APPROVE' | 'REJECT') {
  if (!selected.value.length) return
  batch.value = kind
}

async function submitBatch(batchReason: string) {
  if (!batch.value) return
  batchSubmitting.value = true
  error.value = ''
  message.value = ''
  try {
    const result = await api.batchDecideAudit(selected.value, batch.value, batchReason)
    batch.value = ''
    if (result.failed) {
      error.value = `通过 ${result.succeeded} 条，失败 ${result.failed} 条：${result.items
        .filter((item) => !item.ok)
        .map((item) => `#${item.id} ${item.error_message}`)
        .join('；')}`
    } else {
      message.value = `已处理 ${result.succeeded} 条审核任务`
    }
    await load(page.value.page)
  } catch (exc) {
    error.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '批量审核失败'
  } finally {
    batchSubmitting.value = false
  }
}

onMounted(() => load(Number(route.query.page ?? 1)))
</script>

<template>
  <PageHeader title="审核中心" description="按业务类型处理待审核任务；批量操作逐条校验，失败项单独返回原因。" />

  <div class="toolbar">
    <div class="chips">
      <button
        v-for="item in tabs"
        :key="item.value"
        class="chip"
        :class="{ on: bizType === item.value }"
        @click="selectTab(item.value)"
      >
        {{ item.label }}<em>{{ tabCount(item.value) }}</em>
      </button>
    </div>
    <label class="field">
      <span>状态</span>
      <select v-model="status" @change="load(1)">
        <option v-for="item in statusFilters" :key="item.value || 'all'" :value="item.value">{{ item.label }}</option>
      </select>
    </label>
  </div>

  <div v-if="error" class="error" role="alert">{{ error }}</div>
  <div v-if="message" class="notice" aria-live="polite">{{ message }}</div>

  <div v-if="selected.length" class="batch-bar">
    <span>已选 <b>{{ selected.length }}</b> 项</span>
    <button class="text" @click="openBatch('APPROVE')">批量通过</button>
    <button class="text" @click="openBatch('REJECT')">批量驳回</button>
    <span class="spacer" />
    <button class="text" @click="selected = []">取消选择</button>
  </div>

  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th class="select">
            <input
              type="checkbox"
              aria-label="全选当前页待处理任务"
              :checked="pendingRows().length > 0 && pendingRows().every((row) => selected.includes(row.id))"
              :disabled="!pendingRows().length"
              @change="toggleAll"
            />
          </th>
          <th>类型</th>
          <th>审核对象</th>
          <th>状态</th>
          <th>提交时间</th>
          <th>处理信息</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.id">
          <td class="select">
            <input
              v-if="row.status === 'PENDING' || row.status === 'PROCESSING'"
              type="checkbox"
              :checked="selected.includes(row.id)"
              :aria-label="`选择 ${row.biz_name}`"
              @change="toggleRow(row.id)"
            />
          </td>
          <td>{{ BIZ_LABEL[row.biz_type] ?? row.biz_type }}</td>
          <td>{{ row.biz_name || `#${row.biz_id}` }}</td>
          <td><StatusTag :status="row.status" /></td>
          <td>{{ formatDateTime(row.created_at) }}</td>
          <td>
            <span v-if="row.handled_at">{{ row.assigned_to_name || '平台' }} · {{ formatDateTime(row.handled_at) }}</span>
            <span v-else class="muted">-</span>
            <div v-if="row.reason" class="muted">{{ row.reason }}</div>
          </td>
          <td>
            <div class="actions">
              <button class="text" @click="openView(row)">查看</button>
              <template v-if="row.status === 'PENDING' || row.status === 'PROCESSING'">
                <button class="text" @click="openDecision(row, 'APPROVE')">通过</button>
                <button class="danger" @click="openDecision(row, 'REJECT')">驳回</button>
              </template>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-if="!rows.length" class="empty">{{ loading ? '加载中…' : '当前类型暂无可处理事项' }}</div>
  </div>

  <PaginationBar
    :page="page.page"
    :page-size="page.page_size"
    :total="page.total"
    @change="(payload) => load(payload.page, payload.pageSize)"
  />

  <ModalShell v-if="viewRow" :title="`审核详情 · ${viewRow.biz_name || viewRow.biz_id}`" wide @close="closeView">
    <h2>审核详情 · {{ viewRow.biz_name || `#${viewRow.biz_id}` }}</h2>
    <div class="detail-grid">
      <span>类型</span><b>{{ BIZ_LABEL[viewRow.biz_type] ?? viewRow.biz_type }}</b>
      <span>状态</span><b><span :class="statusClass(viewRow.status)">{{ STATUS_LABEL[viewRow.status] ?? viewRow.status }}</span></b>
      <span>提交时间</span><b>{{ formatDateTime(viewRow.created_at) }}</b>
      <span>处理人</span><b>{{ viewRow.assigned_to_name || '-' }}</b>
      <span>处理说明</span><b>{{ viewRow.reason || '-' }}</b>
    </div>

    <template v-if="viewRow.biz_type === 'MERCHANT'">
      <div v-if="detailLoading" class="muted">加载商户资料…</div>
      <div v-else-if="detailError" class="error" role="alert">{{ detailError }}</div>
      <template v-else-if="merchantDetail">
        <div class="section-title">商户资料</div>
        <div class="detail-grid">
          <span>商户号</span><b>{{ merchantDetail.merchant_no }}</b>
          <span>类目</span><b>{{ merchantDetail.category_name || '未分类' }}</b>
          <span>区域</span><b>{{ merchantDetail.province }}{{ merchantDetail.city }}{{ merchantDetail.district }}</b>
          <span>地址</span><b>{{ merchantDetail.address || '-' }}</b>
          <span>联系电话</span><b>{{ merchantDetail.contact_phone || '-' }}</b>
          <span>佣金率</span><b>{{ (merchantDetail.commission_rate * 100).toFixed(1) }}%</b>
          <span>资金余额</span><b>{{ formatMoney(merchantDetail.balances.available_amount) }} 可提现</b>
        </div>

        <div class="section-title">资质材料</div>
        <div v-if="merchantDetail.qualifications.length" class="detail-grid">
          <template v-for="item in merchantDetail.qualifications" :key="item.id">
            <span>{{ item.type_label }}</span>
            <b>
              <a :href="item.file_url" target="_blank">查看材料</a>
              · {{ item.audit_status }}
              <span v-if="item.reject_reason" class="muted">（{{ item.reject_reason }}）</span>
            </b>
          </template>
        </div>
        <div v-else class="muted">该商户尚未上传资质</div>
      </template>
    </template>

    <template v-if="viewRow.biz_type === 'PRODUCT'">
      <div v-if="detailLoading" class="muted">加载商品资料…</div>
      <div v-else-if="detailError" class="error" role="alert">{{ detailError }}</div>
      <template v-else-if="productDetail">
        <div class="section-title">商品资料</div>
        <div class="detail-grid">
          <span>标题</span><b>{{ productDetail.title }}</b>
          <span>副标题</span><b>{{ productDetail.subtitle || '-' }}</b>
          <span>商户</span><b>{{ productDetail.merchant_name }}（{{ productDetail.merchant_no }}）</b>
          <span>类目</span><b>{{ productDetail.category_name || '未分类' }}</b>
          <span>本店分类</span><b>{{ productDetail.merchant_category_name || '-' }}</b>
          <span>货号</span><b>{{ productDetail.product_code || '-' }}</b>
          <span>类型</span><b>{{ productDetail.type_label }}</b>
          <span>售价</span><b>{{ formatMoney(productDetail.price) }}</b>
          <span>划线价</span><b>{{ formatMoney(productDetail.original_price) }}</b>
          <span>履约方式</span><b>{{ productDetail.delivery_types.join('、') }}</b>
          <span>核销有效期</span><b>{{ productDetail.verify_days }} 天</b>
          <span>提交时间</span><b>{{ formatDateTime(productDetail.submitted_at) }}</b>
        </div>
        <div v-if="productDetail.cover_url" class="detail-grid">
          <span>封面</span><b><a :href="productDetail.cover_url" target="_blank">查看图片</a></b>
        </div>
        <div class="section-title">SKU</div>
        <div class="card" style="padding: 0">
          <table>
            <thead>
              <tr><th>编码</th><th>规格</th><th class="money">售价</th><th class="money">库存</th><th class="money">可售</th></tr>
            </thead>
            <tbody>
              <tr v-for="sku in productDetail.skus" :key="sku.id">
                <td>{{ sku.sku_code }}</td>
                <td>{{ String(sku.spec_json?.name ?? '-') }}</td>
                <td class="money">{{ formatMoney(sku.price) }}</td>
                <td class="money">{{ sku.stock }}</td>
                <td class="money">{{ sku.available_stock }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="productDetail.description" class="muted">详情：{{ productDetail.description }}</div>
      </template>
    </template>

    <div class="toolbar" style="margin: 0">
      <template v-if="viewRow.status === 'PENDING' || viewRow.status === 'PROCESSING'">
        <button class="primary" @click="openDecision(viewRow, 'APPROVE'); closeView()">通过</button>
        <button class="danger" @click="openDecision(viewRow, 'REJECT'); closeView()">驳回</button>
      </template>
      <button class="text" @click="closeView">关闭</button>
    </div>
  </ModalShell>

  <ModalShell v-if="current" :title="`${decision === 'APPROVE' ? '审核通过' : '审核驳回'} · ${current.biz_name || current.biz_id}`" @close="current = null">
    <h2>{{ decision === 'APPROVE' ? '审核通过' : '审核驳回' }} · {{ current.biz_name || `#${current.biz_id}` }}</h2>
    <div class="muted">
      通过后商品/商户进入可售或营业状态；驳回后标记驳回原因，需商户修改后重新提交。
    </div>
    <label class="field">
      <span>{{ decision === 'REJECT' ? '驳回原因（必填）' : '审核说明（选填）' }}</span>
      <textarea v-model="reason" rows="3" name="reason" placeholder="请填写审核说明…" />
    </label>
    <div class="toolbar" style="margin: 0">
      <button
        class="primary"
        :disabled="submitting || (decision === 'REJECT' && !reason.trim())"
        @click="submitDecision"
      >
        提交
      </button>
      <button class="text" @click="current = null">取消</button>
    </div>
  </ModalShell>

  <ConfirmDialog
    v-if="batch"
    :title="batch === 'APPROVE' ? '批量审核通过' : '批量审核驳回'"
    :message="`将对已选 ${selected.length} 条任务执行${batch === 'APPROVE' ? '通过' : '驳回'}；逐条校验状态，失败项会返回原因。`"
    :reason-required="batch === 'REJECT'"
    :reason-label="batch === 'REJECT' ? '驳回原因' : '审核说明'"
    :danger="batch === 'REJECT'"
    :busy="batchSubmitting"
    @confirm="submitBatch"
    @close="batch = ''"
  />
</template>
