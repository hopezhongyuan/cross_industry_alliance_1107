<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { api, ApiError, type AdminPlatformConfigPayload } from '../api'
import MediaPicker from '../components/MediaPicker.vue'
import PageHeader from '../components/PageHeader.vue'
import SecretInput from '../components/SecretInput.vue'
import { formatDateTime } from '../format'

const form = reactive<AdminPlatformConfigPayload>({
  platform_name: '',
  logo_url: '',
  contact_phone: '',
  company_name: '',
  icp_no: '',
  privacy_policy: '',
  user_agreement: '',
  agreement_version: '',
  miniapp_app_id: '',
  miniapp_app_secret: '',
  miniapp_original_id: '',
  amap_web_key: '',
  amap_js_key: '',
  amap_js_security_code: '',
  amap_enabled: false,
})
const secretState = reactive({
  miniapp_app_secret_configured: false,
  miniapp_app_secret_masked: '',
  amap_web_key_configured: false,
  amap_web_key_masked: '',
  amap_js_security_code_configured: false,
  amap_js_security_code_masked: '',
})
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const message = ref('')
const updatedBy = ref('')
const updatedAt = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const config = await api.adminPlatformConfig()
    form.platform_name = config.platform_name
    form.logo_url = config.logo_url
    form.contact_phone = config.contact_phone
    form.company_name = config.company_name
    form.icp_no = config.icp_no
    form.privacy_policy = config.privacy_policy
    form.user_agreement = config.user_agreement
    form.agreement_version = config.agreement_version
    form.miniapp_app_id = config.miniapp_app_id
    form.miniapp_original_id = config.miniapp_original_id
    form.amap_js_key = config.amap_js_key
    form.amap_enabled = config.amap_enabled
    applySecrets(config)
    updatedBy.value = config.updated_by_name
    updatedAt.value = config.updated_at
  } catch (exc) {
    error.value = exc instanceof ApiError ? exc.message : '加载失败'
  } finally {
    loading.value = false
  }
}

function applySecrets(config: {
  miniapp_app_secret_configured: boolean
  miniapp_app_secret_masked: string
  amap_web_key_configured: boolean
  amap_web_key_masked: string
  amap_js_security_code_configured: boolean
  amap_js_security_code_masked: string
}) {
  secretState.miniapp_app_secret_configured = config.miniapp_app_secret_configured
  secretState.miniapp_app_secret_masked = config.miniapp_app_secret_masked
  secretState.amap_web_key_configured = config.amap_web_key_configured
  secretState.amap_web_key_masked = config.amap_web_key_masked
  secretState.amap_js_security_code_configured = config.amap_js_security_code_configured
  secretState.amap_js_security_code_masked = config.amap_js_security_code_masked
}

