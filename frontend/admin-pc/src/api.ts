import type { components } from '../../shared/schema'

export type Schemas = components['schemas']
type RequiredPick<T, K extends keyof T> = Required<Pick<T, K>>

export type Page = RequiredPick<Schemas['Page'], 'page' | 'page_size' | 'total' | 'has_more'>
export type Paged<T> = { items: T[]; page: Page }

export type AdminOrderRow = {
  id: number
  order_no: string
  merchant_id: number
  merchant_name: string
  order_type: string
  status: string
  payable_amount: number
  paid_amount: number
  refunded_amount: number
  created_at: string
  completed_at: string | null
}

export type AdminOrderItem = {
  id: number
  title: string
  quantity: number
  amount: number
  paid_amount: number
  commission_rate: number
  platform_amount: number
  platform_refund_amount: number
  platform_net_amount: number
  merchant_amount: number
  merchant_refund_amount: number
  merchant_net_amount: number
  refund_amount: number
}

export type AdminOrderDetail = AdminOrderRow & {
  product_amount: number
  delivery_fee: number
  commission_rate: number
  commission_amount: number
  platform_income_amount: number
  merchant_income_amount: number
  platform_refund_amount: number
  merchant_refund_amount: number
  items: AdminOrderItem[]
}

export type StatementRow = RequiredPick<
  Schemas['StatementItem'],
  | 'order_no'
  | 'order_completed_at'
  | 'due_at'
  | 'product_amount'
  | 'delivery_fee'
  | 'commission_rate'
  | 'commission_amount'
  | 'refund_amount'
  | 'net_amount'
  | 'status'
>

export type SettlementRow = RequiredPick<
  Schemas['SettlementBatch'],
  | 'id'
  | 'batch_no'
  | 'period_start'
  | 'period_end'
  | 'status'
  | 'total_amount'
  | 'commission_amount'
  | 'net_amount'
  | 'items_count'
> & { published_at: string | null }

export type WithdrawalRow = RequiredPick<
  Schemas['Withdrawal'],
  'id' | 'withdrawal_no' | 'merchant_id' | 'amount' | 'net_amount' | 'status'
> & {
  fee: number
  requested_at: string | null
  paid_at: string | null
  voucher_no: string
  voucher_url: string
}

export type ArbitrationRow = RequiredPick<
  Schemas['ArbitrationCase'],
  'id' | 'case_no' | 'after_sale_no' | 'order_id' | 'amount' | 'status' | 'liability'
> & {
  after_sale_id: number
  merchant_id: number
  ruling: string
  deadline_at: string | null
  decided_at: string | null
  created_at: string
}

export type PaymentConfig = RequiredPick<
  Schemas['PaymentConfig'],
  'channel' | 'merchant_no' | 'app_id' | 'cert_serial_no' | 'notify_url' | 'enabled' | 'updated_by_name' | 'updated_at'
>

export type LogRow = RequiredPick<
  Schemas['OperationLog'],
  'id' | 'operator_name' | 'action' | 'biz_type' | 'created_at'
> & { biz_id: number | null; reason: string }

export type ArbitrationDetail = ArbitrationRow & {
  decided_by_name: string
  after_sale: {
    after_sale_no: string
    order_id: number
    merchant_id: number
    merchant_name: string
    user_id: number
    user_name: string
    type: string
    status: string
    request_amount: number
    approved_amount: number
    description: string
    evidence: string[]
    merchant_decision: string
    merchant_reason: string
    deadline_at: string | null
    created_at: string
  }
}

export type Reconciliation = {
  date: string
  checks: Array<{ name: string; status: string; diff_count: number; diff_amount: number }>
  unresolved_count: number
}

export type AdminMerchantRow = {
  id: number
  merchant_no: string
  name: string
  short_name: string
  category_id: number | null
  category_name: string
  industry: string
  industry_label: string
  contact_phone: string
  city: string
  district: string
  status: string
  commission_rate: number
  settlement_cycle_days: number
  delivery_fee: number
  today_orders: number
  settled_amount: number
  created_at: string
}

