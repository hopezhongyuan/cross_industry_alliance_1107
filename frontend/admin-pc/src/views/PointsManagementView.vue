<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, ApiError, type Page, type Schemas } from '../api'
import PageHeader from '../components/PageHeader.vue'
import PaginationBar from '../components/PaginationBar.vue'
import ModalShell from '../components/ModalShell.vue'

const config = ref<Schemas['PointsConfig'] | null>(null)
const configError = ref('')
const configSaving = ref(false)

const rows = ref<Schemas['PointAccount'][]>([])
const page = ref<Page>({ page: 1, page_size: 20, total: 0, has_more: false })
const keyword = ref('')
const loading = ref(false)
const error = ref('')

const adjustOpen = ref(false)
const adjustTarget = ref<Schemas['PointAccount'] | null>(null)
const adjustDelta = ref('')
const adjustReason = ref('')
const adjustBusy = ref(false)
const adjustError = ref('')

const txOpen = ref(false)
const txUserId = ref<number | null>(null)
const txItems = ref<Schemas['PointTransaction'][]>([])
const txLoading = ref(false)

const BIZ_LABEL: Record<string, string> = {
  CONSUMPTION: '消费',
  SIGNIN: '签到',
  SHARE: '分享',
  REGISTER: '注册',
  REVIEW: '评价',
  ADMIN_ADJUST: '后台调整',
}

async function loadConfig() {
  try {
    config.value = await api.pointsConfig()
  } catch (exc) {
    configError.value = exc instanceof ApiError ? exc.message : '加载失败'
  }
}

async function saveConfig() {
  if (!config.value) return
  configSaving.value = true
  configError.value = ''
  try {
    config.value = await api.savePointsConfig(config.value)
  } catch (exc) {
    configError.value = exc instanceof ApiError ? exc.message : '保存失败'
  } finally {
    configSaving.value = false
  }
}

async function loadUsers(target = 1) {
  loading.value = true
  error.value = ''
  try {
    const result = await api.pointsUsers({ keyword: keyword.value.trim(), page: target, page_size: page.value.page_size })
    rows.value = result.items
    page.value = result.page
  } catch (exc) {
    error.value = exc instanceof ApiError ? exc.message : '加载失败'
  } finally {
    loading.value = false
  }
}

function openAdjust(row: Schemas['PointAccount']) {
  adjustTarget.value = row
  adjustDelta.value = ''
  adjustReason.value = ''
  adjustError.value = ''
  adjustOpen.value = true
}

async function submitAdjust() {
  if (!adjustTarget.value) return
  const delta = Number(adjustDelta.value)
  if (!delta || !Number.isInteger(delta)) {
    adjustError.value = '请输入整数积分（正数增加，负数扣减）'
    return
  }
  if (!adjustReason.value.trim()) {
    adjustError.value = '请填写调整原因'
    return
  }
  adjustBusy.value = true
  adjustError.value = ''
  try {
    await api.adjustPoints({ user_id: adjustTarget.value.user_id!, delta, reason: adjustReason.value.trim() })
    adjustOpen.value = false
    await loadUsers(page.value.page)
  } catch (exc) {
    adjustError.value = exc instanceof ApiError ? exc.message : '调整失败'
  } finally {
    adjustBusy.value = false
  }
}

async function openTransactions(row: Schemas['PointAccount']) {
  txUserId.value = row.user_id!
  txOpen.value = true
  txLoading.value = true
  try {
    const result = await api.pointsUserTransactions(row.user_id!)
    txItems.value = result.items
  } finally {
    txLoading.value = false
  }
}

onMounted(() => {
  loadConfig()
  loadUsers(1)
})
</script>

