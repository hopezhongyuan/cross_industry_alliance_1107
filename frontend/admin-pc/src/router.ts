import { createRouter, createWebHistory } from 'vue-router'
import { getToken } from './api'

const routes = [
  { path: '/login', component: () => import('./views/LoginView.vue'), meta: { public: true } },
  { path: '/', component: () => import('./views/DashboardView.vue'), meta: { group: '概览', title: '运营概览' } },
  {
    path: '/products',
    component: () => import('./views/AdminProductsView.vue'),
    meta: { group: '商品', title: '商品管理' },
  },
  {
    path: '/products/:id',
    component: () => import('./views/ProductDetailView.vue'),
    meta: { group: '商品', title: '商品详情' },
  },
  {
    path: '/product-templates',
    component: () => import('./views/TemplatesView.vue'),
    meta: { group: '商品', title: '商品模板' },
  },
  {
    path: '/categories',
    component: () => import('./views/CategoriesView.vue'),
    meta: { group: '商品', title: '商品类目' },
  },
  { path: '/media', component: () => import('./views/MediaLibraryView.vue'), meta: { group: '商品', title: '素材库' } },
  {
    path: '/orders',
    component: () => import('./views/OrdersView.vue'),
    meta: { group: '订单', title: '订单监控' },
  },
  {
    path: '/arbitrations',
    component: () => import('./views/ArbitrationsView.vue'),
    meta: { group: '订单', title: '售后仲裁' },
  },
  {
    path: '/merchants',
    component: () => import('./views/MerchantsView.vue'),
    meta: { group: '店铺', title: '商户管理' },
  },
  {
    path: '/merchants/new',
    component: () => import('./views/MerchantNewView.vue'),
    meta: { group: '店铺', title: '新建商户' },
  },
  {
    path: '/merchants/:id',
    component: () => import('./views/MerchantDetailView.vue'),
    meta: { group: '店铺', title: '商户详情' },
  },
  {
    path: '/storefront',
    component: () => import('./views/StorefrontView.vue'),
    meta: { group: '店铺', title: '店铺装修' },
  },
  {
    path: '/storefront/pages/:id',
    component: () => import('./views/DecoPageEditorView.vue'),
    meta: { group: '店铺', title: '微页面编辑' },
  },
  { path: '/users', component: () => import('./views/UsersView.vue'), meta: { group: '用户', title: '用户列表' } },
  { path: '/points/users', component: () => import('./views/PointsManagementView.vue'), meta: { group: '用户', title: '积分管理' } },
  { path: '/coupons', component: () => import('./views/PlatformCouponsView.vue'), meta: { group: '营销', title: '平台优惠券' } },
  { path: '/audits', component: () => import('./views/AuditsView.vue'), meta: { group: '审核', title: '审核中心' } },
  {
    path: '/settlements',
    component: () => import('./views/SettlementsView.vue'),
    meta: { group: '财务', title: '结算批次' },
  },
  {
    path: '/withdrawals',
    component: () => import('./views/WithdrawalsView.vue'),
    meta: { group: '财务', title: '提现打款' },
  },
  {
    path: '/reconciliation',
    component: () => import('./views/ReconciliationView.vue'),
    meta: { group: '财务', title: '资金对账' },
  },
  {
    path: '/settings',
    component: () => import('./views/PlatformSettingsView.vue'),
    meta: { group: '设置', title: '平台设置' },
  },
  {
    path: '/payment-config',
    component: () => import('./views/PaymentConfigView.vue'),
    meta: { group: '设置', title: '支付配置' },
  },
  { path: '/rules', component: () => import('./views/RuleConfigView.vue'), meta: { group: '设置', title: '交易规则' } },
  { path: '/logs', component: () => import('./views/LogsView.vue'), meta: { group: '设置', title: '操作日志' } },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to) => {
  if (!to.meta.public && !getToken()) return '/login'
  if (to.path === '/login' && getToken()) return '/'
  return true
})

router.afterEach((to) => {
  const title = (to.meta.title as string) || ''
  document.title = title ? `${title} · 异业联盟平台后台` : '异业联盟平台后台'
})

export default router
