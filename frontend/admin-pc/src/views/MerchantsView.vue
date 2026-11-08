<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  api,
  ApiError,
  type AdminMerchantDetail,
  type AdminMerchantRow,
  type CategoryRow,
  type MerchantSummary,
  type StaffUser,
} from '../api'
import ModalShell from '../components/ModalShell.vue'
import MediaPicker from '../components/MediaPicker.vue'
import { formatDateTime, formatMoney } from '../format'

const route = useRoute()
const router = useRouter()

const STATUS_LABEL: Record<string, string> = {
  PENDING: '待审核',
  ACTIVE: '营业中',
  RESTING: '停业',
  BANNED: '已封禁',
  REJECTED: '审核驳回',
}

const filters = [
  { value: '', label: '全部' },
  { value: 'ACTIVE', label: '营业中' },
  { value: 'PENDING', label: '待审核' },
  { value: 'RESTING', label: '停业' },
  { value: 'BANNED', label: '封禁' },
]

const rows = ref<AdminMerchantRow[]>([])
const summary = ref<MerchantSummary>({ total: 0, active: 0, pending: 0, resting: 0, banned: 0, rejected: 0 })
const page = ref({ page: 1, page_size: 20, total: 0, has_more: false })
const status = ref(String(route.query.status ?? ''))
const keyword = ref(String(route.query.q ?? ''))
const loading = ref(false)
const error = ref('')

const detail = ref<AdminMerchantDetail | null>(null)
const detailLoading = ref(false)
const detailError = ref('')

const actionRow = ref<AdminMerchantRow | null>(null)
const actionStatus = ref<'ACTIVE' | 'RESTING' | 'BANNED'>('RESTING')
const reason = ref('')
const submitting = ref(false)

const createOpen = ref(false)
const creating = ref(false)
const createError = ref('')
const categories = ref<CategoryRow[]>([])
const ownerMatches = ref<StaffUser[]>([])
const ownerLoading = ref(false)
const ownerChecked = ref(false)
const form = reactive({
  name: '',
  short_name: '',
  category_id: '',
  contact_phone: '',
  province: '',
  city: '',
  district: '',
  address: '',
  commission_percent: '',
  settlement_cycle_days: '7',
  bank: '',
  card_no: '',
  license_url: '',
  owner_phone: '',
})

function resetForm() {
  form.name = ''
  form.short_name = ''
  form.category_id = ''
  form.contact_phone = ''
  form.province = ''
  form.city = ''
  form.district = ''
  form.address = ''
  form.commission_percent = ''
  form.settlement_cycle_days = '7'
  form.bank = ''
  form.card_no = ''
  form.license_url = ''
  form.owner_phone = ''
  ownerMatches.value = []
  ownerChecked.value = false
  createError.value = ''
}

async function openCreate() {
  resetForm()
  createOpen.value = true
  if (!categories.value.length) {
    try {
      categories.value = await api.categories()
    } catch (exc) {
      createError.value = exc instanceof ApiError ? exc.message : '类目加载失败'
    }
  }
}

async function lookupOwner() {
  const keyword = form.owner_phone.trim()
  ownerChecked.value = false
  ownerMatches.value = []
  if (!keyword) return
  ownerLoading.value = true
  try {
    const users = await api.staffUsers(keyword)
    ownerMatches.value = users.filter((user) => user.phone === keyword)
    ownerChecked.value = true
  } catch (exc) {
    createError.value = exc instanceof ApiError ? exc.message : '负责人查询失败'
  } finally {
    ownerLoading.value = false
  }
}

