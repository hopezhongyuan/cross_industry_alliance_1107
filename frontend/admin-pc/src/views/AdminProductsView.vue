<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { api, ApiError, type AdminCategory, type AdminProductDetail, type AdminProductRow } from '../api'
import MediaPicker from '../components/MediaPicker.vue'
import ModalShell from '../components/ModalShell.vue'
import { formatMoney } from '../format'

const STATUS_LABEL: Record<string, string> = {
  DRAFT: '草稿',
  PENDING_AUDIT: '待审核',
  ON_SALE: '在售',
  OFF_SALE: '已下架',
  REJECTED: '已驳回',
}

const rows = ref<AdminProductRow[]>([])
const categories = ref<AdminCategory[]>([])
const page = ref({ page: 1, page_size: 20, total: 0, has_more: false })
const status = ref('')
const keyword = ref('')
const loading = ref(false)
const error = ref('')

const editorOpen = ref(false)
const editing = ref<AdminProductDetail | null>(null)
const saving = ref(false)
const formError = ref('')
const form = reactive({
  title: '',
  subtitle: '',
  category_id: '',
  product_code: '',
  price: '',
  original_price: '',
  cover_url: '',
  description: '',
})
const skuRows = ref<Array<{ sku_code: string; price: string; stock: string }>>([])

const actionRow = ref<AdminProductRow | null>(null)
const actionType = ref<'FORCE_OFF' | 'RESTORE'>('FORCE_OFF')
const reason = ref('')
const submitting = ref(false)

function leafOptions() {
  const parents = new Set(categories.value.filter((item) => item.parent !== null).map((item) => item.parent as number))
  return categories.value.filter((item) => item.parent !== null || !parents.has(item.id))
}

