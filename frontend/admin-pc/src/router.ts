import { createRouter, createWebHistory } from 'vue-router'
import { getToken } from './api'

const routes = [
  { path: '/login', component: () => import('./views/LoginView.vue'), meta: { public: true } },
  { path: '/', component: () => import('./views/DashboardView.vue') },
  { path: '/orders', component: () => import('./views/OrdersView.vue') },
  { path: '/users', component: () => import('./views/UsersView.vue') },
  { path: '/merchants', component: () => import('./views/MerchantsView.vue') },
  { path: '/categories', component: () => import('./views/CategoriesView.vue') },
  { path: '/products', component: () => import('./views/AdminProductsView.vue') },
  { path: '/product-templates', component: () => import('./views/TemplatesView.vue') },
  { path: '/media', component: () => import('./views/MediaLibraryView.vue') },
  { path: '/storefront', component: () => import('./views/StorefrontView.vue') },
  { path: '/audits', component: () => import('./views/AuditsView.vue') },
  { path: '/arbitrations', component: () => import('./views/ArbitrationsView.vue') },
  { path: '/settlements', component: () => import('./views/SettlementsView.vue') },
  { path: '/withdrawals', component: () => import('./views/WithdrawalsView.vue') },
  { path: '/payment-config', component: () => import('./views/PaymentConfigView.vue') },
  { path: '/settings', component: () => import('./views/PlatformSettingsView.vue') },
  { path: '/rules', component: () => import('./views/RuleConfigView.vue') },
  { path: '/reconciliation', component: () => import('./views/ReconciliationView.vue') },
  { path: '/logs', component: () => import('./views/LogsView.vue') },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to) => {
  if (!to.meta.public && !getToken()) return '/login'
  if (to.path === '/login' && getToken()) return '/'
  return true
})

export default router
