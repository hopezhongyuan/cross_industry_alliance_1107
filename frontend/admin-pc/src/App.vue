<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, clearToken } from './api'

const route = useRoute()
const router = useRouter()

type Menu = { path: string; label: string; badge?: number }
type Group = { name: string; items: Menu[] }

const badges = ref({ audits: 0, products: 0, settlements: 0, withdrawals: 0, arbitrations: 0 })

const groups = computed<Group[]>(() => [
  { name: '概览', items: [{ path: '/', label: '运营概览' }] },
  {
    name: '商品',
    items: [
      { path: '/products', label: '商品管理', badge: badges.value.products },
      { path: '/product-templates', label: '商品模板' },
      { path: '/categories', label: '商品类目' },
      { path: '/media', label: '素材库' },
    ],
  },
  {
    name: '订单',
    items: [
      { path: '/orders', label: '订单监控' },
      { path: '/arbitrations', label: '售后仲裁', badge: badges.value.arbitrations },
    ],
  },
  {
    name: '店铺',
    items: [
      { path: '/merchants', label: '商户管理' },
      { path: '/storefront', label: '店铺装修' },
    ],
  },
  { name: '用户', items: [
    { path: '/users', label: '用户列表' },
    { path: '/points/users', label: '积分管理' },
  ] },
  { name: '营销', items: [
    { path: '/coupons', label: '平台优惠券' },
  ] },
  { name: '审核', items: [{ path: '/audits', label: '审核中心', badge: badges.value.audits }] },
  {
    name: '财务',
    items: [
      { path: '/settlements', label: '结算批次', badge: badges.value.settlements },
      { path: '/withdrawals', label: '提现打款', badge: badges.value.withdrawals },
      { path: '/reconciliation', label: '资金对账' },
    ],
  },
  {
    name: '设置',
    items: [
      { path: '/settings', label: '平台设置' },
      { path: '/payment-config', label: '支付配置' },
      { path: '/rules', label: '交易规则' },
      { path: '/logs', label: '操作日志' },
    ],
  },
])

const collapsed = ref<Record<string, boolean>>({})

const currentGroup = computed(() => {
  const path = route.path
  if (path === '/') return '概览'
  if (path.startsWith('/products') || path.startsWith('/product-templates') || path.startsWith('/categories') || path.startsWith('/media')) return '商品'
  if (path.startsWith('/orders') || path.startsWith('/arbitrations')) return '订单'
  if (path.startsWith('/merchants') || path.startsWith('/storefront')) return '店铺'
  if (path.startsWith('/users') || path.startsWith('/points')) return '用户'
  if (path.startsWith('/coupons')) return '营销'
  if (path.startsWith('/audits')) return '审核'
  if (path.startsWith('/settlements') || path.startsWith('/withdrawals') || path.startsWith('/reconciliation')) return '财务'
  return '设置'
})

const isLogin = computed(() => route.path === '/login')

function toggleGroup(name: string) {
  if (name === currentGroup.value) return
  collapsed.value = { ...collapsed.value, [name]: !collapsed.value[name] }
}

function badgeText(count: number | undefined) {
  if (!count) return ''
  return count > 99 ? '99+' : String(count)
}

function logout() {
  clearToken()
  router.push('/login')
}

async function loadBadges() {
  try {
    const [audits, products, settlements, withdrawals, arbitrations] = await Promise.all([
      api.audits({ status: 'PENDING', page_size: 1 }),
      api.adminProducts({ status: 'PENDING_AUDIT', page_size: 1 }),
      api.settlements({ status: 'PENDING', page_size: 1 }),
      api.withdrawals({ status: 'REQUESTED', page_size: 1 }),
      api.arbitrations({ status: 'PENDING', page_size: 1 }),
    ])
    badges.value = {
      audits: Object.values(audits.summary ?? {}).reduce((sum, value) => sum + Number(value || 0), 0),
      products: products.page.total,
      settlements: settlements.page.total,
      withdrawals: withdrawals.page.total,
      arbitrations: arbitrations.page.total,
    }
  } catch {
    // 角标失败不阻断导航
  }
}

onMounted(loadBadges)
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
        <span>平台后台 v1</span>
      </div>
      <nav v-for="group in groups" :key="group.name" class="nav-group" :class="{ collapsed: collapsed[group.name] && group.name !== currentGroup }">
        <button class="nav-group-title" type="button" @click="toggleGroup(group.name)">
          {{ group.name }}
          <span class="chev">▾</span>
        </button>
        <router-link v-for="item in group.items" :key="item.path" class="nav-link" :to="item.path">
          <span>{{ item.label }}</span>
          <span v-if="badgeText(item.badge)" class="nav-badge">{{ badgeText(item.badge) }}</span>
        </router-link>
      </nav>
      <button class="ghost" @click="logout">退出登录</button>
    </aside>
    <main id="main-content" class="content" tabindex="-1">
      <div class="topbar">
        <div class="breadcrumb">
          <router-link to="/">平台后台</router-link>
          <span class="sep">/</span>
          <span>{{ currentGroup }}</span>
          <span class="sep">/</span>
          <span>{{ route.meta.title }}</span>
        </div>
      </div>
      <router-view />
    </main>
  </div>
</template>
