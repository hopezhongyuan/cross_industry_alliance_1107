<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, ApiError, type Schemas } from '../api'
import { formatMoney, formatDateTime } from '../format'
import PageHeader from '../components/PageHeader.vue'
import ModalShell from '../components/ModalShell.vue'

const rows = ref<Schemas['Coupon'][]>([])
const loading = ref(false)
const error = ref('')

const createOpen = ref(false)
const creating = ref(false)
const createError = ref('')

const form = ref({
  name: '',
  face_value: '',
  min_amount: '0',
  scope_type: 'ALL' as 'ALL' | 'CATEGORY' | 'PRODUCT',
  scope_category_ids: '',
  scope_product_ids: '',
  target_merchant_ids: '',
  total_stock: '0',
  per_user_limit: '1',
  valid_from: '',
  valid_to: '',
  description: '',
})

const STATUS_LABEL: Record<string, string> = {
  DRAFT: '草稿',
  ACTIVE: '进行中',
  PAUSED: '已暂停',
  EXPIRED: '已过期',
}

const STATUS_CLASS: Record<string, string> = {
  DRAFT: 'tag',
  ACTIVE: 'tag success',
  PAUSED: 'tag warn',
  EXPIRED: 'tag muted',
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    rows.value = await api.adminCoupons()
  } catch (exc) {
    error.value = exc instanceof ApiError ? exc.message : '加载失败'
  } finally {
    loading.value = false
  }
}

function openCreate() {
  form.value = {
    name: '',
    face_value: '',
    min_amount: '0',
    scope_type: 'ALL',
    scope_category_ids: '',
    scope_product_ids: '',
    target_merchant_ids: '',
    total_stock: '0',
    per_user_limit: '1',
    valid_from: '',
    valid_to: '',
    description: '',
  }
  createError.value = ''
  createOpen.value = true
}

function parseIds(text: string): number[] {
  return text
    .split(/[,，\s]+/)
    .map((s) => s.trim())
    .filter(Boolean)
    .map((s) => Number(s))
    .filter((n) => Number.isInteger(n) && n > 0)
}

async function submitCreate() {
  const f = form.value
  if (!f.name.trim()) return (createError.value = '请填写券名称')
  const face = Math.round(Number(f.face_value) * 100)
  if (!face || face <= 0) return (createError.value = '请填写正确的面额（元）')
  if (!f.valid_from || !f.valid_to) return (createError.value = '请选择生效与失效时间')
  creating.value = true
  createError.value = ''
  try {
    await api.createAdminCoupon({
      name: f.name.trim(),
      face_value: face,
      min_amount: Math.round(Number(f.min_amount || 0) * 100),
      scope_type: f.scope_type,
      scope_category_ids: parseIds(f.scope_category_ids),
      scope_product_ids: parseIds(f.scope_product_ids),
      target_merchant_ids: parseIds(f.target_merchant_ids),
      total_stock: Number(f.total_stock || 0),
      per_user_limit: Number(f.per_user_limit || 1),
      valid_from: new Date(f.valid_from).toISOString(),
      valid_to: new Date(f.valid_to).toISOString(),
      description: f.description.trim(),
    })
    createOpen.value = false
    await load()
  } catch (exc) {
    createError.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '创建失败'
  } finally {
    creating.value = false
  }
}

async function toggleStatus(row: Schemas['Coupon']) {
  if (!row.id) return
  const action = row.status === 'ACTIVE' ? 'pause' : 'activate'
  try {
    await api.adminCouponStatus(row.id, action)
    await load()
  } catch (exc) {
    error.value = exc instanceof ApiError ? exc.message : '操作失败'
  }
}

function scopeLabel(c: Schemas['Coupon']): string {
  if (c.scope_type === 'ALL') return '全场'
  if (c.scope_type === 'CATEGORY') return `指定类目（${(c.scope_category_ids ?? []).length}）`
  return `指定商品（${(c.scope_product_ids ?? []).length}）`
}

onMounted(load)
</script>

