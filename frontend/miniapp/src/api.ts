import Taro from '@tarojs/taro'
import type { components } from '../../shared/schema'

export type Schemas = components['schemas']
export type Paged<T> = { items: T[]; page: { page: number; page_size: number; total: number; has_more: boolean } }

declare const process: { env?: Record<string, string | undefined> } | undefined

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
  merchant_id?: number
  merchant?: { id: number; name: string }
  type?: string
}

export type ProductDetail = {
  id: number
  merchant_id: number
  merchant_name: string
  merchant_address: string
  merchant_phone: string
  type: 'PHYSICAL' | 'SERVICE'
  title: string
  subtitle?: string
  cover_url?: string
  images?: string[]
  description?: string
  price: number
  original_price?: number
  verify_days?: number
  appointment_required: boolean
  refund_policy?: string
  skus: Array<{ id: number; price: number; available_stock: number; sku_code: string }>
  slots: Array<{ id: number; slot_date: string; start_time: string; end_time: string; remaining: number }>
}

export type StoreRow = {
  id: number
  merchant_no: string
  name: string
  logo_url: string
  category_id: number | null
  category_name: string
  address: string
  city: string
  district: string
  distance_meters: number | null
  business_hours: Record<string, unknown>
  status: string
}

export type CategoryRow = { id: number; name: string; parent: number | null; icon_url: string; level?: number; sort?: number }

export type MerchantProductCategoryRow = {
  id: number
  name: string
  sort: number
  status: string
  product_count: number
}


export type AddressRow = {
  id: number
  receiver_name: string
  phone: string
  province: string
  city: string
  district: string
  detail: string
  tag: string
  is_default: boolean
}

export type MerchantSkuRow = {
  id: number
  sku_code: string
  spec_json: Record<string, unknown>
  price: number
  stock: number
  available_stock: number
}

export type MerchantProductRow = {
  id: number
  product_code: string
  merchant_category_id: number | null
  merchant_category_name: string
  type: string
  title: string
  subtitle: string
  cover_url: string
  price: number
  status: string
  reject_reason: string
  total_stock: number
  sold_count: number
  delivery_types: string[]
  submitted_at: string | null
  updated_at: string
  off_sale_by: string
  off_sale_reason: string
  off_sale_at: string | null
}

export type MerchantProductDetail = MerchantProductRow & {
  category_id: number | null
  category_name: string
  type_label: string
  images: string[]
  description: string
  original_price: number
  verify_days: number
  appointment_required: boolean
  skus: MerchantSkuRow[]
  audited_at: string | null
  version: number
  created_at: string
}

export type MerchantProductPayload = {
  category_id: number
  merchant_category_id?: number | null
  product_code?: string
  type: 'PHYSICAL' | 'SERVICE'
  title: string
  subtitle?: string
  cover_url?: string
  images?: string[]
  description?: string
  price_amount: number
  original_price_amount?: number
  verify_days?: number
  appointment_required?: boolean
  delivery_types: string[]
  skus: Array<{ sku_code: string; spec?: Record<string, unknown>; price_amount: number; stock: number }>
  version?: number
}

