<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import {
  api,
  ApiError,
  type AdminCategory,
  type AdminMerchantRow,
  type ProductTemplate,
} from '../api'
import MediaPicker from '../components/MediaPicker.vue'
import ModalShell from '../components/ModalShell.vue'
import PageHeader from '../components/PageHeader.vue'
import StatusTag from '../components/StatusTag.vue'
import { formatMoney } from '../format'

const STATUS_LABEL: Record<string, string> = { DRAFT: '草稿', PUBLISHED: '已发布', OFFLINE: '已下线' }
const SCOPE_LABEL: Record<string, string> = { NONE: '不关联', ALL: '所有商户', SELECTED: '指定商户' }

const rows = ref<ProductTemplate[]>([])
const categories = ref<AdminCategory[]>([])
const merchants = ref<AdminMerchantRow[]>([])
const status = ref('')
const loading = ref(false)
const error = ref('')

const editorOpen = ref(false)
const editing = ref<ProductTemplate | null>(null)
const saving = ref(false)
const formError = ref('')
const form = reactive({
  title: '',
  subtitle: '',
  type: 'PHYSICAL',
  category_id: '',
  price: '',
  cover_url: '',
  description: '',
  status: 'DRAFT',
  scope: 'NONE',
})
const selectedMerchants = ref<number[]>([])
const skuRows = ref<Array<{ sku_code: string; spec_name: string; price: string; stock: string }>>([])

function leafOptions() {
  const parents = new Set(categories.value.filter((item) => item.parent !== null).map((item) => item.parent as number))
  return categories.value.filter((item) => item.parent !== null || !parents.has(item.id))
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const result = await api.adminTemplates({ status: status.value, page_size: 50 })
    rows.value = result.items
  } catch (exc) {
    error.value = exc instanceof ApiError ? exc.message : '加载失败'
  } finally {
    loading.value = false
  }
}

async function ensureOptions() {
  const tasks: Promise<unknown>[] = []
  if (!categories.value.length) tasks.push(api.adminCategories().then((data) => (categories.value = data)))
  if (!merchants.value.length)
    tasks.push(api.adminMerchants({ page_size: 100 }).then((result) => (merchants.value = result.items)))
  await Promise.all(tasks)
}

async function openCreate() {
  await ensureOptions()
  editing.value = null
  formError.value = ''
  form.title = ''
  form.subtitle = ''
  form.type = 'PHYSICAL'
  form.category_id = ''
  form.price = ''
  form.cover_url = ''
  form.description = ''
  form.status = 'DRAFT'
  form.scope = 'NONE'
  selectedMerchants.value = []
  skuRows.value = [{ sku_code: 'A', spec_name: '标准', price: '', stock: '0' }]
  editorOpen.value = true
}

async function openEdit(template: ProductTemplate) {
  await ensureOptions()
  editing.value = template
  formError.value = ''
  form.title = template.title
  form.subtitle = template.subtitle
  form.type = template.type
  form.category_id = String(template.category_id)
  form.price = String(template.price / 100)
  form.cover_url = template.cover_url
  form.description = template.description
  form.status = template.status
  form.scope = template.scope
  selectedMerchants.value = [...template.target_merchant_ids]
  skuRows.value = template.skus.map((sku) => ({
    sku_code: sku.sku_code,
    spec_name: String((sku.spec as { name?: string })?.name ?? ''),
    price: String(sku.price_amount / 100),
    stock: String(sku.stock ?? 0),
  }))
  editorOpen.value = true
}

function toggleMerchant(id: number) {
  selectedMerchants.value = selectedMerchants.value.includes(id)
    ? selectedMerchants.value.filter((item) => item !== id)
    : [...selectedMerchants.value, id]
}

async function save() {
  formError.value = ''
  if (!form.title.trim() || !form.category_id) {
    formError.value = '请填写标题并选择类目'
    return
  }
  const price = Math.round(Number(form.price || 0) * 100)
  if (price < 1) {
    formError.value = '建议售价必须大于 0'
    return
  }
  const deliveries = form.type === 'PHYSICAL' ? ['EXPRESS', 'PICKUP'] : ['VERIFY', 'APPOINTMENT']
  saving.value = true
  try {
    const payload = {
      title: form.title.trim(),
      subtitle: form.subtitle.trim(),
      type: form.type,
      category_id: Number(form.category_id),
      cover_url: form.cover_url,
      images: editing.value?.images ?? [],
      description: form.description,
      price_amount: price,
      original_price_amount: price,
      verify_days: 30,
      appointment_required: false,
      delivery_types: deliveries,
      skus: skuRows.value.map((sku) => ({
        sku_code: sku.sku_code,
        spec: sku.spec_name ? { name: sku.spec_name } : {},
        price_amount: Math.round(Number(sku.price || 0) * 100),
        stock: Number(sku.stock || 0),
      })),
      status: form.status,
      scope: form.scope,
      merchant_ids: form.scope === 'SELECTED' ? selectedMerchants.value : [],
    }
    if (editing.value) await api.updateTemplate(editing.value.id, payload)
    else await api.createTemplate(payload)
    editorOpen.value = false
    await load()
  } catch (exc) {
    formError.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '保存失败'
  } finally {
    saving.value = false
  }
}

