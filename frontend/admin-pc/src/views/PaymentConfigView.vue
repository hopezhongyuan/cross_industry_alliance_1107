<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, ApiError, type PaymentConfig } from '../api'

const channel = ref('WECHAT_MINI')
const current = ref<PaymentConfig | null>(null)
const message = ref('')
const error = ref('')
const loading = ref(false)
const saving = ref(false)
const form = ref({
  merchant_no: '',
  app_id: '',
  cert_serial_no: '',
  notify_url: '',
  enabled: false,
  api_v3_key: '',
  private_key: '',
  platform_cert: '',
})

async function load() {
  loading.value = true
  error.value = ''
  message.value = ''
  current.value = null
  try {
    const config = await api.paymentConfig(channel.value)
    current.value = config
    form.value = {
      merchant_no: config.merchant_no,
      app_id: config.app_id,
      cert_serial_no: config.cert_serial_no,
      notify_url: config.notify_url,
      enabled: config.enabled,
      api_v3_key: '',
      private_key: '',
      platform_cert: '',
    }
  } catch (exc) {
    if (exc instanceof ApiError && exc.code === 'NOT_FOUND') {
      message.value = '该渠道尚未配置，请填写后保存'
      form.value.enabled = false
    } else {
      error.value = exc instanceof ApiError ? exc.message : '加载失败'
    }
  } finally {
    loading.value = false
  }
}

async function save() {
  error.value = ''
  message.value = ''
  if (!form.value.merchant_no || !form.value.api_v3_key || !form.value.private_key || !form.value.platform_cert) {
    error.value = '请填写商户号、APIv3 密钥、商户私钥与平台证书'
    return
  }
  saving.value = true
  try {
    await api.savePaymentConfig(channel.value, { ...form.value })
    await load()
    message.value = '已保存，密钥与证书已加密存储'
  } catch (exc) {
    error.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '保存失败'
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <h1>支付配置</h1>
  <div class="toolbar">
    <label class="field">
      <span>渠道</span>
      <select v-model="channel" @change="load">
        <option value="WECHAT_MINI">微信小程序</option>
        <option value="WECHAT_H5">微信 H5</option>
      </select>
    </label>
  </div>
  <div v-if="error" class="error" role="alert">{{ error }}</div>
  <div v-if="message" class="tag ok" style="display: inline-block; margin-bottom: 12px">{{ message }}</div>

  <div class="card" style="max-width: 720px; display: flex; flex-direction: column; gap: 14px">
    <div class="grid">
      <label class="field"><span>商户号</span><input v-model="form.merchant_no" name="merchant_no" autocomplete="off" placeholder="请输入商户号…" /></label>
      <label class="field"><span>AppID</span><input v-model="form.app_id" name="app_id" autocomplete="off" placeholder="请输入 AppID…" /></label>
      <label class="field"><span>证书序列号</span><input v-model="form.cert_serial_no" name="cert_serial_no" autocomplete="off" placeholder="请输入证书序列号…" /></label>
      <label class="field"><span>回调地址</span><input v-model="form.notify_url" name="notify_url" type="url" autocomplete="off" placeholder="https://…" /></label>
    </div>
    <label class="field">
      <span>APIv3 密钥（保存时必填，读取不回传）</span>
      <input v-model="form.api_v3_key" name="api_v3_key" type="password" autocomplete="off" placeholder="请输入 32 位密钥…" />
    </label>
    <label class="field">
      <span>商户私钥 PEM（保存时必填）</span>
      <textarea v-model="form.private_key" rows="4" />
    </label>
    <label class="field">
      <span>平台证书 PEM（保存时必填）</span>
      <textarea v-model="form.platform_cert" rows="4" />
    </label>
    <label class="field" style="flex-direction: row; align-items: center; gap: 8px">
      <input v-model="form.enabled" type="checkbox" style="min-width: auto" />
      <span>启用该渠道</span>
    </label>
    <div class="toolbar" style="margin: 0">
      <button class="primary" :disabled="saving" @click="save">
        {{ saving ? '保存中…' : '保存配置' }}
      </button>
    </div>
    <div v-if="current" class="muted">最后修改：{{ current.updated_by_name || '-' }} · {{ current.updated_at }}</div>
  </div>
</template>

<style scoped>
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}

.muted {
  color: var(--ink-2);
  font-size: 13px;
}

textarea {
  width: 100%;
  font-family: monospace;
}
</style>
