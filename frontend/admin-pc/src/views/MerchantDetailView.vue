<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, ApiError, type AdminMerchantDetail } from '../api'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import ModalShell from '../components/ModalShell.vue'
import PageHeader from '../components/PageHeader.vue'
import StatusTag from '../components/StatusTag.vue'
import { formatDateTime, formatMoney, INDUSTRY_OPTIONS } from '../format'

const route = useRoute()
const router = useRouter()
const merchantId = computed(() => Number(route.params.id))

const detail = ref<AdminMerchantDetail | null>(null)
const loading = ref(true)
const error = ref('')
const message = ref('')
const tab = ref<'OVERVIEW' | 'STAFF' | 'QUALIFICATION' | 'FUND'>('OVERVIEW')

const actionStatus = ref<'' | 'ACTIVE' | 'RESTING' | 'BANNED'>('')
const submitting = ref(false)

const locationOpen = ref(false)
const locationError = ref('')
const locationSaving = ref(false)
const locationForm = reactive({ lng: '', lat: '', province: '', city: '', district: '', address: '' })

const profileOpen = ref(false)
const profileError = ref('')
const profileSaving = ref(false)
const profileForm = reactive({ industry: 'OTHER', delivery_fee_yuan: '0' })

function openProfile() {
  if (!detail.value) return
  profileForm.industry = detail.value.industry || 'OTHER'
  profileForm.delivery_fee_yuan = (detail.value.delivery_fee / 100).toFixed(2)
  profileError.value = ''
  profileOpen.value = true
}

async function submitProfile() {
  if (!detail.value) return
  const fee = Math.round(Number(profileForm.delivery_fee_yuan || 0) * 100)
  if (!Number.isFinite(fee) || fee < 0) {
    profileError.value = '配送费不能为负'
    return
  }
  profileSaving.value = true
  profileError.value = ''
  try {
    await api.updateMerchantProfile(detail.value.id, {
      industry: profileForm.industry,
      delivery_fee: fee,
    })
    profileOpen.value = false
    message.value = '归类信息已保存'
    await load()
  } catch (exc) {
    profileError.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '保存归类信息失败'
  } finally {
    profileSaving.value = false
  }
}

function formatRate(rate: number | null | undefined): string {
  return `${((rate ?? 0) * 100).toFixed(1)}%`
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    detail.value = await api.adminMerchantDetail(merchantId.value)
  } catch (exc) {
    error.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '加载商户详情失败'
  } finally {
    loading.value = false
  }
}

function openLocation() {
  if (!detail.value) return
  locationForm.lng = detail.value.lng === null ? '' : String(detail.value.lng)
  locationForm.lat = detail.value.lat === null ? '' : String(detail.value.lat)
  locationForm.province = detail.value.province
  locationForm.city = detail.value.city
  locationForm.district = detail.value.district
  locationForm.address = detail.value.address
  locationError.value = ''
  locationOpen.value = true
}

async function submitLocation() {
  if (!detail.value) return
  const lng = Number(locationForm.lng)
  const lat = Number(locationForm.lat)
  if (!Number.isFinite(lng) || lng < -180 || lng > 180) {
    locationError.value = '经度需在 -180 到 180 之间'
    return
  }
  if (!Number.isFinite(lat) || lat < -90 || lat > 90) {
    locationError.value = '纬度需在 -90 到 90 之间'
    return
  }
  locationSaving.value = true
  locationError.value = ''
  try {
    await api.updateMerchantLocation(detail.value.id, {
      lng: lng.toFixed(6),
      lat: lat.toFixed(6),
      province: locationForm.province.trim(),
      city: locationForm.city.trim(),
      district: locationForm.district.trim(),
      address: locationForm.address.trim(),
    })
    locationOpen.value = false
    message.value = '定位已保存'
    await load()
  } catch (exc) {
    locationError.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '保存定位失败'
  } finally {
    locationSaving.value = false
  }
}

async function submitAction(reason: string) {
  if (!detail.value || !actionStatus.value) return
  submitting.value = true
  error.value = ''
  try {
    await api.changeMerchantStatus(detail.value.id, actionStatus.value, reason)
    actionStatus.value = ''
    message.value = '商户状态已更新'
    await load()
  } catch (exc) {
    error.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '操作失败'
  } finally {
    submitting.value = false
  }
}

function actionTitle(): string {
  if (actionStatus.value === 'BANNED') return '封禁商户'
  if (actionStatus.value === 'RESTING') return '停业商户'
  if (actionStatus.value === 'ACTIVE') return '恢复营业'
  return ''
}

onMounted(load)
</script>