export type MerchantSummary = {
  total: number
  active: number
  pending: number
  resting: number
  banned: number
  rejected: number
}

export type MerchantPage = { items: AdminMerchantRow[]; page: Page; summary: MerchantSummary }

export type MerchantQualification = {
  id: number
  type: string
  type_label: string
  file_url: string
  expire_at: string | null
  audit_status: string
  reject_reason: string
}

export type MerchantStaff = {
  id: number
  user_id: number
  nickname: string
  role: string
  role_label: string
  status: string
  joined_at: string | null
}

export type AdminMerchantDetail = AdminMerchantRow & {
  logo_url: string
  description: string
  province: string
  address: string
  lng: number | null
  lat: number | null
  business_hours: Record<string, unknown>
  opened_at: string | null
  commission_override: number | null
  gmv_total: number
  bank_last4: string
  balances: {
    pending_amount: number
    frozen_amount: number
    available_amount: number
    withdrawing_amount: number
  }
  qualifications: MerchantQualification[]
  staff: MerchantStaff[]
}

export type AuditTaskRow = {
  id: number
  biz_type: string
  biz_id: number
  biz_name: string
  status: string
  decision: string
  reason: string
  assigned_to_name: string
  handled_at: string | null
  created_at: string
}

export type AuditPage = { items: AuditTaskRow[]; page: Page; summary: Record<string, number> }

export type CategoryRow = { id: number; parent: number | null; name: string; icon_url: string; level: number; sort: number }

export type StaffUser = { id: number; phone: string; nickname: string; status: string }

export type AdminUserRow = {
  id: number
  nickname: string
  phone_masked: string
  avatar_url: string
  gender: string
  status: string
  is_staff: boolean
  user_type: string
  merchant_names: string[]
  last_login: string | null
  created_at: string
}

export type AdminPlatformConfig = {
  platform_name: string
  logo_url: string
  contact_phone: string
  company_name: string
  icp_no: string
  privacy_policy: string
  user_agreement: string
  agreement_version: string
  miniapp_app_id: string
  miniapp_app_secret_configured: boolean
  miniapp_app_secret_masked: string
  miniapp_original_id: string
  amap_web_key_configured: boolean
  amap_web_key_masked: string
  amap_js_key: string
  amap_js_security_code_configured: boolean
  amap_js_security_code_masked: string
  amap_enabled: boolean
  updated_by_name: string
  updated_at: string
}

export type AdminPlatformConfigPayload = {
  platform_name: string
  logo_url: string
  contact_phone: string
  company_name: string
  icp_no: string
  privacy_policy: string
  user_agreement: string
  agreement_version: string
  miniapp_app_id: string
  miniapp_app_secret: string
  miniapp_original_id: string
  amap_web_key: string
  amap_js_key: string
  amap_js_security_code: string
  amap_enabled: boolean
}

export type StoreNavItem = {
  id?: number
  title: string
  icon_selected: string
  icon_unselected: string
  link_type: string
  link_value: string
  sort?: number
  status: string
}

export type DecoComponent = {
  id: string
  type: string
  config: Record<string, any>
}

export type DecoPageRow = {
  id: number
  slug: string
  title: string
  status: string
  component_count: number
  published_at: string | null
  updated_by_name: string
  updated_at: string
}

export type DecoPageDetail = DecoPageRow & {
  share_title: string
  share_image: string
  draft_components: DecoComponent[]
  published_components: DecoComponent[]
}

export type DecoPagePayload = {
  slug: string
  title: string
  share_title: string
  share_image: string
  draft_components: DecoComponent[]
}

export type MerchantLocationPayload = {
  lng: string
  lat: string
  province?: string
  city?: string
  district?: string
  address?: string
}

export type MerchantSkuRow = {
  id: number
  sku_code: string
  spec_json: Record<string, unknown>
  price: number
  stock: number
  available_stock: number
}

