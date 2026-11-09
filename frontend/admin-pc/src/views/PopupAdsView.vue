<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, ApiError, type Schemas } from '../api'
import { formatDateTime } from '../format'
import PageHeader from '../components/PageHeader.vue'
import ModalShell from '../components/ModalShell.vue'

const rows = ref<Schemas['PopupAd'][]>([])
const loading = ref(false)
const error = ref('')
const statusFilter = ref('')

const createOpen = ref(false)
const creating = ref(false)
const createError = ref('')

const form = ref({
  title: '',
  image_url: '',
  link_url: '',
  frequency: 'ONCE_PER_DAY' as 'EVERY_LAUNCH' | 'ONCE_PER_DAY' | 'ONCE_PER_WEEK' | 'ONCE_PER_USER',
  priority: '0',
  start_at: '',
  end_at: '',
  max_impressions: '0',
})

const STATUS_LABEL: Record<string, string> = {
  DRAFT: '草稿',
  ENABLED: '投放中',
  DISABLED: '已下架',
  EXPIRED: '已过期',
}

const STATUS_CLASS: Record<string, string> = {
  DRAFT: 'tag',
  ENABLED: 'tag success',
  DISABLED: 'tag warn',
  EXPIRED: 'tag muted',
}

const FREQUENCY_LABEL: Record<string, string> = {
  EVERY_LAUNCH: '每次启动',
  ONCE_PER_DAY: '一天一次',
  ONCE_PER_WEEK: '一周一次',
  ONCE_PER_USER: '仅一次',
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    rows.value = await api.adminPopupAds(statusFilter.value ? { status: statusFilter.value } : {})
  } catch (exc) {
    error.value = exc instanceof ApiError ? exc.message : '加载失败'
  } finally {
    loading.value = false
  }
}

function openCreate() {
  form.value = {
    title: '',
    image_url: '',
    link_url: '',
    frequency: 'ONCE_PER_DAY',
    priority: '0',
    start_at: '',
    end_at: '',
    max_impressions: '0',
  }
  createError.value = ''
  createOpen.value = true
}

function toIso(value: string): string | null {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date.toISOString()
}

async function submitCreate() {
  const f = form.value
  if (!f.title.trim()) return (createError.value = '请填写标题')
  if (!f.image_url.trim()) return (createError.value = '请填写图片 URL')
  const startAt = toIso(f.start_at)
  const endAt = toIso(f.end_at)
  if (startAt && endAt && startAt >= endAt) return (createError.value = '结束时间必须晚于开始时间')
  creating.value = true
  createError.value = ''
  try {
    await api.createAdminPopupAd({
      title: f.title.trim(),
      image_url: f.image_url.trim(),
      link_url: f.link_url.trim() || undefined,
      frequency: f.frequency,
      priority: Number(f.priority || 0),
      start_at: startAt,
      end_at: endAt,
      max_impressions: Number(f.max_impressions || 0),
    })
    createOpen.value = false
    await load()
  } catch (exc) {
    createError.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '创建失败'
  } finally {
    creating.value = false
  }
}

async function toggleStatus(row: Schemas['PopupAd'], action: 'enable' | 'disable') {
  if (!row.id) return
  try {
    await api.adminPopupAdStatus(row.id, action)
    await load()
  } catch (exc) {
    error.value = exc instanceof ApiError ? exc.message : '操作失败'
  }
}

onMounted(load)
</script>

