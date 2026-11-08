<script setup lang="ts">
import { ref } from 'vue'
import { api, ApiError } from '../api'

const form = ref({
  afterSaleHours: 48,
  arbitrationSlaHours: 72,
  settlementCycleDays: 7,
  verifyDays: 30,
  refundPolicy: '未核销、有效期内可退；已核销按售后规则处理',
})
const remark = ref('')
const saving = ref(false)
const error = ref('')
const message = ref('')

async function submit() {
  saving.value = true
  error.value = ''
  message.value = ''
  try {
    await api.publishRule(
      {
        after_sale_deadline_hours: form.value.afterSaleHours,
        arbitration_sla_hours: form.value.arbitrationSlaHours,
        settlement_cycle_days: form.value.settlementCycleDays,
        verify_days_default: form.value.verifyDays,
        refund_policy_text: form.value.refundPolicy,
      },
      remark.value,
    )
    message.value = '规则版本已发布，新版本立即生效'
  } catch (exc) {
    error.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '发布失败'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <h1>规则配置</h1>
  <div v-if="error" class="error" role="alert">{{ error }}</div>
  <div v-if="message" class="tag ok" style="display: inline-block; margin-bottom: 12px">{{ message }}</div>
  <div class="card" style="max-width: 640px; display: flex; flex-direction: column; gap: 14px">
    <div class="grid">
      <label class="field"><span>售后商户处理时限（小时）</span><input v-model.number="form.afterSaleHours" type="number" min="1" /></label>
      <label class="field"><span>仲裁裁定 SLA（小时）</span><input v-model.number="form.arbitrationSlaHours" type="number" min="1" /></label>
      <label class="field"><span>默认结算周期（天）</span><input v-model.number="form.settlementCycleDays" type="number" min="0" /></label>
      <label class="field"><span>默认核销有效期（天）</span><input v-model.number="form.verifyDays" type="number" min="1" /></label>
    </div>
    <label class="field"><span>退款规则展示文案</span><textarea v-model="form.refundPolicy" rows="3" /></label>
    <label class="field"><span>版本说明</span><input v-model="remark" name="remark" autocomplete="off" placeholder="如：调整售后处理时限…" /></label>
    <div class="toolbar" style="margin: 0">
      <button class="primary" :disabled="saving" @click="submit">{{ saving ? '发布中…' : '发布规则版本' }}</button>
    </div>
    <div class="muted">发布后旧版本自动置为 RETIRED；规则快照用于新订单与售后。</div>
  </div>
</template>

<style scoped>
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 12px;
}
textarea {
  width: 100%;
}
</style>
