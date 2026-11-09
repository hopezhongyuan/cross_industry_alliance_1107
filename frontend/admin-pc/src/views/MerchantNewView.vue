<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, ApiError, type CategoryRow, type StaffUser } from '../api'
import MediaPicker from '../components/MediaPicker.vue'
import PageHeader from '../components/PageHeader.vue'

const router = useRouter()
const categories = ref<CategoryRow[]>([])
const ownerMatches = ref<StaffUser[]>([])
const ownerLoading = ref(false)
const ownerChecked = ref(false)
const creating = ref(false)
const error = ref('')

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

async function loadCategories() {
  try {
    categories.value = await api.categories()
  } catch (exc) {
    error.value = exc instanceof ApiError ? exc.message : '类目加载失败'
  }
}

async function lookupOwner() {
  const keyword = form.owner_phone.trim()
  ownerChecked.value = false
  ownerMatches.value = []
  if (!keyword) return
  ownerLoading.value = true
  error.value = ''
  try {
    const users = await api.staffUsers(keyword)
    ownerMatches.value = users.filter((user) => user.phone === keyword)
    ownerChecked.value = true
  } catch (exc) {
    error.value = exc instanceof ApiError ? exc.message : '负责人查询失败'
  } finally {
    ownerLoading.value = false
  }
}

async function submit() {
  error.value = ''
  if (!form.name.trim()) return (error.value = '请填写商户名称')
  if (!form.category_id) return (error.value = '请选择经营类目')
  if (!form.contact_phone.trim()) return (error.value = '请填写联系电话')
  if (!form.city.trim() || !form.district.trim() || !form.address.trim()) {
    return (error.value = '请填写城市、区县和详细地址')
  }
  const owner = ownerMatches.value[0]
  if (!form.owner_phone.trim() || !owner) {
    return (error.value = '请先查找并确认已注册的负责人')
  }
  const percent = String(form.commission_percent).trim()
  if (percent && (Number(percent) < 0 || Number(percent) > 100)) {
    return (error.value = '佣金率需在 0–100% 之间')
  }
  const cycle = Number(form.settlement_cycle_days)
  if (!Number.isInteger(cycle) || cycle < 1 || cycle > 360) {
    return (error.value = '结算周期需在 1–360 天之间')
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
      bank_info:
        form.bank.trim() || form.card_no.trim() ? { bank: form.bank.trim(), card_no: form.card_no.trim() } : {},
      qualifications: form.license_url
        ? [{ type: 'BUSINESS_LICENSE', file_url: form.license_url }]
        : [],
      owner_phone: owner.phone,
    })
    router.push(`/merchants/${created.id}`)
  } catch (exc) {
    error.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '创建失败'
  } finally {
    creating.value = false
  }
}

onMounted(loadCategories)
</script>

