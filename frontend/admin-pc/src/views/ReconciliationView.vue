<script setup lang="ts">
import { ref } from 'vue'
import { api, ApiError, type Reconciliation } from '../api'

const date = ref(new Date().toISOString().slice(0, 10))
const report = ref<Reconciliation | null>(null)
const loading = ref(false)
const error = ref('')

async function run() {
  loading.value = true
  error.value = ''
  report.value = null
  try {
    report.value = await api.reconciliation(date.value)
  } catch (exc) {
    error.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '对账失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <h1>对账</h1>
  <div class="toolbar">
    <label class="field"><span>日期</span><input v-model="date" type="date" /></label>
    <button class="primary" :disabled="loading || !date" @click="run">执行对账</button>
  </div>
  <div v-if="error" class="error">{{ error }}</div>
  <div v-if="report" class="card" style="padding: 0; max-width: 760px">
    <div style="padding: 16px 20px; border-bottom: 1px solid var(--line)">
      对账日期 {{ report.date }} · 未解决项
      <span class="tag" :class="{ ok: report.unresolved_count === 0, danger: report.unresolved_count > 0 }">
        {{ report.unresolved_count }}
      </span>
    </div>
    <table>
      <thead>
        <tr><th>检查项</th><th>结果</th><th>差异数量</th><th>差异金额</th></tr>
      </thead>
      <tbody>
        <tr v-for="check in report.checks" :key="check.name">
          <td>{{ check.name }}</td>
          <td><span class="tag" :class="{ ok: check.status === 'OK', danger: check.status === 'DIFF' }">{{ check.status }}</span></td>
          <td>{{ check.diff_count }}</td>
          <td>{{ (check.diff_amount / 100).toFixed(2) }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