async function sync(template: ProductTemplate) {
  if (!confirm(`将模板「${template.title}」同步到 ${template.adoption_count} 个已认领商品？`)) return
  try {
    const result = await api.syncTemplate(template.id)
    alert(`已同步 ${result.synced} 个商品`)
    await load()
  } catch (exc) {
    error.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '同步失败'
  }
}

onMounted(load)
</script>

<template>
  <PageHeader title="商品模板" description="平台维护商品资料，按范围分发给商户认领；商户可自行上下架。" />
  <div class="toolbar">
    <label class="field">
      <span>状态</span>
      <select v-model="status" @change="load">
        <option value="">全部</option>
        <option value="DRAFT">草稿</option>
        <option value="PUBLISHED">已发布</option>
        <option value="OFFLINE">已下线</option>
      </select>
    </label>
    <button class="primary" @click="openCreate">发布模板</button>
  </div>

  <div v-if="error" class="error" role="alert">{{ error }}</div>

  <div class="table-wrap">
    <table>
      <thead>
        <tr><th>模板</th><th>类目</th><th class="money">建议价</th><th>分发</th><th>状态</th><th class="money">认领</th><th>操作</th></tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.id">
          <td class="cell-main">
            {{ row.title }}
            <div class="muted">{{ row.template_no }}</div>
          </td>
          <td>{{ row.category_name || '-' }}</td>
          <td class="money">{{ formatMoney(row.price) }}</td>
          <td>{{ SCOPE_LABEL[row.scope] ?? row.scope }}</td>
          <td><StatusTag :status="row.status" :label="STATUS_LABEL[row.status] ?? row.status" /></td>
          <td class="money">{{ row.adoption_count }}</td>
          <td>
            <div class="actions">
              <button class="text" @click="openEdit(row)">编辑</button>
              <button class="text" @click="sync(row)">同步到商户</button>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-if="!rows.length" class="empty">{{ loading ? '加载中…' : '暂无模板' }}</div>
  </div>

  <ModalShell v-if="editorOpen" :title="editing ? '编辑模板' : '发布模板'" wide @close="editorOpen = false">
    <h2>{{ editing ? '编辑模板' : '发布模板' }}</h2>
    <div v-if="formError" class="error" role="alert">{{ formError }}</div>
    <div class="form-grid">
      <label class="field"><span>标题</span><input v-model="form.title" name="title" /></label>
      <label class="field"><span>副标题</span><input v-model="form.subtitle" name="subtitle" /></label>
      <label class="field">
        <span>类型</span>
        <select v-model="form.type" name="type">
          <option value="PHYSICAL">实物商品</option>
          <option value="SERVICE">到店服务</option>
        </select>
      </label>
      <label class="field">
        <span>平台类目</span>
        <select v-model="form.category_id" name="category_id">
          <option value="">请选择</option>
          <option v-for="item in leafOptions()" :key="item.id" :value="String(item.id)">{{ item.name }}</option>
        </select>
      </label>
      <label class="field"><span>建议售价（元）</span><input v-model="form.price" name="price" type="number" step="0.01" /></label>
      <label class="field"><span>封面</span><MediaPicker v-model="form.cover_url" kind="IMAGE" /></label>
      <label class="field">
        <span>状态</span>
        <select v-model="form.status" name="status">
          <option value="DRAFT">草稿</option>
          <option value="PUBLISHED">已发布</option>
          <option value="OFFLINE">已下线</option>
        </select>
      </label>
      <label class="field">
        <span>分发范围</span>
        <select v-model="form.scope" name="scope">
          <option value="NONE">不关联</option>
          <option value="ALL">所有商户</option>
          <option value="SELECTED">指定商户</option>
        </select>
      </label>
    </div>
    <label class="field"><span>详情</span><textarea v-model="form.description" rows="3" name="description" /></label>

    <div v-if="form.scope === 'SELECTED'" class="section-title">选择商户</div>
    <div v-if="form.scope === 'SELECTED'" class="chips">
      <button
        v-for="merchant in merchants"
        :key="merchant.id"
        class="chip"
        :class="{ on: selectedMerchants.includes(merchant.id) }"
        @click="toggleMerchant(merchant.id)"
      >
        {{ merchant.name }}
      </button>
    </div>

    <div class="section-title">默认 SKU</div>
    <div v-for="(sku, index) in skuRows" :key="index" class="form-grid">
      <label class="field"><span>编码</span><input v-model="sku.sku_code" /></label>
      <label class="field"><span>规格名</span><input v-model="sku.spec_name" /></label>
      <label class="field"><span>售价（元）</span><input v-model="sku.price" type="number" step="0.01" /></label>
      <label class="field"><span>默认库存</span><input v-model="sku.stock" type="number" /></label>
    </div>
    <button class="text" @click="skuRows.push({ sku_code: '', spec_name: '', price: '', stock: '0' })">添加 SKU</button>

    <div class="toolbar" style="margin: 0">
      <button class="primary" :disabled="saving" @click="save">保存</button>
      <button class="text" @click="editorOpen = false">取消</button>
    </div>
  </ModalShell>
</template>