<template>
  <PageHeader title="积分管理" description="配置积分规则，查看与调整用户积分。" />

  <!-- 积分规则 -->
  <section class="card">
    <h2 class="card-title">积分规则配置</h2>
    <div v-if="configError" class="alert error">{{ configError }}</div>
    <div v-if="config" class="grid-2">
      <label class="field">
        <span>启用积分功能</span>
        <select v-model="config.enabled">
          <option :value="true">启用</option>
          <option :value="false">停用</option>
        </select>
      </label>
      <label class="field">
        <span>消费积分比例（分/积分）</span>
        <input type="number" min="1" v-model.number="config.consumption_rate" />
        <span class="field-help">例：100 表示每消费 1 元得 1 积分</span>
      </label>
      <label class="field">
        <span>单笔订单积分上限（0=不限）</span>
        <input type="number" min="0" v-model.number="config.consumption_max_per_order" />
      </label>
      <label class="field">
        <span>签到积分</span>
        <input type="number" min="0" v-model.number="config.signin_points" />
      </label>
      <label class="field">
        <span>单次分享积分</span>
        <input type="number" min="0" v-model.number="config.share_points" />
      </label>
      <label class="field">
        <span>每日分享次数上限</span>
        <input type="number" min="0" v-model.number="config.share_daily_limit" />
      </label>
      <label class="field">
        <span>注册积分</span>
        <input type="number" min="0" v-model.number="config.register_points" />
      </label>
      <label class="field">
        <span>评价积分</span>
        <input type="number" min="0" v-model.number="config.review_points" />
      </label>
    </div>
    <div class="toolbar" style="justify-content: flex-end">
      <button class="primary" type="button" :disabled="configSaving" @click="saveConfig">
        {{ configSaving ? '保存中…' : '保存规则' }}
      </button>
    </div>
  </section>

  <!-- 用户积分列表 -->
  <section class="card">
    <h2 class="card-title">用户积分</h2>
    <div class="toolbar">
      <label class="field">
        <span>搜索</span>
        <input v-model="keyword" placeholder="手机号或昵称…" @keyup.enter="loadUsers(1)" />
      </label>
      <button class="primary" type="button" @click="loadUsers(1)">查询</button>
    </div>
    <div v-if="error" class="alert error">{{ error }}</div>
    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th>用户 ID</th>
            <th>手机号</th>
            <th>昵称</th>
            <th class="num">可用积分</th>
            <th class="num">累计获得</th>
            <th class="num">累计消耗</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.id">
            <td>{{ row.user_id }}</td>
            <td>{{ row.user_phone }}</td>
            <td>{{ row.user_nickname }}</td>
            <td class="num"><strong>{{ row.balance }}</strong></td>
            <td class="num">{{ row.total_earned }}</td>
            <td class="num">{{ row.total_spent }}</td>
            <td>
              <button class="chip" type="button" @click="openTransactions(row)">明细</button>
              <button class="chip primary" type="button" @click="openAdjust(row)">调整</button>
            </td>
          </tr>
          <tr v-if="!loading && rows.length === 0">
            <td colspan="7" class="muted center">暂无数据</td>
          </tr>
        </tbody>
      </table>
    </div>
    <PaginationBar :page="page.page" :page-size="page.page_size" :total="page.total" @change="(p) => loadUsers(p.page)" />
  </section>

  <!-- 调整弹窗 -->
  <ModalShell v-if="adjustOpen" title="调整积分" @close="adjustOpen = false">
    <div class="modal-head">
      <h2>调整积分</h2>
      <button class="modal-close" type="button" @click="adjustOpen = false">✕</button>
    </div>
    <div class="muted" style="margin-bottom: 12px">
      用户：{{ adjustTarget?.user_nickname || adjustTarget?.user_phone }}（ID {{ adjustTarget?.user_id }}），当前余额 {{ adjustTarget?.balance }}
    </div>
    <div v-if="adjustError" class="alert error">{{ adjustError }}</div>
    <label class="field">
      <span>调整积分<i class="req">*</i></span>
      <input type="number" v-model="adjustDelta" placeholder="正数增加，负数扣减，如 100 或 -50" />
    </label>
    <label class="field">
      <span>调整原因<i class="req">*</i></span>
      <textarea rows="3" v-model="adjustReason" placeholder="请填写调整原因，将写入操作日志" />
    </label>
    <div class="toolbar" style="justify-content: flex-end">
      <button class="outline" type="button" @click="adjustOpen = false">取消</button>
      <button class="primary" type="button" :disabled="adjustBusy" @click="submitAdjust">
        {{ adjustBusy ? '处理中…' : '确认调整' }}
      </button>
    </div>
  </ModalShell>

  <!-- 明细弹窗 -->
  <ModalShell v-if="txOpen" title="积分明细" @close="txOpen = false">
    <div class="modal-head">
      <h2>积分明细</h2>
      <button class="modal-close" type="button" @click="txOpen = false">✕</button>
    </div>
    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr><th>类型</th><th>变动</th><th>余额</th><th>备注</th><th>时间</th></tr>
        </thead>
        <tbody>
          <tr v-for="t in txItems" :key="t.id">
            <td>{{ BIZ_LABEL[t.biz_type || ''] || t.biz_type }}</td>
            <td :class="{ pos: (t.delta ?? 0) >= 0, neg: (t.delta ?? 0) < 0 }">
              {{ (t.delta ?? 0) >= 0 ? '+' : '' }}{{ t.delta }}
            </td>
            <td>{{ t.balance_after }}</td>
            <td>{{ t.remark }}</td>
            <td>{{ t.created_at }}</td>
          </tr>
          <tr v-if="!txLoading && txItems.length === 0">
            <td colspan="5" class="muted center">暂无流水</td>
          </tr>
        </tbody>
      </table>
    </div>
  </ModalShell>
</template>

<style scoped>
.grid-2 {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}
.card-title {
  margin: 0 0 16px;
  font-size: 18px;
}
.num { text-align: right; }
.center { text-align: center; }
.pos { color: var(--success); font-weight: 600; }
.neg { color: var(--danger); font-weight: 600; }
</style>