export type MerchantTemplateRow = {
  id: number
  template_no: string
  title: string
  subtitle: string
  type: string
  category_id: number
  category_name: string
  cover_url: string
  description: string
  price: number
  original_price: number
  verify_days: number
  delivery_types: string[]
  skus: Array<{ sku_code: string; spec?: Record<string, unknown>; price_amount: number; stock: number }>
  adopted_product_id: number | null
  adopted_status: string
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
  appointment?: { slot_id: number; slot_date: string; start_time: string; end_time: string; status: string }
  timeline?: Array<{
    from_status: string
    to_status: string
    event: string
    operator_type: string
    operator_name: string
    reason: string
    created_at: string
  }>
  status_logs?: Array<{
    from_status: string
    to_status: string
    event: string
    operator_type: string
    operator_name: string
    reason: string
    created_at: string
  }>
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

  async products(params: { merchant?: number; search?: string; category?: number } = {}) {
    const query = new URLSearchParams()
    if (params.merchant) query.set('merchant', String(params.merchant))
    if (params.category) query.set('category', String(params.category))
    if (params.search) query.set('search', params.search)
    const suffix = query.toString()
    const payload = await request<unknown>(`/products/${suffix ? `?${suffix}` : ''}`)
    return normalizeList<ProductRow>(payload)
  },

  product(id: number) {
    return request<ProductDetail>(`/products/${id}/`)
  },

  async stores(params: { lat: number; lng: number; category?: number; q?: string }) {
    const query = new URLSearchParams({ lat: String(params.lat), lng: String(params.lng) })
    if (params.category) query.set('category', String(params.category))
    if (params.q) query.set('q', params.q)
    return request<Paged<StoreRow>>(`/stores/nearby/?${query.toString()}`)
  },

  store(id: number) {
    return request<StoreRow>(`/stores/${id}/`)
  },

  async categories() {
    const payload = await request<unknown>('/categories/')
    return normalizeList<CategoryRow>(payload)
  },

  async addresses() {
    return request<AddressRow[]>('/addresses/')
  },

  createAddress(payload: Record<string, unknown>) {
    return request<AddressRow>('/addresses/', { method: 'POST', data: payload })
  },

  deleteAddress(id: number) {
    return request<void>(`/addresses/${id}/`, { method: 'DELETE' })
  },

  review(orderId: number, score: number, content = '') {
    return request<unknown>(`/orders/${orderId}/review/`, { method: 'POST', data: { score, content } })
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
    appointment?: { slot_id: number; remark?: string }
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

  merchantProducts(status = '', q = '') {
    const query = new URLSearchParams()
    if (status) query.set('status', status)
    if (q) query.set('q', q)
    const suffix = query.toString()
    return request<Paged<MerchantProductRow>>(`/merchant/products/${suffix ? `?${suffix}` : ''}`)
  },

  merchantProduct(id: number) {
    return request<MerchantProductDetail>(`/merchant/products/${id}/`)
  },

  createMerchantProduct(payload: MerchantProductPayload) {
    return request<MerchantProductDetail>('/merchant/products/', {
      method: 'POST',
      data: payload,
      headers: { 'Idempotency-Key': idempotencyKey() },
    })
  },

  updateMerchantProduct(id: number, payload: MerchantProductPayload) {
    return request<MerchantProductDetail>(`/merchant/products/${id}/`, { method: 'PUT', data: payload })
  },

  setMerchantProductStatus(id: number, status: 'ON_SALE' | 'OFF_SALE') {
    return request<{ id: number; status: string; version: number }>(`/merchant/products/${id}/status/`, {
      method: 'POST',
      data: { status },
    })
  },

  merchantProductCategories() {
    return request<MerchantProductCategoryRow[]>('/merchant/product-categories/')
  },

  merchantTemplates() {
    return request<MerchantTemplateRow[]>('/merchant/product-templates/')
  },

  adoptTemplate(id: number, listed = true) {
    return request<{ product_id: number; status: string }>(`/merchant/product-templates/${id}/adopt/`, {
      method: 'POST',
      data: { listed },
    })
  },

  createMerchantProductCategory(payload: { name: string; sort?: number; status?: string }) {
    return request<MerchantProductCategoryRow>('/merchant/product-categories/', { method: 'POST', data: payload })
  },

  updateMerchantProductCategory(id: number, payload: { name: string; sort?: number; status?: string }) {
    return request<MerchantProductCategoryRow>(`/merchant/product-categories/${id}/`, {
      method: 'PUT',
      data: payload,
    })
  },

  deleteMerchantProductCategory(id: number) {
    return request<void>(`/merchant/product-categories/${id}/`, { method: 'DELETE' })
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
