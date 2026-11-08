<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, ApiError } from '../api'

const counts = ref({ orders: 0, settlements: 0, withdrawals: 0, arbitrations: 0, logs: 0 })
const loading = ref(true)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [orders, settlements, withdrawals, arbitrations, logs] = await Promise.all([
      api.adminOrders({ page_size: 1 }),
      api.settlements({ page_size: 1 }),
      api.withdrawals({ page_size: 1 }),
      api.arbitrations({ page_size: 1 }),
      api.logs({ page_size: 1 }),
    ])
    counts.value = {
      orders: orders.page.total,
      settlements: settlements.page.total,
      withdrawals: withdrawals.page.total,
      arbitrations: arbitrations.page.total,
      logs: logs.page.total,
    }
  } catch (exc) {
    error.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <h1>运营概览</h1>
  <div v-if="error" class="error">{{ error }}</div>
  <div class="cards">
    <div class="card metric"><span>订单总数</span><strong>{{ counts.orders }}</strong></div>
    <div class="card metric"><span>结算批次</span><strong>{{ counts.settlements }}</strong></div>
    <div class="card metric"><span>提现单</span><strong>{{ counts.withdrawals }}</strong></div>
    <div class="card metric"><span>仲裁案件</span><strong>{{ counts.arbitrations }}</strong></div>
    <div class="card metric"><span>操作日志</span><strong>{{ counts.logs }}</strong></div>
  </div>
  <div v-if="loading" class="empty">加载中…</div>
</template>

<style scoped>
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 16px;
}

.metric {
  display: flex;
  flex-direction: column;
  gap: 10px;
  color: var(--ink-2);
  font-size: 13px;
}

.metric strong {
  font-size: 28px;
  color: var(--ink);
}
</style>
