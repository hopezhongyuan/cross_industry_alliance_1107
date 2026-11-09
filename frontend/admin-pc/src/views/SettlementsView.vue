<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, ApiError, type Page, type SettlementRow } from '../api'
import PageHeader from '../components/PageHeader.vue'
import PaginationBar from '../components/PaginationBar.vue'
import StatusTag from '../components/StatusTag.vue'
import { formatDateTime, formatMoney } from '../format'

const route = useRoute()
const router = useRouter()
const rows = ref<SettlementRow[]>([])
const page = ref<Page>({ page: 1, page_size: 20, total: 0, has_more: false })
const status = ref(String(route.query.status ?? ''))
const loading = ref(false)
const error = ref('')
const publishing = ref<number | null>(null)

async function load(target = 1, size = page.value.page_size) {
  loading.value = true
  error.value = ''
  router.replace({
    query: {
      ...(status.value ? { status: status.value } : {}),
      ...(target > 1 ? { page: String(target) } : {}),
    },
  })
  try {
    const result = await api.settlements({ status: status.value, page: target, page_size: size })
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

onMounted(() => load(Number(route.query.page ?? 1)))
</script>

<template>
  <PageHeader title="结算批次" description="按周期发布结算批次；发布后结算项转为可提现。" />
  <div class="toolbar">
    <label class="field">
      <span>状态</span>
      <select v-model="status" @change="load(1)">
        <option value="">全部</option>
        <option value="PENDING">待发布</option>
        <option value="PUBLISHED">已发布</option>
        <option value="CLOSED">已关闭</option>
      </select>
    </label>
    <button class="primary" :disabled="loading" @click="load(1)">查询</button>
  </div>
  <div v-if="error" class="error" role="alert">{{ error }}</div>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>批次号</th>
          <th>周期</th>
          <th>状态</th>
          <th class="money">结算总额</th>
          <th class="money">佣金</th>
          <th class="money">应打款</th>
          <th class="money">结算项</th>
          <th>发布时间</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.id">
          <td>{{ row.batch_no }}</td>
          <td>{{ row.period_start }} ~ {{ row.period_end }}</td>
          <td><StatusTag :status="row.status" /></td>
          <td class="money">{{ formatMoney(row.total_amount) }}</td>
          <td class="money">{{ formatMoney(row.commission_amount) }}</td>
          <td class="money">{{ formatMoney(row.net_amount) }}</td>
          <td class="money">{{ row.items_count }}</td>
          <td>{{ formatDateTime(row.published_at) }}</td>
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
  <PaginationBar
    :page="page.page"
    :page-size="page.page_size"
    :total="page.total"
    @change="(payload) => load(payload.page, payload.pageSize)"
  />
</template>
