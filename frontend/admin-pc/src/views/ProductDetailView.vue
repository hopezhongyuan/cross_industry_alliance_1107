<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, ApiError, type AdminCategory, type AdminProductDetail } from '../api'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import MediaPicker from '../components/MediaPicker.vue'
import PageHeader from '../components/PageHeader.vue'
import StatusTag from '../components/StatusTag.vue'
import { formatDateTime, formatMoney } from '../format'

const route = useRoute()
const router = useRouter()
const productId = computed(() => Number(route.params.id))

const detail = ref<AdminProductDetail | null>(null)
const categories = ref<AdminCategory[]>([])
const loading = ref(true)
const error = ref('')
const message = ref('')
const saving = ref(false)

const form = reactive({
  title: '',
  subtitle: '',
  category_id: '',
  product_code: '',
  price: '',
  original_price: '',
  cover_url: '',
  images: [] as string[],
  description: '',
})
const skuRows = ref<Array<{ sku_code: string; price: string; stock: string }>>([])

const action = ref<'FORCE_OFF' | 'RESTORE' | ''>('')
const submitting = ref(false)

const leafOptions = computed(() => {
  const parents = new Set(categories.value.filter((item) => item.parent !== null).map((item) => item.parent as number))
  return categories.value.filter((item) => item.parent !== null || !parents.has(item.id))
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [product, cats] = await Promise.all([api.adminProductDetail(productId.value), api.adminCategories()])
    detail.value = product
    categories.value = cats
    form.title = product.title
    form.subtitle = product.subtitle
    form.category_id = product.category_id ? String(product.category_id) : ''
    form.product_code = product.product_code
    form.price = String(product.price / 100)
    form.original_price = String(product.original_price / 100)
    form.cover_url = product.cover_url
    form.images = [...(product.images ?? [])]
    form.description = product.description
    skuRows.value = product.skus.map((sku) => ({
      sku_code: sku.sku_code,
      price: String(sku.price / 100),
      stock: String(sku.stock),
    }))
  } catch (exc) {
    const code = exc instanceof ApiError ? exc.code : ''
    if (exc instanceof ApiError && exc.status === 404) {
      error.value = `商品不存在（${code}）`
      return
    }
    error.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '加载商品失败'
  } finally {
    loading.value = false
  }
}

async function save() {
  if (!detail.value) return
  error.value = ''
  message.value = ''
  if (!form.title.trim() || !form.category_id) {
    error.value = '请填写标题并选择平台类目'
    return
  }
  const price = Math.round(Number(form.price || 0) * 100)
  if (price < 1) {
    error.value = '售价必须大于 0'
    return
  }
  saving.value = true
  try {
    const saved = await api.updateAdminProduct(detail.value.id, {
      category_id: Number(form.category_id),
      type: detail.value.type,
      title: form.title.trim(),
      subtitle: form.subtitle.trim(),
      product_code: form.product_code.trim(),
      price_amount: price,
      original_price_amount: Math.round(Number(form.original_price || 0) * 100),
      cover_url: form.cover_url,
      images: form.images,
      description: form.description,
      verify_days: detail.value.verify_days,
      appointment_required: detail.value.appointment_required,
      delivery_types: detail.value.delivery_types,
      skus: skuRows.value.map((sku) => ({
        sku_code: sku.sku_code,
        spec: {},
        price_amount: Math.round(Number(sku.price || 0) * 100),
        stock: Number(sku.stock || 0),
      })),
    })
    detail.value = saved
    message.value = '已保存，平台编辑直接生效，不重新进入审核'
  } catch (exc) {
    error.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '保存失败'
  } finally {
    saving.value = false
  }
}

async function submitAction(reason: string) {
  if (!detail.value || !action.value) return
  submitting.value = true
  error.value = ''
  try {
    await api.setAdminProductStatus(detail.value.id, action.value, reason)
    action.value = ''
    message.value = '商品状态已更新'
    await load()
  } catch (exc) {
    error.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '操作失败'
  } finally {
    submitting.value = false
  }
}

onMounted(load)
</script>

