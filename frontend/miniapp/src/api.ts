import Taro from '@tarojs/taro'
import type { components } from '../../shared/schema'

export type Schemas = components['schemas']
export type Paged<T> = { items: T[]; page: { page: number; page_size: number; total: number; has_more: boolean } }

const ENV_API_BASE =
  typeof process !== 'undefined' && process.env ? process.env.TARO_APP_API_BASE : undefined
const BASE_URL = ENV_API_BASE || '/api/v1'
const TOKEN_KEY = 'alliance_token'

export class ApiError extends Error {
  code: string
  status: number

  constructor(code: string, message: string, status: number) {
    super(message)
    this.code = code
    this.status = status
  }
}

export function getToken(): string {
  return (Taro.getStorageSync(TOKEN_KEY) as string) || ''
}

export function setToken(token: string) {
  Taro.setStorageSync(TOKEN_KEY, token)
}

export function clearToken() {
  Taro.removeStorageSync(TOKEN_KEY)
}

function idempotencyKey(): string {
  return `mp${Date.now()}${Math.floor(Math.random() * 100000)}`
}

async function request<T>(path: string, options: { method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'; data?: unknown; headers?: Record<string, string> } = {}): Promise<T> {
  const token = getToken()
  const response = await Taro.request({
    url: `${BASE_URL}${path}`,
    method: options.method ?? 'GET',
    data: options.data,
    header: {
      Accept: 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers ?? {}),
    },
  })
  const payload = response.data as Record<string, unknown> | null
  if (response.statusCode >= 400) {
    const body = (payload ?? {}) as { code?: string; message?: string; detail?: string }
    throw new ApiError(body.code ?? `HTTP_${response.statusCode}`, body.message ?? body.detail ?? '请求失败', response.statusCode)
  }
  if (payload && typeof payload === 'object' && 'code' in payload && 'data' in payload) {
    return (payload as { data: T }).data
  }
  return payload as T
}

function normalizeList<T>(payload: unknown): T[] {
  if (!payload) return []
  const body = payload as { items?: T[]; results?: T[] }
  return body.items ?? body.results ?? []
}

export type ProductRow = {
  id: number
  title: string
  subtitle?: string
  cover_url?: string
  price: number
  merchant?: { id: number; name: string }
  type?: string
}

export type CartData = {
  merchant_id: number | null
  items: Array<{
    id: number
    product_id: number
    sku_id: number | null
    title: string
    cover_url: string
    price_amount: number
    quantity: number
    selected: boolean
  }>
  total_amount: number
}

export type OrderRow = {
  id: number
  order_no: string
  status: string
  order_type: string
  merchant_id: number
  merchant_name?: string
  payable_amount: number
  paid_amount: number
  refunded_amount: number
  created_at: string
  completed_at: string | null
  items?: Array<{ id: number; title: string; price: number; quantity: number; amount: number }>
  verify_codes?: Array<{ code: string; status: string }>
}