export type AdminProductDetail = {
  id: number
  product_code: string
  merchant_id: number
  merchant_name: string
  merchant_no: string
  category_id: number | null
  category_name: string
  merchant_category_id: number | null
  merchant_category_name: string
  type: string
  type_label: string
  title: string
  subtitle: string
  cover_url: string
  images: string[]
  description: string
  price: number
  original_price: number
  status: string
  reject_reason: string
  off_sale_by: string
  off_sale_reason: string
  verify_days: number
  appointment_required: boolean
  delivery_types: string[]
  sold_count: number
  skus: MerchantSkuRow[]
  submitted_at: string | null
  audited_at: string | null
  version: number
  created_at: string
}

export type AdminCategory = {
  id: number
  parent: number | null
  parent_name: string
  name: string
  icon_url: string
  level: number
  sort: number
  status: string
}

export type AdminCategoryPayload = {
  name: string
  parent_id?: number | null
  icon_url?: string
  sort?: number
  status?: string
}

export type MediaFolder = { id: number; name: string; sort: number; asset_count: number; created_at: string }

export type MediaAsset = {
  id: number
  name: string
  original_name: string
  kind: string
  url: string
  mime: string
  size: number
  width: number | null
  height: number | null
  duration_ms: number | null
  folder: number | null
  folder_name: string
  created_by_name: string
  created_at: string
}

export type ProductTemplate = {
  id: number
  template_no: string
  title: string
  subtitle: string
  type: string
  category_id: number
  category_name: string
  cover_url: string
  images: string[]
  description: string
  price: number
  original_price: number
  verify_days: number
  appointment_required: boolean
  delivery_types: string[]
  skus: Array<{ sku_code: string; spec: Record<string, unknown>; price_amount: number; stock: number }>
  status: string
  scope: string
  target_merchant_ids: number[]
  adoption_count: number
  published_at: string | null
  created_at: string
}

export type ProductTemplatePayload = {
  title: string
  subtitle: string
  type: string
  category_id: number
  cover_url: string
  images: string[]
  description: string
  price_amount: number
  original_price_amount: number
  verify_days: number
  appointment_required: boolean
  delivery_types: string[]
  skus: Array<{ sku_code: string; spec: Record<string, unknown>; price_amount: number; stock: number }>
  status: string
  scope: string
  merchant_ids: number[]
}

export type AdminProductRow = {
  id: number
  product_code: string
  title: string
  merchant_id: number
  merchant_name: string
  category_id: number | null
  category_name: string
  type: string
  price: number
  status: string
  sold_count: number
  off_sale_by: string
  off_sale_reason: string
  updated_at: string
}

export type MerchantCreatePayload = {
  name: string
  short_name?: string
  category_id: number
  industry?: string
  contact_phone: string
  province?: string
  city: string
  district: string
  address: string
  commission_rate?: string | null
  settlement_cycle_days?: number
  delivery_fee?: number
  bank_info?: { bank?: string; card_no?: string }
  qualifications?: Array<{ type: string; file_url: string; expire_at?: string | null }>
  owner_phone: string
}



export type BatchActionResultItem = {
  id: number
  ok: boolean
  status: string
  off_sale_by?: string
  error_code: string
  error_message: string
}

export type BatchActionResult = {
  items: BatchActionResultItem[]
  succeeded: number
  failed: number
}

const BASE_URL = import.meta.env.VITE_API_BASE ?? '/api/v1'
const TOKEN_KEY = 'alliance_admin_token'

export class ApiError extends Error {
  code: string
  status: number
  details: unknown

  constructor(code: string, message: string, status: number, details?: unknown) {
    super(message)
    this.code = code
    this.status = status
    this.details = details
  }
}

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) ?? ''
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
}

type RequestOptions = {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  body?: unknown
  headers?: Record<string, string>
}

