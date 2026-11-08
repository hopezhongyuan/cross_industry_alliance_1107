<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, ApiError, type LogRow, type Page } from '../api'

const rows = ref<LogRow[]>([])
const page = ref<Page>({ page: 1, page_size: 20, total: 0, has_more: false })
const bizType = ref('')
const operator = ref('')
const bizId = ref<number | ''>('')
const loading = ref(false)
const error = ref('')

async function load(target = 1) {
  loading.value = true
  error.value = ''
  try {
    const result = await api.logs({
      biz_type: bizType.value,
      operator: operator.value,
      biz_id: bizId.value === '' ? undefined : Number(bizId.value),
      page: target,
      page_size: 20,
    })
    rows.value = result.items
    page.value = result.page
  } catch (exc) {
    error.value = exc instanceof ApiError ? exc.message : '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => load())
</script>

<template>
  <h1>操作日志</h1>
  <div class="toolbar">
    <label class="field"><span>业务类型</span><input v-model="bizType" placeholder="如 SETTLEMENT_BATCH" /></label>
    <label class="field"><span>操作人</span><input v-model="operator" placeholder="姓名或手机号" /></label>
    <label class="field"><span>对象 ID</span><input v-model="bizId" type="number" /></label>
    <button class="primary" :disabled="loading" @click="load()">查询</button>
  </div>
  <div v-if="error" class="error">{{ error }}</div>
  <div class="card" style="padding: 0">
    <table>
      <thead>
        <tr><th>时间</th><th>操作人</th><th>动作</th><th>业务类型</th><th>对象</th><th>说明</th></tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.id">
          <td>{{ row.created_at }}</td>
          <td>{{ row.operator_name || '-' }}</td>
          <td>{{ row.action }}</td>
          <td>{{ row.biz_type || '-' }}</td>
          <td>{{ row.biz_id ?? '-' }}</td>
          <td>{{ row.reason || '-' }}</td>
        </tr>
      </tbody>
    </table>
    <div v-if="!rows.length" class="empty">{{ loading ? '加载中…' : '暂无日志' }}</div>
  </div>
  <div class="pager">
    <button class="text" :disabled="page.page <= 1" @click="load(page.page - 1)">上一页</button>
    <span>第 {{ page.page }} 页 · 共 {{ page.total }} 条</span>
    <button class="text" :disabled="!page.has_more" @click="load(page.page + 1)">下一页</button>
  </div>
</template>
