<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, ApiError, type Page, type SettlementRow } from '../api'

const rows = ref<SettlementRow[]>([])
const page = ref<Page>({ page: 1, page_size: 20, total: 0, has_more: false })
const status = ref('')
const loading = ref(false)
const error = ref('')
const publishing = ref<number | null>(null)

async function load(target = 1) {
  loading.value = true
  error.value = ''
  try {
    const result = await api.settlements({ status: status.value, page: target, page_size: 20 })
    rows.value = result.items
    page.value = result.page
  } catch (exc) {
    error.value = exc instanceof ApiError ? exc.message : '加载失败'
  } finally {
    loading.value = false
  }
}

async function publish(row: SettlementRow) {
  if (!confirm(`发布批次 ${row.batch_no}？发布后结算项转可提现。`)) return
  publishing.value = row.id
  error.value = ''
  try {
    await api.publishSettlement(row.id)
    await load(page.value.page)
  } catch (exc) {
    error.value = exc instanceof ApiError ? `${exc.code}：${exc.message}` : '发布失败'
  } finally {
    publishing.value = null
  }
}

onMounted(() => load())
</script>

<template>
  <h1>结算批次</h1>
  <div class="toolbar">
    <label class="field">
      <span>状态</span>
      <select v-model="status">
        <option value="">全部</option>
        <option v-for="value in ['PENDING', 'PUBLISHED', 'CLOSED']" :key="value" :value="value">{{ value }}</option>
      </select>
    </label>
    <button class="primary" :disabled="loading" @click="load()">查询</button>
  </div>
  <div v-if="error" class="error">{{ error }}</div>
  <div class="card" style="padding: 0">
    <table>
      <thead>
        <tr>
          <th>批次号</th>
          <th>周期</th>
          <th>状态</th>
          <th>结算总额</th>
          <th>佣金</th>
          <th>应打款</th>
          <th>结算项</th>
          <th>发布时间</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.id">
          <td>{{ row.batch_no }}</td>
          <td>{{ row.period_start }} ~ {{ row.period_end }}</td>
          <td><span class="tag" :class="{ ok: row.status === 'PUBLISHED' }">{{ row.status }}</span></td>
          <td>{{ (row.total_amount / 100).toFixed(2) }}</td>
          <td>{{ (row.commission_amount / 100).toFixed(2) }}</td>
          <td>{{ (row.net_amount / 100).toFixed(2) }}</td>
          <td>{{ row.items_count }}</td>
          <td>{{ row.published_at ?? '-' }}</td>
          <td>
            <button class="text" :disabled="row.status !== 'PENDING' || publishing === row.id" @click="publish(row)">
              {{ publishing === row.id ? '发布中…' : '发布' }}
            </button>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-if="!rows.length" class="empty">{{ loading ? '加载中…' : '暂无结算批次' }}</div>
  </div>
  <div class="pager">
    <button class="text" :disabled="page.page <= 1" @click="load(page.page - 1)">上一页</button>
    <span>第 {{ page.page }} 页 · 共 {{ page.total }} 条</span>
    <button class="text" :disabled="!page.has_more" @click="load(page.page + 1)">下一页</button>
  </div>
</template>