async function load(target = 1) {
  loading.value = true
  error.value = ''
  try {
    const result = await api.adminProducts({
      status: status.value,
      q: keyword.value,
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

async function openEdit(row: AdminProductRow) {
  error.value = ''
  formError.value = ''
  try {
    if (!categories.value.length) categories.value = await api.adminCategories()
    const detail = await api.adminProductDetail(row.id)
    editing.value = detail
    form.title = detail.title
    form.subtitle = detail.subtitle
    form.category_id = detail.category_id ? String(detail.category_id) : ''
    form.product_code = detail.product_code
    form.price = String(detail.price / 100)
    form.original_price = String(detail.original_price / 100)
    form.cover_url = detail.cover_url
    form.description = detail.description
    skuRows.value = detail.skus.map((sku) => ({
      sku_code: sku.sku_code,
      price: String(sku.price / 100),
      stock: String(sku.stock),
    }))
    editorOpen.value = true
  } catch (exc) {
    error.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '加载详情失败'
  }
}

async function save() {
  if (!editing.value) return
  formError.value = ''
  if (!form.title.trim() || !form.category_id) {
    formError.value = '请填写标题并选择类目'
    return
  }
  const price = Math.round(Number(form.price || 0) * 100)
  if (price < 1) {
    formError.value = '售价必须大于 0'
    return
  }
  saving.value = true
  try {
    await api.updateAdminProduct(editing.value.id, {
      category_id: Number(form.category_id),
      type: editing.value.type,
      title: form.title.trim(),
      subtitle: form.subtitle.trim(),
      product_code: form.product_code.trim(),
      price_amount: price,
      original_price_amount: Math.round(Number(form.original_price || 0) * 100),
      cover_url: form.cover_url,
      images: editing.value.images,
      description: form.description,
      verify_days: editing.value.verify_days,
      appointment_required: editing.value.appointment_required,
      delivery_types: editing.value.delivery_types,
      skus: skuRows.value.map((sku) => ({
        sku_code: sku.sku_code,
        spec: {},
        price_amount: Math.round(Number(sku.price || 0) * 100),
        stock: Number(sku.stock || 0),
      })),
    })
    editorOpen.value = false
    await load(page.value.page)
  } catch (exc) {
    formError.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '保存失败'
  } finally {
    saving.value = false
  }
}

function openAction(row: AdminProductRow, type: 'FORCE_OFF' | 'RESTORE') {
  actionRow.value = row
  actionType.value = type
  reason.value = ''
}

async function submitAction() {
  if (!actionRow.value) return
  if (actionType.value === 'FORCE_OFF' && !reason.value.trim()) return
  submitting.value = true
  try {
    await api.setAdminProductStatus(actionRow.value.id, actionType.value, reason.value.trim())
    actionRow.value = null
    await load(page.value.page)
  } catch (exc) {
    error.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '操作失败'
  } finally {
    submitting.value = false
  }
}

onMounted(() => load(1))
</script>

<template>
  <h1>商品管理</h1>
  <div class="toolbar">
    <label class="field">
      <span>状态</span>
      <select v-model="status" @change="load(1)">
        <option value="">全部</option>
        <option v-for="(label, value) in STATUS_LABEL" :key="value" :value="value">{{ label }}</option>
      </select>
    </label>
    <label class="field">
      <span>关键词</span>
      <input v-model="keyword" name="product_q" placeholder="商品标题…" @keyup.enter="load(1)" />
    </label>
    <button class="primary" :disabled="loading" @click="load(1)">查询</button>
  </div>

  <div v-if="error" class="error" role="alert">{{ error }}</div>

  <div class="card" style="padding: 0">
    <table>
      <thead>
        <tr><th>商品</th><th>商户</th><th>类目</th><th class="money">售价</th><th>状态</th><th>操作</th></tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.id">
          <td>{{ row.title }}<br /><span class="muted">{{ row.product_code || `#${row.id}` }}</span></td>
          <td>{{ row.merchant_name }}</td>
          <td>{{ row.category_name || '未分类' }}</td>
          <td class="money">{{ formatMoney(row.price) }}</td>
          <td>
            <span class="tag">{{ STATUS_LABEL[row.status] ?? row.status }}</span>
            <br v-if="row.off_sale_reason" />
            <span v-if="row.off_sale_reason" class="muted">平台下架：{{ row.off_sale_reason }}</span>
          </td>
          <td>
            <button class="text" @click="openEdit(row)">编辑</button>
            <button
              v-if="row.status === 'ON_SALE'"
              class="danger"
              style="margin-left: 8px"
              @click="openAction(row, 'FORCE_OFF')"
            >
              强制下架
            </button>
            <button
              v-if="row.status === 'OFF_SALE' && row.off_sale_by === 'PLATFORM'"
              class="text"
              style="margin-left: 8px"
              @click="openAction(row, 'RESTORE')"
            >
              恢复上架
            </button>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-if="!rows.length" class="empty">{{ loading ? '加载中…' : '暂无商品' }}</div>
  </div>
  <div class="pager">
    <button class="text" :disabled="page.page <= 1" @click="load(page.page - 1)">上一页</button>
    <span>第 {{ page.page }} 页 · 共 {{ page.total }} 件</span>
    <button class="text" :disabled="!page.has_more" @click="load(page.page + 1)">下一页</button>
  </div>

  <ModalShell v-if="editorOpen && editing" :title="`编辑商品 · ${editing.title}`" wide @close="editorOpen = false">
    <h2>编辑商品 · {{ editing.title }}</h2>
    <div class="muted">平台编辑直接生效，不重新进入审核；请使用素材库选择封面。</div>
    <div v-if="formError" class="error" role="alert">{{ formError }}</div>
    <div class="form-grid">
      <label class="field"><span>标题</span><input v-model="form.title" name="title" /></label>
      <label class="field"><span>副标题</span><input v-model="form.subtitle" name="subtitle" /></label>
      <label class="field">
        <span>平台类目</span>
        <select v-model="form.category_id" name="category_id">
          <option value="">请选择</option>
          <option v-for="item in leafOptions()" :key="item.id" :value="String(item.id)">{{ item.name }}</option>
        </select>
      </label>
      <label class="field"><span>商户货号</span><input v-model="form.product_code" name="product_code" /></label>
      <label class="field"><span>售价（元）</span><input v-model="form.price" name="price" type="number" step="0.01" /></label>
      <label class="field"><span>划线价（元）</span><input v-model="form.original_price" name="original_price" type="number" step="0.01" /></label>
      <label class="field"><span>封面</span><MediaPicker v-model="form.cover_url" kind="IMAGE" /></label>
    </div>
    <label class="field"><span>详情</span><textarea v-model="form.description" rows="3" name="description" /></label>

    <div class="section-title">SKU</div>
    <div v-for="(sku, index) in skuRows" :key="index" class="form-grid">
      <label class="field"><span>编码</span><input v-model="sku.sku_code" disabled /></label>
      <label class="field"><span>售价（元）</span><input v-model="sku.price" type="number" step="0.01" /></label>
      <label class="field"><span>库存</span><input v-model="sku.stock" type="number" /></label>
    </div>

    <div class="toolbar" style="margin: 0">
      <button class="primary" :disabled="saving" @click="save">保存</button>
      <button class="text" @click="editorOpen = false">取消</button>
    </div>
  </ModalShell>

  <ModalShell v-if="actionRow" :title="actionType === 'FORCE_OFF' ? '强制下架' : '恢复上架'" @close="actionRow = null">
    <h2>{{ actionType === 'FORCE_OFF' ? '强制下架' : '恢复上架' }} · {{ actionRow.title }}</h2>
    <div class="muted">平台下架后商户不能自行上架，需平台恢复。</div>
    <label v-if="actionType === 'FORCE_OFF'" class="field">
      <span>下架原因</span>
      <textarea v-model="reason" rows="3" name="force_reason" placeholder="如：违规宣传…" />
    </label>
    <div class="toolbar" style="margin: 0">
      <button class="primary" :disabled="submitting || (actionType === 'FORCE_OFF' && !reason.trim())" @click="submitAction">
        确认
      </button>
      <button class="text" @click="actionRow = null">取消</button>
    </div>
  </ModalShell>
</template>
