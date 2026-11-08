<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { api, ApiError, type AdminPlatformConfigPayload } from '../api'
import MediaPicker from '../components/MediaPicker.vue'
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
  amap_web_key_configured: false,
  amap_js_security_code_configured: false,
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
    secretState.miniapp_app_secret_configured = config.miniapp_app_secret_configured
    secretState.amap_web_key_configured = config.amap_web_key_configured
    secretState.amap_js_security_code_configured = config.amap_js_security_code_configured
    updatedBy.value = config.updated_by_name
    updatedAt.value = config.updated_at
  } catch (exc) {
    error.value = exc instanceof ApiError ? exc.message : '加载失败'
  } finally {
    loading.value = false
  }
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
    secretState.miniapp_app_secret_configured = config.miniapp_app_secret_configured
    secretState.amap_web_key_configured = config.amap_web_key_configured
    secretState.amap_js_security_code_configured = config.amap_js_security_code_configured
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
  <h1>平台设置</h1>
  <div class="muted" style="margin-bottom: 16px">
    平台名称、协议、小程序与高德参数；密钥类字段不会回显明文，留空保存表示保持原值。
  </div>
  <div v-if="error" class="error" role="alert">{{ error }}</div>
  <div v-if="message" class="muted" aria-live="polite">{{ message }}</div>

  <form class="card" @submit.prevent="save">
    <div class="section-title">基础信息</div>
    <div class="form-grid">
      <label class="field">
        <span>平台名称</span>
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
    </div>
    <div class="field">
      <span>平台 Logo</span>
      <MediaPicker v-model="form.logo_url" kind="IMAGE" />
    </div>

    <div class="section-title">协议</div>
    <div class="form-grid">
      <label class="field">
        <span>协议版本</span>
        <input v-model="form.agreement_version" name="agreement_version" autocomplete="off" placeholder="如：2026.11…" />
      </label>
    </div>
    <label class="field">
      <span>隐私协议正文</span>
      <textarea v-model="form.privacy_policy" rows="6" placeholder="请输入隐私协议正文…" />
    </label>
    <label class="field">
      <span>用户注册协议正文</span>
      <textarea v-model="form.user_agreement" rows="6" placeholder="请输入用户注册协议正文…" />
    </label>

    <div class="section-title">小程序参数</div>
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
    <label class="field">
      <span>AppSecret {{ secretState.miniapp_app_secret_configured ? '（已配置）' : '（未配置）' }}</span>
      <input
        v-model="form.miniapp_app_secret"
        name="miniapp_app_secret"
        type="password"
        autocomplete="new-password"
        :placeholder="secretState.miniapp_app_secret_configured ? '留空表示保持原值…' : '请输入小程序 AppSecret…'"
      />
    </label>

    <div class="section-title">高德地图</div>
    <div class="muted" style="margin-bottom: 10px">
      暂无 Key 时请保持关闭；Key 到位后填入并启用，后台地图选点与用户端地图即可生效。
    </div>
    <label class="field">
      <span>Web 服务 Key {{ secretState.amap_web_key_configured ? '（已配置）' : '（未配置）' }}</span>
      <input
        v-model="form.amap_web_key"
        name="amap_web_key"
        type="password"
        autocomplete="new-password"
        :placeholder="secretState.amap_web_key_configured ? '留空表示保持原值…' : '服务端地理编码 Key…'"
      />
    </label>
    <label class="field">
      <span>JS API Key</span>
      <input v-model="form.amap_js_key" name="amap_js_key" autocomplete="off" placeholder="Web 端（JS API）Key…" />
    </label>
    <label class="field">
      <span>JS 安全密钥 {{ secretState.amap_js_security_code_configured ? '（已配置）' : '（未配置）' }}</span>
      <input
        v-model="form.amap_js_security_code"
        name="amap_js_security_code"
        type="password"
        autocomplete="new-password"
        :placeholder="secretState.amap_js_security_code_configured ? '留空表示保持原值…' : 'JS API 安全密钥…'"
      />
    </label>
    <label class="field" style="flex-direction: row; align-items: center; gap: 8px">
      <input v-model="form.amap_enabled" name="amap_enabled" type="checkbox" style="width: auto" />
      <span>启用高德地图</span>
    </label>

    <div class="toolbar" style="margin: 0">
      <button class="primary" type="submit" :disabled="saving || loading">{{ saving ? '保存中…' : '保存设置' }}</button>
      <span class="muted" v-if="updatedAt">最后修改：{{ updatedBy || '平台' }} · {{ formatDateTime(updatedAt) }}</span>
    </div>
  </form>
</template>