<template>
  <PageHeader title="平台优惠券" description="平台券成本由平台承担，可指定类目或参加商户。" />

  <section class="card">
    <div class="toolbar">
      <h2 class="card-title">优惠券列表</h2>
      <button class="primary" type="button" @click="openCreate">+ 新建平台券</button>
    </div>
    <div v-if="error" class="alert error">{{ error }}</div>
    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th>名称</th>
            <th class="num">面额</th>
            <th>门槛</th>
            <th>适用范围</th>
            <th class="num">已领/总量</th>
            <th class="num">每人限领</th>
            <th>有效期</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in rows" :key="c.id">
            <td>
              <strong>{{ c.name }}</strong>
              <div class="muted small">{{ c.coupon_no }}</div>
            </td>
            <td class="num">{{ formatMoney(c.face_value) }}</td>
            <td>{{ (c.min_amount ?? 0) > 0 ? `满${formatMoney(c.min_amount)}` : '无门槛' }}</td>
            <td>{{ scopeLabel(c) }}</td>
            <td class="num">
              {{ c.issued_count ?? 0 }}{{ c.total_stock ? `/${c.total_stock}` : '' }}
            </td>
            <td class="num">{{ c.per_user_limit }}</td>
            <td class="small">
              {{ formatDateTime(c.valid_from) }} ~ {{ formatDateTime(c.valid_to) }}
            </td>
            <td><span :class="STATUS_CLASS[c.status ?? ''] ?? 'tag'">{{ STATUS_LABEL[c.status ?? ''] ?? c.status }}</span></td>
            <td>
              <button
                v-if="c.status === 'ACTIVE' || c.status === 'PAUSED' || c.status === 'DRAFT'"
                class="chip"
                type="button"
                @click="toggleStatus(c)"
              >
                {{ c.status === 'ACTIVE' ? '暂停' : '启用' }}
              </button>
            </td>
          </tr>
          <tr v-if="!loading && rows.length === 0">
            <td colspan="9" class="muted center">暂无优惠券</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>

  <!-- 新建弹窗 -->
  <ModalShell v-if="createOpen" title="新建平台优惠券" @close="createOpen = false">
    <div class="modal-head">
      <h2>新建平台优惠券</h2>
      <button class="modal-close" type="button" @click="createOpen = false">✕</button>
    </div>
    <div v-if="createError" class="alert error">{{ createError }}</div>
    <div class="grid-2">
      <label class="field">
        <span>券名称<i class="req">*</i></span>
        <input v-model="form.name" placeholder="如：新客立减 20 元" />
      </label>
      <label class="field">
        <span>面额（元）<i class="req">*</i></span>
        <input type="number" min="0.01" step="0.01" v-model="form.face_value" placeholder="20" />
      </label>
      <label class="field">
        <span>满减门槛（元）</span>
        <input type="number" min="0" step="0.01" v-model="form.min_amount" placeholder="0=无门槛" />
      </label>
      <label class="field">
        <span>适用范围</span>
        <select v-model="form.scope_type">
          <option value="ALL">全场通用</option>
          <option value="CATEGORY">指定类目</option>
          <option value="PRODUCT">指定商品</option>
        </select>
      </label>
      <label v-if="form.scope_type === 'CATEGORY'" class="field">
        <span>类目 ID（逗号分隔）</span>
        <input v-model="form.scope_category_ids" placeholder="1,2,3" />
      </label>
      <label v-if="form.scope_type === 'PRODUCT'" class="field">
        <span>商品 ID（逗号分隔）</span>
        <input v-model="form.scope_product_ids" placeholder="101,102" />
      </label>
      <label class="field">
        <span>参加商户 ID（逗号分隔，空=全部）</span>
        <input v-model="form.target_merchant_ids" placeholder="空表示全部商户可参加" />
      </label>
      <label class="field">
        <span>发放总量（0=不限）</span>
        <input type="number" min="0" v-model.number="form.total_stock" />
      </label>
      <label class="field">
        <span>每人限领</span>
        <input type="number" min="0" v-model.number="form.per_user_limit" />
      </label>
      <label class="field">
        <span>生效时间<i class="req">*</i></span>
        <input type="datetime-local" v-model="form.valid_from" />
      </label>
      <label class="field">
        <span>失效时间<i class="req">*</i></span>
        <input type="datetime-local" v-model="form.valid_to" />
      </label>
    </div>
    <label class="field">
      <span>使用说明</span>
      <textarea rows="2" v-model="form.description" placeholder="可选" />
    </label>
    <div class="toolbar" style="justify-content: flex-end">
      <button class="outline" type="button" @click="createOpen = false">取消</button>
      <button class="primary" type="button" :disabled="creating" @click="submitCreate">
        {{ creating ? '创建中…' : '创建' }}
      </button>
    </div>
  </ModalShell>
</template>

<style scoped>
.card-title { margin: 0; font-size: 18px; }
.toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.num { text-align: right; }
.center { text-align: center; }
.small { font-size: 12px; }
.grid-2 {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}
.tag.success { background: #e8f5e9; color: #2e7d32; }
.tag.warn { background: #fff3e0; color: #ef6c00; }
.tag.muted { background: #f1eadc; color: #7b7468; }
</style>