async function submitCreate() {
  createError.value = ''
  if (!form.name.trim()) return (createError.value = '请填写商户名称')
  if (!form.category_id) return (createError.value = '请选择经营类目')
  if (!form.contact_phone.trim()) return (createError.value = '请填写联系电话')
  if (!form.city.trim() || !form.district.trim() || !form.address.trim()) {
    return (createError.value = '请填写城市、区县和详细地址')
  }
  const owner = ownerMatches.value[0]
  if (!form.owner_phone.trim() || !owner) {
    return (createError.value = '请先查找并确认已注册的负责人')
  }
  const percent = String(form.commission_percent).trim()
  if (percent && (Number(percent) < 0 || Number(percent) > 100)) {
    return (createError.value = '佣金率需在 0–100% 之间')
  }
  const cycle = Number(form.settlement_cycle_days)
  if (!Number.isInteger(cycle) || cycle < 1 || cycle > 360) {
    return (createError.value = '结算周期需在 1–360 天之间')
  }

  creating.value = true
  try {
    const created = await api.createMerchant({
      name: form.name.trim(),
      short_name: form.short_name.trim(),
      category_id: Number(form.category_id),
      contact_phone: form.contact_phone.trim(),
      province: form.province.trim(),
      city: form.city.trim(),
      district: form.district.trim(),
      address: form.address.trim(),
      commission_rate: percent ? (Number(percent) / 100).toFixed(4) : null,
      settlement_cycle_days: cycle,
      bank_info: form.bank.trim() || form.card_no.trim() ? { bank: form.bank.trim(), card_no: form.card_no.trim() } : {},
      qualifications: form.license_url.trim()
        ? [{ type: 'BUSINESS_LICENSE', file_url: form.license_url.trim() }]
        : [],
      owner_phone: owner.phone,
    })
    createOpen.value = false
    await load(1)
    await openDetail(created)
  } catch (exc) {
    createError.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '创建失败'
  } finally {
    creating.value = false
  }
}


function chipCount(value: string): number {
  if (!value) return summary.value.total
  if (value === 'ACTIVE') return summary.value.active
  if (value === 'PENDING') return summary.value.pending
  if (value === 'RESTING') return summary.value.resting
  if (value === 'BANNED') return summary.value.banned
  return 0
}

function statusClass(value: string): string {
  if (value === 'ACTIVE') return 'tag ok'
  if (value === 'BANNED' || value === 'REJECTED') return 'tag danger'
  return 'tag'
}

function formatRate(rate: number | null | undefined): string {
  return `${((rate ?? 0) * 100).toFixed(1)}%`
}

