<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { clearToken } from './api'

const route = useRoute()
const router = useRouter()

const nav = [
  { path: '/', label: '概览' },
  { path: '/orders', label: '订单' },
  { path: '/users', label: '用户管理' },
  { path: '/merchants', label: '商户管理' },
  { path: '/categories', label: '商品类目' },
  { path: '/products', label: '商品管理' },
  { path: '/product-templates', label: '商品模板' },
  { path: '/media', label: '素材库' },
  { path: '/storefront', label: '店铺装修' },
  { path: '/audits', label: '审核中心' },
  { path: '/arbitrations', label: '仲裁' },
  { path: '/settlements', label: '结算' },
  { path: '/withdrawals', label: '提现' },
  { path: '/payment-config', label: '支付配置' },
  { path: '/settings', label: '平台设置' },
  { path: '/rules', label: '规则配置' },
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
    <a class="skip-link" href="#main-content">跳到主要内容</a>
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
    <main id="main-content" class="content" tabindex="-1">
      <router-view />
    </main>
  </div>
</template>