<template>
  <PageHeader title="弹窗广告" description="小程序启动时展示的弹窗，支持频次控制与投放时段。" />

  <section class="card">
    <div class="toolbar">
      <h2 class="card-title">弹窗列表</h2>
      <div class="toolbar-right">
        <select v-model="statusFilter" @change="load">
          <option value="">全部状态</option>
          <option value="DRAFT">草稿</option>
          <option value="ENABLED">投放中</option>
          <option value="DISABLED">已下架</option>
          <option value="EXPIRED">已过期</option>
        </select>
        <button class="primary" type="button" @click="openCreate">+ 新建弹窗</button>
      </div>
    </div>
    <div v-if="error" class="alert error">{{ error }}</div>
    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th>标题</th>
            <th>图片</th>
            <th>跳转链接</th>
            <th>频次</th>
            <th class="num">优先级</th>
            <th>投放时段</th>
            <th class="num">展示次数</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in rows" :key="p.id">
            <td>
              <strong>{{ p.title }}</strong>
              <div class="muted small">{{ p.created_by_name }} · {{ formatDateTime(p.created_at) }}</div>
            </td>
            <td>
              <img v-if="p.image_url" :src="p.image_url" class="thumb" alt="" />
              <span v-else class="muted">-</span>
            </td>
            <td class="small mono">
              <span v-if="p.link_url">{{ p.link_url }}</span>
              <span v-else class="muted">-</span>
            </td>
            <td>{{ FREQUENCY_LABEL[p.frequency ?? ''] ?? p.frequency }}</td>
            <td class="num">{{ p.priority ?? 0 }}</td>
            <td class="small">
              {{ formatDateTime(p.start_at) }} ~ {{ formatDateTime(p.end_at) }}
            </td>
            <td class="num">
              {{ p.impression_count ?? 0 }}
              <span v-if="p.max_impressions" class="muted">/{{ p.max_impressions }}</span>
            </td>
            <td><span :class="STATUS_CLASS[p.status ?? ''] ?? 'tag'">{{ STATUS_LABEL[p.status ?? ''] ?? p.status }}</span></td>
            <td>
              <button
                v-if="p.status === 'DRAFT' || p.status === 'DISABLED'"
                class="chip"
                type="button"
                @click="toggleStatus(p, 'enable')"
              >上架</button>
              <button
                v-if="p.status === 'ENABLED'"
                class="chip"
                type="button"
                @click="toggleStatus(p, 'disable')"
              >下架</button>
            </td>
          </tr>
          <tr v-if="!loading && rows.length === 0">
            <td colspan="9" class="muted center">暂无弹窗广告</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>

  <!-- 新建弹窗 -->
  <ModalShell v-if="createOpen" title="新建弹窗广告" @close="createOpen = false">
    <div class="modal-head">
      <h2>新建弹窗广告</h2>
      <button class="modal-close" type="button" @click="createOpen = false">✕</button>
    </div>
    <div v-if="createError" class="alert error">{{ createError }}</div>
    <div class="grid-2">
      <label class="field">
        <span>标题<i class="req">*</i></span>
        <input v-model="form.title" placeholder="内部管理标题，不展示给用户" maxlength="80" />
      </label>
      <label class="field">
        <span>图片 URL<i class="req">*</i></span>
        <input v-model="form.image_url" placeholder="https://..." maxlength="500" />
      </label>
      <label class="field">
        <span>跳转链接</span>
        <input v-model="form.link_url" placeholder="小程序路径或外部 URL，可空" maxlength="500" />
      </label>
      <label class="field">
        <span>展示频次</span>
        <select v-model="form.frequency">
          <option value="EVERY_LAUNCH">每次启动</option>
          <option value="ONCE_PER_DAY">一天一次</option>
          <option value="ONCE_PER_WEEK">一周一次</option>
          <option value="ONCE_PER_USER">仅一次</option>
        </select>
      </label>
      <label class="field">
        <span>优先级</span>
        <input type="number" v-model.number="form.priority" placeholder="数字越大越优先" />
      </label>
      <label class="field">
        <span>总展示上限</span>
        <input type="number" min="0" v-model.number="form.max_impressions" placeholder="0=不限" />
      </label>
      <label class="field">
        <span>投放开始</span>
        <input type="datetime-local" v-model="form.start_at" />
      </label>
      <label class="field">
        <span>投放结束</span>
        <input type="datetime-local" v-model="form.end_at" />
      </label>
    </div>
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
.toolbar-right { display: flex; gap: 12px; align-items: center; }
.num { text-align: right; }
.center { text-align: center; }
.small { font-size: 12px; }
.mono { font-family: 'SF Mono', Menlo, monospace; word-break: break-all; }
.thumb { width: 64px; height: 64px; object-fit: cover; border-radius: 8px; display: block; }
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