function unwrap<T>(payload: unknown): T {
  if (payload && typeof payload === 'object' && 'code' in payload && 'data' in payload) {
    return (payload as { data: T }).data
  }
  return payload as T
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const isForm = options.body instanceof FormData
  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...(options.headers ?? {}),
  }
  if (options.body !== undefined && !isForm) headers['Content-Type'] = 'application/json'
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`

  const response = await fetch(`${BASE_URL}${path}`, {
    method: options.method ?? 'GET',
    headers,
    body: options.body === undefined ? undefined : isForm ? (options.body as FormData) : JSON.stringify(options.body),
  })
  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    const body = (payload ?? {}) as { code?: string; message?: string; details?: unknown }
    throw new ApiError(body.code ?? `HTTP_${response.status}`, body.message ?? '请求失败', response.status, body.details)
  }
  return unwrap<T>(payload)
}

function query(params: Record<string, string | number | undefined>): string {
  const entries = Object.entries(params).filter(([, value]) => value !== undefined && value !== '')
  if (entries.length === 0) return ''
  return `?${new URLSearchParams(entries.map(([key, value]) => [key, String(value)]))}`
}

function idempotencyKey(): string {
  return crypto.randomUUID().replace(/-/g, '')
}

export const api = {
  async login(phone: string, password: string) {
    const token = await request<{ access: string; refresh: string }>('/accounts/auth/token/', {
      method: 'POST',
      body: { phone, password },
    })
    setToken(token.access)
    return token
  },

  adminOrders(params: { status?: string; merchant_id?: number; order_no?: string; page?: number; page_size?: number }) {
    return request<Paged<AdminOrderRow>>(`/admin/orders/${query(params)}`)
  },

  adminOrderDetail(orderId: number) {
    return request<AdminOrderDetail>(`/admin/orders/${orderId}/`)
  },

  freezeOrder(orderId: number, action: 'FREEZE' | 'UNFREEZE', reason: string) {
    return request<{ order_id: number; status: string }>(`/admin/orders/${orderId}/freeze/`, {
      method: 'POST',
      body: { action, reason },
      headers: { 'Idempotency-Key': idempotencyKey() },
    })
  },

  adminMerchants(params: {
    status?: string
    q?: string
    category?: string
    city?: string
    industry?: string
    page?: number
    page_size?: number
  }) {
    return request<MerchantPage>(`/admin/merchants/${query(params)}`)
  },

  updateMerchantProfile(merchantId: number, payload: { industry?: string; delivery_fee?: number }) {
    return request<{ id: number; industry: string; delivery_fee: number }>(
      `/admin/merchants/${merchantId}/profile/`,
      { method: 'PATCH', body: payload },
    )
  },

  adminMerchantDetail(merchantId: number) {
    return request<AdminMerchantDetail>(`/admin/merchants/${merchantId}/`)
  },

  createMerchant(payload: MerchantCreatePayload) {
    return request<AdminMerchantDetail>('/admin/merchants/', {
      method: 'POST',
      body: payload,
      headers: { 'Idempotency-Key': idempotencyKey() },
    })
  },

  categories() {
    return request<CategoryRow[]>('/categories/')
  },

  staffUsers(keyword: string) {
    return request<StaffUser[]>(`/accounts/staff/users/${query({ keyword })}`)
  },

  adminUsers(params: { status?: string; user_type?: string; q?: string; page?: number; page_size?: number }) {
    return request<Paged<AdminUserRow>>(`/admin/users/${query(params)}`)
  },

  adminPlatformConfig() {
    return request<AdminPlatformConfig>('/admin/platform-config/')
  },

  saveAdminPlatformConfig(payload: AdminPlatformConfigPayload) {
    return request<AdminPlatformConfig>('/admin/platform-config/', { method: 'PUT', body: payload })
  },

  adminStoreNav() {
    return request<StoreNavItem[]>('/admin/storefront/nav/')
  },

  saveAdminStoreNav(items: StoreNavItem[]) {
    return request<StoreNavItem[]>('/admin/storefront/nav/', { method: 'PUT', body: { items } })
  },

  adminDecoPages(params: { status?: string; page?: number; page_size?: number } = {}) {
    return request<Paged<DecoPageRow>>(`/admin/storefront/pages/${query(params)}`)
  },

  adminDecoPage(pageId: number) {
    return request<DecoPageDetail>(`/admin/storefront/pages/${pageId}/`)
  },

  createDecoPage(payload: DecoPagePayload) {
    return request<DecoPageDetail>('/admin/storefront/pages/', { method: 'POST', body: payload })
  },

  updateDecoPage(pageId: number, payload: DecoPagePayload) {
    return request<DecoPageDetail>(`/admin/storefront/pages/${pageId}/`, { method: 'PUT', body: payload })
  },

  deleteDecoPage(pageId: number) {
    return request<void>(`/admin/storefront/pages/${pageId}/`, { method: 'DELETE' })
  },

  publishDecoPage(pageId: number) {
    return request<DecoPageDetail>(`/admin/storefront/pages/${pageId}/publish/`, { method: 'POST', body: {} })
  },

  updateMerchantLocation(merchantId: number, payload: MerchantLocationPayload) {
    return request<{ id: number; lng: string; lat: string; address: string }>(
      `/admin/merchants/${merchantId}/location/`,
      { method: 'PUT', body: payload },
    )
  },

  changeMerchantStatus(merchantId: number, status: string, reason: string) {
    return request<{ id: number; status: string; changed: boolean }>(`/admin/merchants/${merchantId}/status/`, {
      method: 'POST',
      body: { status, reason },
      headers: { 'Idempotency-Key': idempotencyKey() },
    })
  },

  audits(params: { biz_type?: string; status?: string; page?: number; page_size?: number }) {
    return request<AuditPage>(`/admin/audits/${query(params)}`)
  },

  adminProductDetail(productId: number) {
    return request<AdminProductDetail>(`/admin/products/${productId}/`)
  },

  adminCategories() {
    return request<AdminCategory[]>('/admin/categories/')
  },

  createCategory(payload: AdminCategoryPayload) {
    return request<AdminCategory>('/admin/categories/', { method: 'POST', body: payload })
  },

  updateCategory(categoryId: number, payload: AdminCategoryPayload) {
    return request<AdminCategory>(`/admin/categories/${categoryId}/`, { method: 'PUT', body: payload })
  },

  adminProducts(params: {
    status?: string
    merchant_id?: number
    category?: number
    q?: string
    page?: number
    page_size?: number
  }) {
    return request<Paged<AdminProductRow>>(`/admin/products/${query(params)}`)
  },

  updateAdminProduct(productId: number, payload: Record<string, unknown>) {
    return request<AdminProductDetail>(`/admin/products/${productId}/`, { method: 'PUT', body: payload })
  },

  setAdminProductStatus(productId: number, action: 'FORCE_OFF' | 'RESTORE', reason = '') {
    return request<{ id: number; status: string; off_sale_by: string }>(`/admin/products/${productId}/status/`, {
      method: 'POST',
      body: { action, reason },
    })
  },

  batchAdminProductStatus(ids: number[], action: 'FORCE_OFF' | 'RESTORE', reason = '') {
    return request<BatchActionResult>('/admin/products/batch-status/', {
      method: 'POST',
      body: { ids, action, reason },
    })
  },

  adminTemplates(params: { status?: string; page?: number; page_size?: number } = {}) {
    return request<Paged<ProductTemplate>>(`/admin/product-templates/${query(params)}`)
  },

  createTemplate(payload: ProductTemplatePayload) {
    return request<ProductTemplate>('/admin/product-templates/', { method: 'POST', body: payload })
  },

  updateTemplate(templateId: number, payload: ProductTemplatePayload) {
    return request<ProductTemplate>(`/admin/product-templates/${templateId}/`, { method: 'PUT', body: payload })
  },

  syncTemplate(templateId: number, merchantIds: number[] = []) {
    return request<{ template_id: number; synced: number }>(`/admin/product-templates/${templateId}/sync/`, {
      method: 'POST',
      body: { merchant_ids: merchantIds },
    })
  },

  mediaFolders() {
    return request<MediaFolder[]>('/admin/media-folders/')
  },

  createMediaFolder(payload: { name: string; sort?: number }) {
    return request<MediaFolder>('/admin/media-folders/', { method: 'POST', body: payload })
  },

  updateMediaFolder(folderId: number, payload: { name: string; sort?: number }) {
    return request<MediaFolder>(`/admin/media-folders/${folderId}/`, { method: 'PUT', body: payload })
  },

  deleteMediaFolder(folderId: number) {
    return request<void>(`/admin/media-folders/${folderId}/`, { method: 'DELETE' })
  },

  mediaAssets(params: { folder?: string; kind?: string; q?: string; page?: number; page_size?: number } = {}) {
    return request<Paged<MediaAsset>>(`/admin/media-assets/${query(params)}`)
  },

  uploadMediaAsset(file: File, folderId: number | null = null, name = '') {
    const form = new FormData()
    form.append('file', file)
    if (folderId !== null) form.append('folder_id', String(folderId))
    if (name) form.append('name', name)
    return request<MediaAsset>('/admin/media-assets/', { method: 'POST', body: form })
  },

  uploadMediaAssetWithProgress(
    file: File,
    folderId: number | null = null,
    onProgress?: (percent: number) => void,
  ) {
    const form = new FormData()
    form.append('file', file)
    if (folderId !== null) form.append('folder_id', String(folderId))
    return new Promise<MediaAsset>((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      xhr.open('POST', `${BASE_URL}/admin/media-assets/`)
      const token = getToken()
      if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)
      xhr.setRequestHeader('Accept', 'application/json')
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable && onProgress) {
          onProgress(Math.round((event.loaded / event.total) * 100))
        }
      }
      xhr.onload = () => {
        const payload = xhr.responseText ? JSON.parse(xhr.responseText) : null
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(unwrap<MediaAsset>(payload))
          return
        }
        const body = (payload ?? {}) as { code?: string; message?: string }
        reject(new ApiError(body.code ?? `HTTP_${xhr.status}`, body.message ?? '上传失败', xhr.status))
      }
      xhr.onerror = () => reject(new ApiError('NETWORK_ERROR', '网络异常，上传失败', 0))
      xhr.send(form)
    })
  },

  deleteMediaAsset(assetId: number) {
    return request<void>(`/admin/media-assets/${assetId}/`, { method: 'DELETE' })
  },

  decideAudit(taskId: number, decision: 'APPROVE' | 'REJECT', reason = '') {
    return request<AuditTaskRow>(`/admin/audits/${taskId}/decision/`, {
      method: 'POST',
      body: { decision, reason },
      headers: { 'Idempotency-Key': idempotencyKey() },
    })
  },

  batchDecideAudit(ids: number[], decision: 'APPROVE' | 'REJECT', reason = '') {
    return request<BatchActionResult>('/admin/audits/batch-decision/', {
      method: 'POST',
      body: { ids, decision, reason },
    })
  },

  arbitrations(params: { status?: string; page?: number; page_size?: number }) {
    return request<Paged<ArbitrationRow>>(`/admin/arbitrations/${query(params)}`)
  },

  arbitrationDetail(caseId: number) {
    return request<ArbitrationDetail>(`/admin/arbitrations/${caseId}/`)
  },

  ruleArbitration(
    caseId: number,
    payload: { liability: string; refund_amount: number; ruling: string },
  ) {
    return request<unknown>(`/admin/arbitrations/${caseId}/rule/`, {
      method: 'POST',
      body: payload,
      headers: { 'Idempotency-Key': idempotencyKey() },
    })
  },

  settlements(params: { status?: string; page?: number; page_size?: number }) {
    return request<Paged<SettlementRow>>(`/admin/settlements/${query(params)}`)
  },

  publishSettlement(batchId: number) {
    return request<SettlementRow>(`/admin/settlements/${batchId}/publish/`, { method: 'POST', body: {} })
  },

  withdrawals(params: { status?: string; merchant_id?: number; page?: number; page_size?: number }) {
    return request<Paged<WithdrawalRow>>(`/admin/withdrawals/${query(params)}`)
  },

  payoutWithdrawal(withdrawalId: number, payload: { voucher_no: string; voucher_url: string; paid_at: string }) {
    return request<WithdrawalRow>(`/admin/withdrawals/${withdrawalId}/payout/`, {
      method: 'POST',
      body: payload,
      headers: { 'Idempotency-Key': idempotencyKey() },
    })
  },

  rejectWithdrawal(withdrawalId: number, reason: string) {
    return request<WithdrawalRow>(`/admin/withdrawals/${withdrawalId}/reject/`, {
      method: 'POST',
      body: { reason },
      headers: { 'Idempotency-Key': idempotencyKey() },
    })
  },

  paymentConfig(channel: string) {
    return request<PaymentConfig>(`/admin/payment-configs/${channel}/`)
  },

  savePaymentConfig(channel: string, payload: Record<string, unknown>) {
    return request<PaymentConfig>(`/admin/payment-configs/${channel}/`, { method: 'PUT', body: payload })
  },

  reconciliation(date: string) {
    return request<Reconciliation>(`/admin/reconciliation/${query({ date })}`)
  },

  logs(params: { biz_type?: string; operator?: string; biz_id?: number; page?: number; page_size?: number }) {
    return request<Paged<LogRow>>(`/admin/logs/${query(params)}`)
  },

  publishRule(snapshot: Record<string, unknown>, remark = '') {
    return request<unknown>('/admin/rules/', { method: 'PUT', body: { snapshot, remark } })
  },

  // ---------- 积分 ----------
  pointsConfig() {
    return request<Schemas['PointsConfig']>('/admin/points/config/')
  },

  savePointsConfig(payload: Partial<Schemas['PointsConfig']>) {
    return request<Schemas['PointsConfig']>('/admin/points/config/', { method: 'PUT', body: payload })
  },

  pointsUsers(params: { keyword?: string; page?: number; page_size?: number } = {}) {
    return request<Paged<Schemas['PointAccount']>>(`/admin/points/users/${query(params)}`)
  },

  pointsUserTransactions(userId: number, params: { page?: number; page_size?: number } = {}) {
    return request<Paged<Schemas['PointTransaction']>>(`/admin/points/users/${userId}/transactions/${query(params)}`)
  },

  adjustPoints(payload: { user_id: number; delta: number; reason: string }) {
    return request<Schemas['PointTransaction']>('/admin/points/adjust/', { method: 'POST', body: payload })
  },

  // ---------- 平台优惠券 ----------
  adminCoupons() {
    return request<Schemas['Coupon'][]>('/admin/coupons/')
  },

  createAdminCoupon(payload: Schemas['CouponCreateInput']) {
    return request<Schemas['Coupon']>('/admin/coupons/', {
      method: 'POST',
      body: payload,
      headers: { 'Idempotency-Key': idempotencyKey() },
    })
  },

  adminCouponStatus(couponId: number, action: 'pause' | 'activate') {
    return request<Schemas['Coupon']>(`/admin/coupons/${couponId}/${action}/`, { method: 'POST' })
  },

  // ---------- 弹窗广告 ----------
  adminPopupAds(params: { status?: string } = {}) {
    const qs = new URLSearchParams()
    if (params.status) qs.set('status', params.status)
    const suffix = qs.toString()
    return request<Schemas['PopupAd'][]>(`/admin/popup-ads/${suffix ? `?${suffix}` : ''}`)
  },

  createAdminPopupAd(payload: Schemas['PopupAdCreateInput']) {
    return request<Schemas['PopupAd']>('/admin/popup-ads/', {
      method: 'POST',
      body: payload,
      headers: { 'Idempotency-Key': idempotencyKey() },
    })
  },

  adminPopupAdStatus(popupId: number, action: 'enable' | 'disable') {
    return request<Schemas['PopupAd']>(`/admin/popup-ads/${popupId}/${action}/`, { method: 'POST' })
  },
}