export const api = {
  async sendSms(phone: string) {
    return request<{ expires_in: number; debug_code?: string }>('/auth/sms/send/', {
      method: 'POST',
      data: { phone, scene: 'LOGIN' },
    })
  },

  async loginSms(phone: string, smsCode: string) {
    const token = await request<{ access: string; refresh: string }>('/auth/h5/sms/', {
      method: 'POST',
      data: { phone, sms_code: smsCode },
    })
    setToken(token.access)
    return token
  },

  me() {
    return request<{ id: number; phone: string; nickname: string }>('/accounts/me/')
  },

  async products(keyword = '') {
    const payload = await request<unknown>(`/products/${keyword ? `?search=${encodeURIComponent(keyword)}` : ''}`)
    return normalizeList<ProductRow>(payload)
  },

  product(id: number) {
    return request<ProductRow & { detail?: string; skus?: Array<{ id: number; price: number; stock: number }> }>(`/products/${id}/`)
  },

  cart() {
    return request<CartData>('/cart/')
  },

  addCart(productId: number, skuId: number | null, quantity = 1) {
    return request<CartData>('/cart/items/', {
      method: 'POST',
      data: { product_id: productId, sku_id: skuId, quantity },
    })
  },

  updateCart(itemId: number, data: { quantity?: number; selected?: boolean }) {
    return request<CartData>(`/cart/items/${itemId}/`, { method: 'PATCH', data })
  },

  removeCart(itemId: number) {
    return request<void>(`/cart/items/${itemId}/`, { method: 'DELETE' })
  },

  createOrder(payload: {
    merchant_id: number
    order_type: string
    items: Array<{ product_id: number; sku_id: number | null; quantity: number }>
    contact: { name: string; phone: string; address_detail: string }
    remark?: string
  }) {
    return request<OrderRow>('/orders/', {
      method: 'POST',
      data: payload,
      headers: { 'Idempotency-Key': idempotencyKey() },
    })
  },

  async pay(orderId: number, channel = 'WECHAT_MINI') {
    return request<{ payment_no: string; prepay_id: string; pay_params: Record<string, unknown> }>(`/orders/${orderId}/pay/`, {
      method: 'POST',
      data: { channel },
      headers: { 'Idempotency-Key': idempotencyKey() },
    })
  },

  async mockPay(orderId: number) {
    const payment = await api.pay(orderId)
    const order = await api.order(orderId)
    await Taro.request({
      url: `${BASE_URL}/callback/wechat/pay/`,
      method: 'POST',
      data: {
        payment_no: payment.payment_no,
        transaction_id: `mp-${Date.now()}`,
        amount: order.payable_amount,
        trade_state: 'SUCCESS',
      },
    })
    return order
  },

  async orders(status = '') {
    const payload = await request<unknown>(`/orders/${status ? `?status=${status}` : ''}`)
    return normalizeList<OrderRow>(payload)
  },

  order(id: number) {
    return request<OrderRow>(`/orders/${id}/`)
  },

  confirmOrder(id: number) {
    return request<OrderRow>(`/orders/${id}/confirm/`, { method: 'POST', data: {} })
  },

  cancelOrder(id: number) {
    return request<OrderRow>(`/orders/${id}/cancel/`, { method: 'POST', data: { reason: '用户取消' } })
  },

  applyAfterSale(payload: { order_id: number; type: string; reason_code: string; request_amount: number; description?: string }) {
    return request<unknown>('/after-sales/', { method: 'POST', data: payload })
  },

  async merchantOrders(status = '') {
    const payload = await request<unknown>(`/merchant/orders/${status ? `?status=${status}` : ''}`)
    return normalizeList<OrderRow>(payload)
  },

  acceptOrder(id: number) {
    return request<OrderRow>(`/merchant/orders/${id}/accept/`, { method: 'POST', data: {} })
  },

  rejectOrder(id: number, reason: string) {
    return request<OrderRow>(`/merchant/orders/${id}/reject/`, { method: 'POST', data: { reason } })
  },

  shipOrder(id: number, logisticsCompany = '', logisticsNo = '') {
    return request<OrderRow>(`/merchant/orders/${id}/ship/`, {
      method: 'POST',
      data: { logistics_company: logisticsCompany, logistics_no: logisticsNo },
    })
  },

  verifyCode(code: string) {
    return request<{ order_id: number; order_no: string; order_status: string }>('/merchant/verify/', {
      method: 'POST',
      data: { code },
    })
  },

  async statements(status = '') {
    const result = await request<Paged<Schemas['StatementItem']>>(`/merchant/statements/${status ? `?status=${status}` : ''}`)
    return result
  },

  account() {
    return request<{ merchant_id: number; pending_balance: number; frozen_balance: number; available_balance: number; withdrawing_balance: number }>(
      '/merchant/account/',
    )
  },

  withdraw(amount: number) {
    return request<unknown>('/merchant/withdrawals/', {
      method: 'POST',
      data: { amount },
      headers: { 'Idempotency-Key': idempotencyKey() },
    })
  },
}
