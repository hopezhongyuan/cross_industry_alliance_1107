<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, ApiError, type AdminProductRow, type Page } from '../api'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import PageHeader from '../components/PageHeader.vue'
import PaginationBar from '../components/PaginationBar.vue'
import StatusTag from '../components/StatusTag.vue'
import { formatMoney } from '../format'

const route = useRoute()
const router = useRouter()

const STATUS_OPTIONS = [
  { value: '', label: '全部状态' },
  { value: 'DRAFT', label: '草稿' },
  { value: 'PENDING_AUDIT', label: '待审核' },
  { value: 'ON_SALE', label: '在售' },
  { value: 'OFF_SALE', label: '已下架' },
  { value: 'REJECTED', label: '已驳回' },
]

const rows = ref<AdminProductRow[]>([])
const page = ref<Page>({ page: 1, page_size: 20, total: 0, has_more: false })
const status = ref(String(route.query.status ?? ''))
const keyword = ref(String(route.query.q ?? ''))
const loading = ref(false)
const error = ref('')
const message = ref('')

const selected = ref<number[]>([])
const allChecked = computed(() => rows.value.length > 0 && selected.value.length === rows.value.length)

const action = ref<'' | 'FORCE_OFF' | 'RESTORE'>('')
const submitting = ref(false)

function toggleAll() {
  selected.value = allChecked.value ? [] : rows.value.map((row) => row.id)
}

function toggleRow(id: number) {
  selected.value = selected.value.includes(id)
    ? selected.value.filter((item) => item !== id)
    : [...selected.value, id]
}

async function load(target = 1, size = page.value.page_size) {
  loading.value = true
  error.value = ''
  message.value = ''
  selected.value = []
  router.replace({
    query: {
      ...(status.value ? { status: status.value } : {}),
      ...(keyword.value.trim() ? { q: keyword.value.trim() } : {}),
      ...(target > 1 ? { page: String(target) } : {}),
    },
  })
  try {
    const result = await api.adminProducts({
      status: status.value,
      q: keyword.value.trim(),
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

function reset() {
  status.value = ''
  keyword.value = ''
  load(1)
}

function openBatch(kind: 'FORCE_OFF' | 'RESTORE') {
  if (!selected.value.length) return
  action.value = kind
}

async function submitBatch(reason: string) {
  if (!action.value) return
  submitting.value = true
  error.value = ''
  message.value = ''
  try {
    const result = await api.batchAdminProductStatus(selected.value, action.value, reason)
    action.value = ''
    if (result.failed) {
      error.value = `成功 ${result.succeeded} 条，失败 ${result.failed} 条：${result.items
        .filter((item) => !item.ok)
        .map((item) => `#${item.id} ${item.error_message}`)
        .join('；')}`
    } else {
      message.value = `已处理 ${result.succeeded} 条商品`
    }
    await load(page.value.page)
  } catch (exc) {
    error.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '批量操作失败'
  } finally {
    submitting.value = false
  }
}

onMounted(() => load(Number(route.query.page ?? 1)))
</script>

<template>
  <PageHeader title="商品管理" description="全平台商品检索、编辑与违规处置；编辑与下架均写入操作日志。">
    <template #actions>
      <button class="outline" @click="router.push('/product-templates')">商品模板</button>
    </template>
  </PageHeader>

  <div class="toolbar">
    <label class="field">
      <span>状态</span>
      <select v-model="status" @change="load(1)">
        <option v-for="item in STATUS_OPTIONS" :key="item.value" :value="item.value">{{ item.label }}</option>
      </select>
    </label>
    <label class="field">
      <span>关键词</span>
      <input v-model="keyword" name="product_q" placeholder="商品标题 / 货号…" @keyup.enter="load(1)" />
    </label>
    <button class="primary" :disabled="loading" @click="load(1)">查询</button>
    <button class="outline" @click="reset">重置</button>
  </div>

  <div v-if="error" class="error" role="alert">{{ error }}</div>
  <div v-if="message" class="notice" aria-live="polite">{{ message }}</div>

  <div v-if="selected.length" class="batch-bar">
    <span>已选 <b>{{ selected.length }}</b> 项</span>
    <button class="text" @click="openBatch('FORCE_OFF')">批量强制下架</button>
    <button class="text" @click="openBatch('RESTORE')">批量恢复上架</button>
    <span class="spacer" />
    <button class="text" @click="selected = []">取消选择</button>
  </div>

  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th class="select"><input type="checkbox" :checked="allChecked" aria-label="全选当前页" @change="toggleAll" /></th>
          <th>商品</th>
          <th>商户</th>
          <th>类目</th>
          <th class="money">售价</th>
          <th>状态</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.id">
          <td class="select">
            <input type="checkbox" :checked="selected.includes(row.id)" :aria-label="`选择 ${row.title}`" @change="toggleRow(row.id)" />
          </td>
          <td class="cell-main">
            {{ row.title }}
            <div class="muted">{{ row.product_code || `#${row.id}` }}</div>
          </td>
          <td>{{ row.merchant_name }}</td>
          <td>{{ row.category_name || '未分类' }}</td>
          <td class="money">{{ formatMoney(row.price) }}</td>
          <td>
            <StatusTag :status="row.status" />
            <div v-if="row.off_sale_reason" class="muted">平台下架：{{ row.off_sale_reason }}</div>
          </td>
          <td>
            <div class="actions">
              <button class="text" @click="router.push(`/products/${row.id}`)">查看 / 编辑</button>
              <button v-if="row.status === 'ON_SALE'" class="danger" @click="selected = [row.id]; openBatch('FORCE_OFF')">
                强制下架
              </button>
              <button
                v-if="row.status === 'OFF_SALE' && row.off_sale_by === 'PLATFORM'"
                class="text"
                @click="selected = [row.id]; openBatch('RESTORE')"
              >
                恢复上架
              </button>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-if="!rows.length" class="empty">{{ loading ? '加载中…' : '暂无商品' }}</div>
  </div>

  <PaginationBar
    :page="page.page"
    :page-size="page.page_size"
    :total="page.total"
    @change="(payload) => load(payload.page, payload.pageSize)"
  />

  <ConfirmDialog
    v-if="action"
    :title="action === 'FORCE_OFF' ? '批量强制下架' : '批量恢复上架'"
    :message="action === 'FORCE_OFF' ? `将对已选 ${selected.length} 件商品执行下架，仅“在售”状态可成功。` : `将对已选 ${selected.length} 件商品执行恢复，仅平台下架的商品可成功。`"
    :reason-required="action === 'FORCE_OFF'"
    reason-label="下架原因"
    :danger="action === 'FORCE_OFF'"
    :busy="submitting"
    @confirm="submitBatch"
    @close="action = ''"
  />
</template>
