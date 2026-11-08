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

export type Reconciliation = {
  date: string
  checks: Array<{ name: string; status: string; diff_count: number; diff_amount: number }>
  unresolved_count: number
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
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
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
  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...(options.headers ?? {}),
  }
  if (options.body !== undefined) headers['Content-Type'] = 'application/json'
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`

  const response = await fetch(`${BASE_URL}${path}`, {
    method: options.method ?? 'GET',
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
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

  freezeOrder(orderId: number, action: 'FREEZE' | 'UNFREEZE', reason: string) {
    return request<{ order_id: number; status: string }>(`/admin/orders/${orderId}/freeze/`, {
      method: 'POST',
      body: { action, reason },
      headers: { 'Idempotency-Key': idempotencyKey() },
    })
  },

  arbitrations(params: { status?: string; page?: number; page_size?: number }) {
    return request<Paged<ArbitrationRow>>(`/admin/arbitrations/${query(params)}`)
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
}