async function save() {
  if (!form.platform_name.trim()) {
    error.value = '平台名称必填'
    return
  }
  saving.value = true
  error.value = ''
  message.value = ''
  try {
    const config = await api.saveAdminPlatformConfig({ ...form, platform_name: form.platform_name.trim() })
    applySecrets(config)
    form.miniapp_app_secret = ''
    form.amap_web_key = ''
    form.amap_js_security_code = ''
    updatedBy.value = config.updated_by_name
    updatedAt.value = config.updated_at
    message.value = '已保存'
  } catch (exc) {
    error.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '保存失败'
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <PageHeader title="平台设置" description="平台基础信息、协议正文、小程序与高德参数；密钥只写不回显。">
    <template #actions>
      <button class="primary" :disabled="saving || loading" @click="save">{{ saving ? '保存中…' : '保存设置' }}</button>
    </template>
  </PageHeader>

  <div v-if="error" class="error" role="alert">{{ error }}</div>
  <div v-if="message" class="notice" aria-live="polite">{{ message }}</div>

  <form class="card" @submit.prevent="save">
    <div class="section-title" style="margin-top: 0">基础信息</div>
    <div class="form-grid">
      <label class="field">
        <span>平台名称<i class="req">*</i></span>
        <input v-model="form.platform_name" name="platform_name" autocomplete="off" placeholder="如：异业联盟…" />
      </label>
      <label class="field">
        <span>联系电话</span>
        <input v-model="form.contact_phone" name="contact_phone" autocomplete="off" placeholder="客服电话…" />
      </label>
      <label class="field">
        <span>公司主体</span>
        <input v-model="form.company_name" name="company_name" autocomplete="off" placeholder="运营主体…" />
      </label>
      <label class="field">
        <span>ICP 备案号</span>
        <input v-model="form.icp_no" name="icp_no" autocomplete="off" placeholder="如：浙ICP备…" />
      </label>
      <div class="field">
        <span>平台 Logo</span>
        <MediaPicker v-model="form.logo_url" kind="IMAGE" hint="建议 512×512（1:1），PNG，≤200KB" />
      </div>
    </div>

    <div class="form-section">
      <div class="section-title" style="margin-top: 0">协议</div>
      <div class="form-grid">
        <label class="field">
          <span>协议版本</span>
          <input v-model="form.agreement_version" name="agreement_version" autocomplete="off" placeholder="如：2026.11…" />
          <span class="field-help">版本变更后需在消费者端重新弹窗确认（TBD）。</span>
        </label>
      </div>
      <label class="field">
        <span>隐私协议正文</span>
        <textarea v-model="form.privacy_policy" rows="6" placeholder="请输入隐私协议正文…" />
        <span class="field-help">纯文本，前台按段落渲染；建议单段不超过 6 行。</span>
      </label>
      <label class="field">
       <span>用户注册协议正文</span>
        <textarea v-model="form.user_agreement" rows="6" placeholder="请输入用户注册协议正文…" />
      </label>
    </div>

    <div class="form-section">
      <div class="section-title" style="margin-top: 0">小程序参数</div>
      <div class="form-grid">
        <label class="field">
          <span>AppID</span>
          <input v-model="form.miniapp_app_id" name="miniapp_app_id" autocomplete="off" placeholder="wx…" />
        </label>
        <label class="field">
          <span>原始 ID</span>
          <input v-model="form.miniapp_original_id" name="miniapp_original_id" autocomplete="off" placeholder="gh_…" />
        </label>
      </div>
      <SecretInput
        v-model="form.miniapp_app_secret"
        label="AppSecret"
        :configured="secretState.miniapp_app_secret_configured"
        :masked="secretState.miniapp_app_secret_masked"
        placeholder="请输入小程序 AppSecret…"
      />
    </div>

    <div class="form-section">
      <div class="section-title" style="margin-top: 0">高德地图</div>
      <div class="muted" style="margin-bottom: 10px">
        暂无 Key 时请保持关闭；Key 到位后填入并启用，后台地图选点与用户端地图即可生效。
      </div>
      <SecretInput
        v-model="form.amap_web_key"
        label="Web 服务 Key"
        :configured="secretState.amap_web_key_configured"
        :masked="secretState.amap_web_key_masked"
        placeholder="服务端地理编码 Key…"
      />
      <label class="field">
        <span>JS API Key</span>
        <input v-model="form.amap_js_key" name="amap_js_key" autocomplete="off" placeholder="Web 端（JS API）Key…" />
        <span class="field-help">JS API Key 会下发到前端，不属于保密字段。</span>
      </label>
      <SecretInput
        v-model="form.amap_js_security_code"
        label="JS 安全密钥"
        :configured="secretState.amap_js_security_code_configured"
        :masked="secretState.amap_js_security_code_masked"
        placeholder="JS API 安全密钥…"
      />
      <label class="field" style="flex-direction: row; align-items: center; gap: 8px; margin-top: 10px">
        <input v-model="form.amap_enabled" name="amap_enabled" type="checkbox" style="width: auto" />
        <span>启用高德地图</span>
      </label>
    </div>

    <div class="toolbar" style="margin: var(--gap-lg) 0 0">
      <button class="primary" type="submit" :disabled="saving || loading">{{ saving ? '保存中…' : '保存设置' }}</button>
      <span class="muted" v-if="updatedAt">最后修改：{{ updatedBy || '平台' }} · {{ formatDateTime(updatedAt) }}</span>
    </div>
  </form>
</template>