async function load(target = 1) {
  loading.value = true
  error.value = ''
  router.replace({
    query: {
      ...(status.value ? { status: status.value } : {}),
      ...(keyword.value ? { q: keyword.value } : {}),
      ...(target > 1 ? { page: String(target) } : {}),
    },
  })
  try {
    const result = await api.adminMerchants({
      status: status.value,
      q: keyword.value,
      page: target,
      page_size: 20,
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

function selectFilter(value: string) {
  status.value = value
  load(1)
}

async function openDetail(row: AdminMerchantRow) {
  detail.value = null
  detailError.value = ''
  detailLoading.value = true
  try {
    detail.value = await api.adminMerchantDetail(row.id)
  } catch (exc) {
    detailError.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '加载详情失败'
  } finally {
    detailLoading.value = false
  }
}

function openAction(row: AdminMerchantRow, target: 'ACTIVE' | 'RESTING' | 'BANNED') {
  actionRow.value = row
  actionStatus.value = target
  reason.value = ''
}

async function submitAction() {
  if (!actionRow.value || !reason.value.trim()) return
  submitting.value = true
  error.value = ''
  try {
    await api.changeMerchantStatus(actionRow.value.id, actionStatus.value, reason.value.trim())
    actionRow.value = null
    await load(page.value.page)
  } catch (exc) {
    error.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '操作失败'
  } finally {
    submitting.value = false
  }
}

onMounted(() => load(Number(route.query.page ?? 1)))
</script>

<template>
  <h1>商户管理</h1>

  <div class="metric-strip">
    <div class="metric"><small>商户总数</small><b>{{ summary.total }}</b></div>
    <div class="metric"><small>营业中</small><b>{{ summary.active }}</b></div>
    <div class="metric"><small>待审核</small><b>{{ summary.pending }}</b></div>
    <div class="metric"><small>停业 / 封禁</small><b>{{ summary.resting + summary.banned }}</b></div>
  </div>

  <div class="toolbar">
    <div class="chips">
      <button
        v-for="item in filters"
        :key="item.value"
        class="chip"
        :class="{ on: status === item.value }"
        @click="selectFilter(item.value)"
      >
        {{ item.label }}<em>{{ chipCount(item.value) }}</em>
      </button>
    </div>
    <label class="field">
      <span>关键词</span>
      <input
        v-model="keyword"
        name="q"
        autocomplete="off"
        placeholder="商户名称 / 编号 / 电话…"
        aria-label="商户关键词搜索"
        @keyup.enter="load(1)"
      />
    </label>
    <button class="primary" :disabled="loading" @click="load(1)">查询</button>
    <button class="text" @click="keyword = ''; load(1)">重置</button>
    <button class="primary" style="margin-left: auto" @click="openCreate">新增商户</button>
  </div>

  <div v-if="error" class="error" role="alert">{{ error }}</div>

  <div class="card" style="padding: 0">
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
          <td>{{ row.name }}<br /><span class="muted">{{ row.merchant_no }} · {{ row.contact_phone || '未留电话' }}</span></td>
          <td>{{ row.category_name || '未分类' }}<br /><span class="muted">{{ row.city }}{{ row.district }}</span></td>
          <td><span :class="statusClass(row.status)">{{ STATUS_LABEL[row.status] ?? row.status }}</span></td>
          <td class="money">{{ formatRate(row.commission_rate) }}</td>
          <td class="money">{{ row.today_orders }}</td>
          <td class="money">{{ formatMoney(row.settled_amount) }}</td>
          <td>
            <button class="text" @click="openDetail(row)">查看</button>
            <button
              v-if="row.status === 'PENDING' || row.status === 'REJECTED'"
              class="text"
              style="margin-left: 8px"
              @click="router.push('/audits')"
            >
              去审核
            </button>
            <template v-if="row.status === 'ACTIVE'">
              <button class="text" style="margin-left: 8px" @click="openAction(row, 'RESTING')">停业</button>
              <button class="danger" style="margin-left: 8px" @click="openAction(row, 'BANNED')">封禁</button>
            </template>
            <button
              v-if="row.status === 'RESTING'"
              class="text"
              style="margin-left: 8px"
              @click="openAction(row, 'ACTIVE')"
            >
              恢复营业
            </button>
            <button
              v-if="row.status === 'BANNED'"
              class="text"
              style="margin-left: 8px"
              @click="openAction(row, 'ACTIVE')"
            >
              解除封禁
            </button>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-if="!rows.length" class="empty">{{ loading ? '加载中…' : '该条件下暂无商户' }}</div>
  </div>

  <div class="pager">
    <button class="text" :disabled="page.page <= 1" @click="load(page.page - 1)">上一页</button>
    <span>第 {{ page.page }} 页 · 共 {{ page.total }} 家</span>
    <button class="text" :disabled="!page.has_more" @click="load(page.page + 1)">下一页</button>
  </div>

  <ModalShell v-if="detailLoading || detail || detailError" title="商户详情" wide @close="detail = null; detailError = ''">
    <template v-if="detailLoading">
      <h2>商户详情</h2>
      <div class="muted">加载中…</div>
    </template>
    <template v-else-if="detailError">
      <h2>加载失败</h2>
      <div class="error" role="alert">{{ detailError }}</div>
      <button class="text" @click="detailError = ''">关闭</button>
    </template>
    <template v-else-if="detail">
      <h2>商户详情 · {{ detail.name }}</h2>
      <div class="section-title">基础信息</div>
      <div class="detail-grid">
        <span>商户号</span><b>{{ detail.merchant_no }}</b>
        <span>状态</span><b><span :class="statusClass(detail.status)">{{ STATUS_LABEL[detail.status] ?? detail.status }}</span></b>
        <span>经营类目</span><b>{{ detail.category_name || '未分类' }}</b>
        <span>所属区域</span><b>{{ detail.province }}{{ detail.city }}{{ detail.district }}</b>
        <span>详细地址</span><b>{{ detail.address || '-' }}</b>
        <span>联系人</span><b>{{ detail.contact_phone || '-' }}</b>
        <span>佣金率</span>
        <b>{{ formatRate(detail.commission_rate) }}
          <span class="muted">（{{ detail.commission_override === null ? '继承类目' : '商户覆盖' }}）</span>
        </b>
        <span>结算周期</span><b>{{ detail.settlement_cycle_days }} 天</b>
        <span>开店时间</span><b>{{ detail.opened_at ? formatDateTime(detail.opened_at) : '-' }}</b>
      </div>

      <div class="section-title">经营表现</div>
      <div class="detail-grid">
        <span>今日订单</span><b>{{ detail.today_orders }} 笔</b>
        <span>累计 GMV</span><b>{{ formatMoney(detail.gmv_total) }}</b>
        <span>累计结算</span><b>{{ formatMoney(detail.settled_amount) }}</b>
        <span>收款账户</span><b>{{ detail.bank_last4 ? `尾号 ${detail.bank_last4}` : '未配置' }}</b>
      </div>

      <div class="section-title">资金账户</div>
      <div class="detail-grid">
        <span>待结算</span><b>{{ formatMoney(detail.balances.pending_amount) }}</b>
        <span>冻结</span><b>{{ formatMoney(detail.balances.frozen_amount) }}</b>
        <span>可提现</span><b>{{ formatMoney(detail.balances.available_amount) }}</b>
        <span>提现中</span><b>{{ formatMoney(detail.balances.withdrawing_amount) }}</b>
      </div>

      <div class="section-title">资质材料</div>
      <div v-if="detail.qualifications.length" class="detail-grid">
        <template v-for="item in detail.qualifications" :key="item.id">
          <span>{{ item.type_label }}</span>
          <b>
            <a :href="item.file_url" target="_blank">查看材料</a>
            · {{ item.audit_status }}
            <span v-if="item.reject_reason" class="muted">（{{ item.reject_reason }}）</span>
          </b>
        </template>
      </div>
      <div v-else class="muted">暂无上传资质</div>

      <div class="section-title">员工</div>
      <div v-if="detail.staff.length" class="card" style="padding: 0">
        <table>
          <thead>
            <tr><th>员工</th><th>角色</th><th>状态</th><th>加入时间</th></tr>
          </thead>
          <tbody>
            <tr v-for="item in detail.staff" :key="item.id">
              <td>{{ item.nickname || `用户 #${item.user_id}` }}</td>
              <td>{{ item.role_label }}</td>
              <td>{{ item.status }}</td>
              <td>{{ item.joined_at ? formatDateTime(item.joined_at) : '-' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else class="muted">暂无员工账号</div>

      <div class="toolbar" style="margin: 0">
        <button class="text" @click="detail = null">关闭</button>
      </div>
    </template>
  </ModalShell>

  <ModalShell v-if="actionRow" :title="`${STATUS_LABEL[actionStatus]} · ${actionRow.name}`" @close="actionRow = null">
    <h2>{{ STATUS_LABEL[actionStatus] }} · {{ actionRow.name }}</h2>
    <div class="muted">
      停业与封禁会立即停止新订单；在途订单与售后的处理规则待定，本次不做自动取消。
    </div>
    <label class="field">
      <span>原因</span>
      <textarea v-model="reason" rows="3" name="reason" placeholder="请填写变更原因…" />
    </label>
    <div class="toolbar" style="margin: 0">
      <button class="primary" :disabled="submitting || !reason.trim()" @click="submitAction">确认</button>
      <button class="text" @click="actionRow = null">取消</button>
    </div>
  </ModalShell>

  <ModalShell v-if="createOpen" title="新增商户" wide @close="createOpen = false">
    <h2>新增商户</h2>
    <div class="muted">创建后商户立即营业；负责人必须是已注册用户，创建完成后可在商户中心登录操作。</div>
    <div v-if="createError" class="error" role="alert">{{ createError }}</div>

    <div class="section-title">基本资料</div>
    <div class="form-grid">
      <label class="field">
        <span>商户名称</span>
        <input v-model="form.name" name="name" autocomplete="organization" placeholder="如：山野咖啡 · 文三店…" />
      </label>
      <label class="field">
        <span>简称</span>
        <input v-model="form.short_name" name="short_name" autocomplete="off" placeholder="选填…" />
      </label>
      <label class="field">
        <span>经营类目</span>
        <select v-model="form.category_id" name="category_id">
          <option value="">请选择类目</option>
          <option v-for="item in categories" :key="item.id" :value="String(item.id)">{{ item.name }}</option>
        </select>
      </label>
      <label class="field">
        <span>联系电话</span>
        <input
          v-model="form.contact_phone"
          name="contact_phone"
          type="tel"
          inputmode="tel"
          autocomplete="tel"
          placeholder="门店对外电话…"
        />
      </label>
      <label class="field">
        <span>省份</span>
        <input v-model="form.province" name="province" autocomplete="address-level1" placeholder="如：浙江…" />
      </label>
      <label class="field">
        <span>城市</span>
        <input v-model="form.city" name="city" autocomplete="address-level2" placeholder="如：杭州…" />
      </label>
      <label class="field">
        <span>区县</span>
        <input v-model="form.district" name="district" autocomplete="address-level3" placeholder="如：西湖区…" />
      </label>
      <label class="field">
        <span>详细地址</span>
        <input
          v-model="form.address"
          name="address"
          autocomplete="street-address"
          placeholder="如：文三路 90 号…"
        />
      </label>
    </div>

    <div class="section-title">负责人</div>
    <div class="form-grid">
      <label class="field">
        <span>负责人手机号</span>
        <input
          v-model="form.owner_phone"
          name="owner_phone"
          type="tel"
          inputmode="numeric"
          autocomplete="tel"
          placeholder="已注册用户的手机号…"
          @keyup.enter="lookupOwner"
        />
      </label>
      <div class="field">
        <span>账号校验</span>
        <div style="display: flex; gap: 8px; align-items: center">
          <button class="text" :disabled="ownerLoading || !form.owner_phone.trim()" @click="lookupOwner">
            {{ ownerLoading ? '查询中…' : '查找负责人' }}
          </button>
          <span v-if="ownerChecked && ownerMatches.length" class="tag ok">
            已匹配：{{ ownerMatches[0].nickname || `用户 #${ownerMatches[0].id}` }}
          </span>
          <span v-else-if="ownerChecked" class="muted">未找到该手机号，请先让负责人登录一次</span>
        </div>
      </div>
    </div>

    <div class="section-title">经营设置</div>
    <div class="form-grid">
      <label class="field">
        <span>佣金率（%）</span>
        <input
          v-model="form.commission_percent"
          name="commission_percent"
          type="number"
          inputmode="decimal"
          min="0"
          max="100"
          step="0.1"
          placeholder="留空则继承类目默认…"
        />
      </label>
      <label class="field">
        <span>结算周期（天）</span>
        <input
          v-model="form.settlement_cycle_days"
          name="settlement_cycle_days"
          type="number"
          inputmode="numeric"
          min="1"
          max="360"
        />
      </label>
    </div>

    <div class="section-title">收款与资质（选填）</div>
    <div class="form-grid">
      <label class="field">
        <span>开户行</span>
        <input v-model="form.bank" name="bank" autocomplete="off" placeholder="如：招商银行…" />
      </label>
      <label class="field">
        <span>银行卡号</span>
        <input v-model="form.card_no" name="card_no" inputmode="numeric" autocomplete="off" placeholder="加密存储…" />
      </label>
      <div class="field">
        <span>营业执照</span>
        <MediaPicker v-model="form.license_url" kind="IMAGE" />
      </div>
    </div>

    <div class="toolbar" style="margin: 0">
      <button class="primary" :disabled="creating" @click="submitCreate">
        {{ creating ? '创建中…' : '创建商户' }}
      </button>
      <button class="text" @click="createOpen = false">取消</button>
    </div>
  </ModalShell>
</template>
