<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { clearToken } from './api'

const route = useRoute()
const router = useRouter()

const nav = [
  { path: '/', label: '概览' },
  { path: '/orders', label: '订单' },
  { path: '/arbitrations', label: '仲裁' },
  { path: '/settlements', label: '结算' },
  { path: '/withdrawals', label: '提现' },
  { path: '/payment-config', label: '支付配置' },
  { path: '/reconciliation', label: '对账' },
  { path: '/logs', label: '操作日志' },
]

const isLogin = computed(() => route.path === '/login')

function logout() {
  clearToken()
  router.push('/login')
}
</script>

<template>
  <div v-if="isLogin" class="login-shell">
    <router-view />
  </div>
  <div v-else class="shell">
    <aside class="sidebar">
      <div class="brand">
        <strong>异业联盟</strong>
        <span>平台后台</span>
      </div>
      <nav>
        <router-link v-for="item in nav" :key="item.path" :to="item.path">{{ item.label }}</router-link>
      </nav>
      <button class="ghost" @click="logout">退出登录</button>
    </aside>
    <main class="content">
      <router-view />
    </main>
  </div>
</template>