<template>
  <PageHeader title="新建商户" description="创建后商户立即营业；负责人必须是已注册用户。">
    <template #actions>
      <button class="outline" @click="router.push('/merchants')">返回列表</button>
      <button class="primary" :disabled="creating" @click="submit">{{ creating ? '创建中…' : '创建商户' }}</button>
    </template>
  </PageHeader>

  <div v-if="error" class="error" role="alert">{{ error }}</div>

  <div class="new-layout">
    <form class="card" @submit.prevent="submit">
      <div class="form-section" style="margin-top: 0">
        <div class="section-title" style="margin-top: 0">基本资料</div>
        <div class="form-grid">
          <label class="field">
            <span>商户名称<i class="req">*</i></span>
            <input v-model="form.name" name="name" autocomplete="organization" placeholder="如：山野咖啡 · 文三店…" />
          </label>
          <label class="field">
            <span>简称</span>
            <input v-model="form.short_name" name="short_name" autocomplete="off" placeholder="选填…" />
          </label>
          <label class="field">
            <span>经营类目<i class="req">*</i></span>
            <select v-model="form.category_id" name="category_id">
              <option value="">请选择类目</option>
              <option v-for="item in categories" :key="item.id" :value="String(item.id)">{{ item.name }}</option>
            </select>
            <span class="field-help">经营类目决定默认佣金率与消费者端归类。</span>
          </label>
          <label class="field">
            <span>联系电话<i class="req">*</i></span>
            <input
              v-model="form.contact_phone"
              name="contact_phone"
              type="tel"
              inputmode="tel"
              autocomplete="tel"
              placeholder="门店对外电话…"
            />
          </label>
        </div>
      </div>

      <div class="form-section">
        <div class="section-title" style="margin-top: 0">门店地址</div>
        <div class="form-grid">
          <label class="field">
            <span>省份</span>
            <input v-model="form.province" name="province" autocomplete="address-level1" placeholder="如：浙江…" />
          </label>
          <label class="field">
            <span>城市<i class="req">*</i></span>
            <input v-model="form.city" name="city" autocomplete="address-level2" placeholder="如：杭州…" />
          </label>
          <label class="field">
            <span>区县<i class="req">*</i></span>
            <input v-model="form.district" name="district" autocomplete="address-level3" placeholder="如：西湖区…" />
          </label>
          <label class="field">
            <span>详细地址<i class="req">*</i></span>
            <input v-model="form.address" name="address" autocomplete="street-address" placeholder="如：文三路 90 号…" />
          </label>
        </div>
        <span class="field-help">创建后可在商户详情补充高德 GCJ-02 经纬度，用于消费者端导航。</span>
      </div>

      <div class="form-section">
        <div class="section-title" style="margin-top: 0">负责人</div>
        <div class="form-grid">
          <label class="field">
            <span>负责人手机号<i class="req">*</i></span>
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
            <div style="display: flex; gap: 8px; align-items: center; height: 38px">
              <button class="outline" type="button" :disabled="ownerLoading || !form.owner_phone.trim()" @click="lookupOwner">
                {{ ownerLoading ? '查询中…' : '查找负责人' }}
              </button>
              <span v-if="ownerChecked && ownerMatches.length" class="tag ok">
                已匹配：{{ ownerMatches[0].nickname || `用户 #${ownerMatches[0].id}` }}
              </span>
              <span v-else-if="ownerChecked" class="muted">未找到该手机号，请先让负责人登录一次</span>
            </div>
            <span class="field-help">负责人将成为商户 OWNER，可在商户中心登录。</span>
          </div>
        </div>
      </div>

      <div class="form-section">
        <div class="section-title" style="margin-top: 0">经营设置</div>
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
            <span class="field-help">平台抽佣比例，填写 5 表示 5%；留空继承类目默认值。</span>
          </label>
          <label class="field">
            <span>结算周期（天）</span>
            <input v-model="form.settlement_cycle_days" name="settlement_cycle_days" type="number" min="1" max="360" />
            <span class="field-help">订单完成后第 N 天结算，范围 1–360。</span>
          </label>
        </div>
      </div>

      <div class="form-section">
        <div class="section-title" style="margin-top: 0">收款与资质（选填）</div>
        <div class="form-grid">
          <label class="field">
            <span>开户行</span>
            <input v-model="form.bank" name="bank" autocomplete="off" placeholder="如：招商银行…" />
          </label>
          <label class="field">
            <span>银行卡号</span>
            <input
              v-model="form.card_no"
              name="card_no"
              inputmode="numeric"
              autocomplete="off"
              placeholder="加密存储，仅显示尾号…"
            />
            <span class="field-help">银行卡号加密存储，后台只展示尾号；请勿在备注类字段填写卡号。</span>
          </label>
          <div class="field span-2">
            <span>营业执照</span>
            <MediaPicker v-model="form.license_url" kind="IMAGE" hint="建议 1200×900 以上，JPG/PNG，≤2MB" />
            <span class="field-help">上传后自动进入资质审核队列。</span>
          </div>
        </div>
      </div>
    </form>

    <aside>
      <div class="card">
        <div class="section-title" style="margin-top: 0">创建后会发生什么</div>
        <div class="muted" style="line-height: 24px">
          · 商户状态立即为「营业中」，负责人可在商户中心登录。<br />
          · 营业执照进入资质审核队列，可在审核中心处理。<br />
          · 佣金率留空时继承类目默认值，可在商户详情中覆盖。<br />
          · 定位坐标未设置时，消费者端暂不支持导航到店。
        </div>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.new-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: var(--gap-md);
  align-items: start;
}

@media (max-width: 1080px) {
  .new-layout {
    grid-template-columns: 1fr;
  }
}
</style>
