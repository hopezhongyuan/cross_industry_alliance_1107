import Taro from '@tarojs/taro'

export type LinkTarget = { type?: string; value?: string }

const FUNCTION_PATH: Record<string, string> = {
  HOME: '/pages/index/index',
  CATEGORY: '/pages/category/index',
  CART: '/pages/cart/index',
  ORDERS: '/pages/orders/index',
  ME: '/pages/me/index',
  SEARCH: '/pages/category/index',
  MERCHANT_LIST: '/pages/merchants/index',
}

export function linkPath(link?: LinkTarget): string {
  if (!link?.type) return ''
  if (link.type === 'FUNCTION') return FUNCTION_PATH[link.value || ''] || ''
  if (link.type === 'MICRO_PAGE') return `/pages/micro/index?slug=${encodeURIComponent(link.value || '')}`
  if (link.type === 'CATEGORY') return `/pages/category/index${link.value ? `?category=${link.value}` : ''}`
  if (link.type === 'MERCHANT') return `/pages/store/index?id=${link.value}`
  if (link.type === 'PRODUCT') return `/pages/product/index?id=${link.value}`
  return ''
}

export function navigateLink(link?: LinkTarget, mode: 'push' | 'tab' = 'push') {
  if (!link?.type) return
  const path = linkPath(link)
  if (!path) return
  if (mode === 'tab' && (link.type === 'FUNCTION' || link.type === 'MICRO_PAGE')) {
    Taro.reLaunch({ url: path })
  } else {
    Taro.navigateTo({ url: path })
  }
}
