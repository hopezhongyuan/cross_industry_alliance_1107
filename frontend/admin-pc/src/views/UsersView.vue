<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, ApiError, type AdminUserRow, type Page } from '../api'
import { formatDateTime } from '../format'

const route = useRoute()
const router = useRouter()
const rows = ref<AdminUserRow[]>([])
const page = ref<Page>({ page: 1, page_size: 20, total: 0, has_more: false })
const status = ref(String(route.query.status ?? ''))
const userType = ref(String(route.query.user_type ?? ''))
const keyword = ref(String(route.query.q ?? ''))
const loading = ref(false)
const error = ref('')

const USER_TYPE_LABEL: Record<string, string> = {
  CONSUMER: '消费者',
  MERCHANT_STAFF: '商户员工',
  PLATFORM_ADMIN: '平台管理员',
}

async function load(target = 1) {
  loading.value = true
  error.value = ''
  router.replace({
    query: {
      ...(status.value ? { status: status.value } : {}),
      ...(userType.value ? { user_type: userType.value } : {}),
      ...(keyword.value.trim() ? { q: keyword.value.trim() } : {}),
      ...(target > 1 ? { page: String(target) } : {}),
    },
  })
  try {
    const result = await api.adminUsers({
      status: status.value,
      user_type: userType.value,
      q: keyword.value.trim(),
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

onMounted(() => load(Number(route.query.page ?? 1)))
</script>

<template>
  <h1>用户管理</h1>
  <div class="toolbar">
    <label class="field">
      <span>关键词</span>
      <input v-model="keyword" name="q" autocomplete="off" placeholder="昵称或手机号…" @keyup.enter="load()" />
    </label>
    <label class="field">
      <span>状态</span>
      <select v-model="status">
        <option value="">全部</option>
        <option value="ACTIVE">正常</option>
        <option value="DISABLED">禁用</option>
      </select>
    </label>
    <label class="field">
      <span>身份</span>
      <select v-model="userType">
        <option value="">全部</option>
        <option value="CONSUMER">消费者</option>
        <option value="MERCHANT_STAFF">商户员工</option>
        <option value="PLATFORM_ADMIN">平台管理员</option>
      </select>
    </label>
    <button class="primary" :disabled="loading" @click="load()">查询</button>
  </div>
  <div class="muted" style="margin-bottom: 12px">只读列表；手机号已脱敏展示。</div>
  <div v-if="error" class="error" role="alert">{{ error }}</div>

  <div class="card" style="padding: 0">
    <table>
      <thead>
        <tr>
          <th>用户</th>
          <th>手机号</th>
          <th>身份</th>
          <th>状态</th>
          <th>注册时间</th>
          <th>最近登录</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.id">
          <td>
            <div class="user-cell">
              <img v-if="row.avatar_url" :src="row.avatar_url" :alt="row.nickname || '用户头像'" class="avatar" />
              <span v-else class="avatar avatar-fallback">{{ (row.nickname || '用')[0] }}</span>
              <span>{{ row.nickname || '匿名用户' }}</span>
            </div>
          </td>
          <td>{{ row.phone_masked || '-' }}</td>
          <td>
            <span class="tag">{{ USER_TYPE_LABEL[row.user_type] ?? row.user_type }}</span>
            <span v-if="row.merchant_names.length" class="muted"> · {{ row.merchant_names.join('、') }}</span>
          </td>
          <td>
            <span class="tag" :class="{ ok: row.status === 'ACTIVE', danger: row.status === 'DISABLED' }">
              {{ row.status === 'ACTIVE' ? '正常' : '禁用' }}
            </span>
          </td>
          <td>{{ formatDateTime(row.created_at) }}</td>
          <td>{{ row.last_login ? formatDateTime(row.last_login) : '-' }}</td>
        </tr>
      </tbody>
    </table>
    <div v-if="!rows.length" class="empty">{{ loading ? '加载中…' : '暂无用户' }}</div>
  </div>

  <div class="pager">
    <button class="text" :disabled="page.page <= 1" @click="load(page.page - 1)">上一页</button>
    <span>第 {{ page.page }} 页 · 共 {{ page.total }} 条</span>
    <button class="text" :disabled="!page.has_more" @click="load(page.page + 1)">下一页</button>
  </div>
</template>