<template>
  <PageHeader :title="detail ? `商户详情 · ${detail.name}` : '商户详情'">
    <template #actions>
      <button class="outline" @click="router.push('/merchants')">返回列表</button>
      <button v-if="detail" class="outline" @click="openProfile">编辑归类</button>
      <button v-if="detail" class="outline" @click="openLocation">设置定位</button>
      <button v-if="detail?.status === 'ACTIVE'" class="outline" @click="actionStatus = 'RESTING'">停业</button>
      <button v-if="detail?.status === 'ACTIVE'" class="outline" @click="actionStatus = 'BANNED'">封禁</button>
      <button
        v-if="detail?.status === 'RESTING' || detail?.status === 'BANNED'"
        class="outline"
        @click="actionStatus = 'ACTIVE'"
      >
        恢复营业
      </button>
    </template>
  </PageHeader>

  <div v-if="error" class="error" role="alert">{{ error }}</div>
  <div v-if="message" class="notice" aria-live="polite">{{ message }}</div>
  <div v-if="loading" class="empty">加载中…</div>

  <template v-if="detail">
    <div class="summary-strip">
      <div class="card mini">
        <small>当前状态</small>
        <StatusTag :status="detail.status" />
      </div>
      <div class="card mini">
        <small>经营类目</small>
        <b>{{ detail.category_name || '未分类' }}</b>
      </div>
      <div class="card mini">
        <small>生效佣金率</small>
        <b>{{ formatRate(detail.commission_rate) }}</b>
        <span class="muted">{{ detail.commission_override === null ? '继承类目' : '商户覆盖' }}</span>
      </div>
      <div class="card mini">
        <small>累计 GMV</small>
        <b>{{ formatMoney(detail.gmv_total) }}</b>
      </div>
      <div class="card mini">
        <small>可提现余额</small>
        <b>{{ formatMoney(detail.balances.available_amount) }}</b>
      </div>
    </div>

    <div class="chips tab-strip">
      <button class="chip" :class="{ on: tab === 'OVERVIEW' }" @click="tab = 'OVERVIEW'">概览</button>
      <button class="chip" :class="{ on: tab === 'STAFF' }" @click="tab = 'STAFF'">员工（{{ detail.staff.length }}）</button>
      <button class="chip" :class="{ on: tab === 'QUALIFICATION' }" @click="tab = 'QUALIFICATION'">
        资质（{{ detail.qualifications.length }}）
      </button>
      <button class="chip" :class="{ on: tab === 'FUND' }" @click="tab = 'FUND'">资金</button>
    </div>

    <div v-if="tab === 'OVERVIEW'" class="card">
      <div class="section-title" style="margin-top: 0">基础信息</div>
      <div class="detail-grid">
        <span>商户号</span><b>{{ detail.merchant_no }}</b>
        <span>简称</span><b>{{ detail.short_name || '-' }}</b>
        <span>所属区域</span><b>{{ detail.province }}{{ detail.city }}{{ detail.district }}</b>
        <span>详细地址</span><b>{{ detail.address || '-' }}</b>
        <span>定位坐标</span>
        <b>
          <span v-if="detail.lng !== null && detail.lat !== null">{{ detail.lng }}, {{ detail.lat }}</span>
          <span v-else class="muted">未设置（消费者端暂不支持导航）</span>
        </b>
        <span>联系电话</span><b>{{ detail.contact_phone || '-' }}</b>
        <span>行业</span><b>{{ detail.industry_label || '未设置' }}</b>
        <span>配送费</span><b>{{ formatMoney(detail.delivery_fee) }}</b>
        <span>结算周期</span><b>{{ detail.settlement_cycle_days }} 天</b>
        <span>开店时间</span><b>{{ detail.opened_at ? formatDateTime(detail.opened_at) : '-' }}</b>
        <span>创建时间</span><b>{{ formatDateTime(detail.created_at) }}</b>
        <span>收款账户</span><b>{{ detail.bank_last4 ? `尾号 ${detail.bank_last4}` : '未配置' }}</b>
      </div>
      <div class="section-title">经营表现</div>
      <div class="detail-grid">
        <span>今日订单</span><b>{{ detail.today_orders }} 笔</b>
        <span>累计结算</span><b>{{ formatMoney(detail.settled_amount) }}</b>
      </div>
      <div v-if="detail.description" class="section-title">商户简介</div>
      <div v-if="detail.description" class="muted">{{ detail.description }}</div>
    </div>

    <div v-else-if="tab === 'STAFF'" class="table-wrap">
      <table>
        <thead>
          <tr><th>员工</th><th>角色</th><th>状态</th><th>加入时间</th></tr>
        </thead>
        <tbody>
          <tr v-for="item in detail.staff" :key="item.id">
            <td>{{ item.nickname || `用户 #${item.user_id}` }}</td>
            <td>{{ item.role_label }}</td>
            <td><StatusTag :status="item.status" /></td>
            <td>{{ item.joined_at ? formatDateTime(item.joined_at) : '-' }}</td>
          </tr>
        </tbody>
      </table>
      <div v-if="!detail.staff.length" class="empty">暂无员工账号</div>
    </div>

    <div v-else-if="tab === 'QUALIFICATION'" class="card">
      <div v-if="detail.qualifications.length" class="quals">
        <div v-for="item in detail.qualifications" :key="item.id" class="qual-row">
          <div>
            <b>{{ item.type_label }}</b>
            <div class="muted">{{ item.expire_at ? `有效期至 ${item.expire_at}` : '长期有效' }}</div>
          </div>
          <div class="actions">
            <StatusTag :status="item.audit_status" />
            <a :href="item.file_url" target="_blank" rel="noopener">查看材料</a>
            <span v-if="item.reject_reason" class="muted">{{ item.reject_reason }}</span>
          </div>
        </div>
      </div>
      <div v-else class="empty">暂无上传资质</div>
    </div>

    <div v-else class="card">
      <div class="section-title" style="margin-top: 0">资金账户</div>
      <div class="detail-grid">
        <span>待结算</span><b>{{ formatMoney(detail.balances.pending_amount) }}</b>
        <span>冻结</span><b>{{ formatMoney(detail.balances.frozen_amount) }}</b>
        <span>可提现</span><b>{{ formatMoney(detail.balances.available_amount) }}</b>
        <span>提现中</span><b>{{ formatMoney(detail.balances.withdrawing_amount) }}</b>
      </div>
      <div class="muted" style="margin-top: 12px">余额只能通过记账事务变更；如有差异请走资金对账与反向分录。</div>
    </div>
  </template>

  <ConfirmDialog
    v-if="actionStatus"
    :title="actionTitle()"
    :message="actionStatus === 'ACTIVE' ? '恢复后商户可重新接单。' : '停业与封禁立即停止新订单；在途订单与售后不自动取消。'"
    reason-label="变更原因"
    reason-required
    :danger="actionStatus === 'BANNED'"
    :busy="submitting"
    @confirm="submitAction"
    @close="actionStatus = ''"
  />

  <ModalShell v-if="locationOpen && detail" :title="`设置定位 · ${detail.name}`" @close="locationOpen = false">
    <div class="modal-head">
      <h2>设置定位 · {{ detail.name }}</h2>
      <button class="modal-close" type="button" aria-label="关闭" @click="locationOpen = false">✕</button>
    </div>
    <div class="muted">坐标统一使用高德 GCJ-02；高德 Key 启用后可用地图选点替换手填。</div>
    <div v-if="locationError" class="error" role="alert">{{ locationError }}</div>
    <div class="form-grid">
      <label class="field">
        <span>经度（lng）</span>
        <input v-model="locationForm.lng" name="lng" autocomplete="off" placeholder="如：120.155100" />
      </label>
      <label class="field">
        <span>纬度（lat）</span>
        <input v-model="locationForm.lat" name="lat" autocomplete="off" placeholder="如：30.274100" />
      </label>
      <label class="field">
        <span>省</span>
        <input v-model="locationForm.province" name="province" autocomplete="off" placeholder="如：浙江" />
      </label>
      <label class="field">
        <span>市</span>
        <input v-model="locationForm.city" name="city" autocomplete="off" placeholder="如：杭州" />
      </label>
      <label class="field">
        <span>区县</span>
        <input v-model="locationForm.district" name="district" autocomplete="off" placeholder="如：西湖区" />
      </label>
      <label class="field">
        <span>详细地址</span>
        <input v-model="locationForm.address" name="address" autocomplete="off" placeholder="如：文三路 100 号…" />
      </label>
    </div>
    <div class="toolbar" style="margin: 0; justify-content: flex-end">
      <button class="outline" @click="locationOpen = false">取消</button>
      <button class="primary" :disabled="locationSaving" @click="submitLocation">
        {{ locationSaving ? '保存中…' : '保存定位' }}
      </button>
    </div>
  </ModalShell>

  <ModalShell v-if="profileOpen && detail" :title="`编辑归类 · ${detail.name}`" @close="profileOpen = false">
    <div class="modal-head">
      <h2>编辑归类 · {{ detail.name }}</h2>
      <button class="modal-close" type="button" aria-label="关闭" @click="profileOpen = false">✕</button>
    </div>
    <div class="muted">行业与配送费仅后台可见，用于归类统计与配送订单计费。</div>
    <div v-if="profileError" class="error" role="alert">{{ profileError }}</div>
    <div class="form-grid">
      <label class="field">
        <span>行业</span>
        <select v-model="profileForm.industry">
          <option v-for="item in INDUSTRY_OPTIONS" :key="item.value" :value="item.value">{{ item.label }}</option>
        </select>
      </label>
      <label class="field">
        <span>配送费（元）</span>
        <input v-model="profileForm.delivery_fee_yuan" type="number" min="0" step="0.01" />
      </label>
    </div>
    <div class="toolbar" style="margin: 0; justify-content: flex-end">
      <button class="outline" @click="profileOpen = false">取消</button>
      <button class="primary" :disabled="profileSaving" @click="submitProfile">
        {{ profileSaving ? '保存中…' : '保存' }}
      </button>
    </div>
  </ModalShell>
</template>

<style scoped>
.summary-strip {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: var(--gap-md);
}

.card.mini {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 14px 16px;
}

.card.mini small {
  color: var(--ink-3);
  font-size: var(--fs-help);
}

.card.mini .tag {
  align-self: flex-start;
}

.card.mini b {
  font-size: 17px;
  font-variant-numeric: tabular-nums;
}

.tab-strip {
  margin-bottom: var(--gap-md);
}

.quals {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.qual-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid var(--line);
}

.qual-row:last-child {
  border-bottom: none;
}

@media (max-width: 1100px) {
  .summary-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
