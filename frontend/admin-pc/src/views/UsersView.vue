<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, ApiError, type AdminUserRow, type Page } from '../api'
import PageHeader from '../components/PageHeader.vue'
import PaginationBar from '../components/PaginationBar.vue'
import StatusTag from '../components/StatusTag.vue'
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

async function load(target = 1, size = page.value.page_size) {
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
      page_size: size,
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
  <PageHeader title="用户列表" description="只读身份视图；手机号已脱敏，敏感字段不在此展示。" />
  <div class="toolbar">
    <label class="field">
      <span>关键词</span>
      <input v-model="keyword" name="q" autocomplete="off" placeholder="昵称或手机号…" @keyup.enter="load(1)" />
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
    <button class="primary" :disabled="loading" @click="load(1)">查询</button>
    <button class="outline" @click="keyword = ''; status = ''; userType = ''; load(1)">重置</button>
  </div>
  <div v-if="error" class="error" role="alert">{{ error }}</div>

  <div class="table-wrap">
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
            <span class="tag info">{{ USER_TYPE_LABEL[row.user_type] ?? row.user_type }}</span>
            <span v-if="row.merchant_names.length" class="muted"> · {{ row.merchant_names.join('、') }}</span>
          </td>
          <td><StatusTag :status="row.status === 'ACTIVE' ? 'ACTIVE' : 'DISABLED'" :label="row.status === 'ACTIVE' ? '正常' : '禁用'" /></td>
          <td>{{ formatDateTime(row.created_at) }}</td>
          <td>{{ row.last_login ? formatDateTime(row.last_login) : '-' }}</td>
        </tr>
      </tbody>
    </table>
    <div v-if="!rows.length" class="empty">{{ loading ? '加载中…' : '暂无用户' }}</div>
  </div>

  <PaginationBar
    :page="page.page"
    :page-size="page.page_size"
    :total="page.total"
    @change="(payload) => load(payload.page, payload.pageSize)"
  />
</template>