<template>
  <PageHeader :title="detail ? `商品详情 · ${detail.title}` : '商品详情'" description="平台编辑商户商品将直接生效，不重新进入审核。">
    <template #actions>
      <button class="outline" @click="router.push('/products')">返回列表</button>
      <button v-if="detail?.status === 'ON_SALE'" class="outline" @click="action = 'FORCE_OFF'">强制下架</button>
      <button
        v-if="detail?.status === 'OFF_SALE' && detail?.off_sale_by === 'PLATFORM'"
        class="outline"
        @click="action = 'RESTORE'"
      >
        恢复上架
      </button>
      <button class="primary" :disabled="saving || !detail" @click="save">{{ saving ? '保存中…' : '保存' }}</button>
    </template>
  </PageHeader>

  <div v-if="error" class="error" role="alert">{{ error }}</div>
  <div v-if="message" class="notice" aria-live="polite">{{ message }}</div>
  <div v-if="loading" class="empty">加载中…</div>

  <div v-if="detail" class="detail-layout">
    <div>
      <form class="card" @submit.prevent="save">
        <div class="section-title" style="margin-top: 0">基本信息</div>
        <div class="form-grid">
          <label class="field span-2">
            <span>标题<i class="req">*</i></span>
            <input v-model="form.title" name="title" />
          </label>
          <label class="field">
            <span>副标题</span>
            <input v-model="form.subtitle" name="subtitle" />
          </label>
          <label class="field">
            <span>平台类目<i class="req">*</i></span>
            <select v-model="form.category_id" name="category_id">
              <option value="">请选择</option>
              <option v-for="item in leafOptions" :key="item.id" :value="String(item.id)">{{ item.name }}</option>
            </select>
            <span class="field-help">平台类目为二级；商户自建分类不在此处修改。</span>
          </label>
          <label class="field">
            <span>商户货号</span>
            <input v-model="form.product_code" name="product_code" />
            <span class="field-help">建议格式：商户ID-类目缩写-序号，例如 M1001-CF-001。</span>
          </label>
          <label class="field">
            <span>整店配送方式</span>
            <input :value="detail.delivery_types.join('、') || '-'" disabled />
          </label>
          <label class="field">
            <span>售价（元）<i class="req">*</i></span>
            <input v-model="form.price" name="price" type="number" step="0.01" min="0" />
          </label>
          <label class="field">
            <span>划线价（元）</span>
            <input v-model="form.original_price" name="original_price" type="number" step="0.01" min="0" />
            <span class="field-help">划线价仅用于展示，不参与分账。</span>
          </label>
        </div>

        <div class="form-section">
          <div class="section-title" style="margin-top: 0">图片</div>
          <div class="form-grid">
            <div class="field">
              <span>商品封面</span>
              <MediaPicker v-model="form.cover_url" kind="IMAGE" hint="建议 1200×1200（1:1），JPG/WebP，≤500KB" />
            </div>
            <div class="field">
              <span>商品图集</span>
              <MediaPicker v-model="form.images" kind="IMAGE" multiple hint="建议 750×750 以上，最多 8 张，每张 ≤1MB" />
            </div>
          </div>
        </div>

        <div class="form-section">
          <div class="section-title" style="margin-top: 0">规格与库存</div>
          <table class="sku-table">
            <thead>
              <tr><th>规格编码</th><th class="money">售价（元）</th><th class="money">库存</th></tr>
            </thead>
            <tbody>
              <tr v-for="(sku, index) in skuRows" :key="index">
                <td><input v-model="sku.sku_code" name="sku_code" /></td>
                <td class="money"><input v-model="sku.price" type="number" step="0.01" min="0" /></td>
                <td class="money"><input v-model="sku.stock" type="number" min="0" /></td>
              </tr>
            </tbody>
          </table>
          <span class="field-help">规格编码创建后不建议修改，跨系统对账依赖该编码。</span>
        </div>

        <div class="form-section">
          <div class="section-title" style="margin-top: 0">图文详情</div>
          <label class="field">
            <span>详情文案</span>
            <textarea v-model="form.description" rows="6" name="description" />
          </label>
        </div>
      </form>
    </div>

    <aside>
      <div class="card">
        <div class="section-title" style="margin-top: 0">状态</div>
        <div class="detail-grid">
          <span>当前状态</span><b><StatusTag :status="detail.status" /></b>
          <span>所属商户</span><b>{{ detail.merchant_name }}</b>
          <span>商户编号</span><b>{{ detail.merchant_no }}</b>
          <span>累计销量</span><b>{{ detail.sold_count }}</b>
          <span>版本号</span><b>{{ detail.version }}</b>
          <span>提交审核</span><b>{{ detail.submitted_at ? formatDateTime(detail.submitted_at) : '-' }}</b>
          <span>审核时间</span><b>{{ detail.audited_at ? formatDateTime(detail.audited_at) : '-' }}</b>
          <span>创建时间</span><b>{{ formatDateTime(detail.created_at) }}</b>
          <span>当前售价</span><b>{{ formatMoney(detail.price) }}</b>
        </div>
        <div v-if="detail.reject_reason" class="muted" style="margin-top: 10px">驳回原因：{{ detail.reject_reason }}</div>
      </div>
      <div class="card">
        <div class="section-title" style="margin-top: 0">操作说明</div>
        <div class="muted">
          平台可强制下架在售商品并填写原因；下架后商户不能自行上架，需平台恢复。平台编辑不影响审核状态。
        </div>
      </div>
    </aside>
  </div>

  <ConfirmDialog
    v-if="action"
    :title="action === 'FORCE_OFF' ? '强制下架商品' : '恢复上架'"
    :message="action === 'FORCE_OFF' ? '下架后立即停止销售，商户无法自行上架，需平台恢复。' : '恢复后商品重新在售。'"
    :reason-required="action === 'FORCE_OFF'"
    reason-label="下架原因"
    confirm-label="确认"
    :danger="action === 'FORCE_OFF'"
    :busy="submitting"
    @confirm="submitAction"
    @close="action = ''"
  />
</template>

<style scoped>
.detail-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: var(--gap-md);
  align-items: start;
}

.sku-table {
  width: 100%;
}

.sku-table input {
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 6px 8px;
  font-size: var(--fs-table);
}

@media (max-width: 1080px) {
  .detail-layout {
    grid-template-columns: 1fr;
  }
}
</style>
