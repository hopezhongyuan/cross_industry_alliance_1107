import { Text } from '@tarojs/components'

type Kind = 'order' | 'product' | 'aftersale' | 'statement' | 'merchant'

const ORDER_MAP: Record<string, { label: string; cls: string }> = {
  PENDING_PAYMENT: { label: '待支付', cls: 'warn' },
  PENDING_ACCEPT: { label: '待接单', cls: 'danger' },
  PENDING_FULFILL: { label: '待发货', cls: 'danger' },
  FULFILLING: { label: '履约中', cls: 'info' },
  COMPLETED: { label: '已完成', cls: 'success' },
  AFTER_SALE: { label: '售后中', cls: 'warn' },
  REFUNDING: { label: '退款中', cls: 'warn' },
  REFUNDED: { label: '已退款', cls: 'muted' },
  CLOSED: { label: '已关闭', cls: 'muted' },
}

const PRODUCT_MAP: Record<string, { label: string; cls: string }> = {
  DRAFT: { label: '草稿', cls: 'muted' },
  PENDING_AUDIT: { label: '待审核', cls: 'danger' },
  ON_SALE: { label: '在售', cls: 'success' },
  OFF_SALE: { label: '已下架', cls: 'muted' },
  REJECTED: { label: '已驳回', cls: 'danger' },
}

const AFTERSALE_MAP: Record<string, { label: string; cls: string }> = {
  APPLIED: { label: '已申请', cls: 'danger' },
  MERCHANT_PROCESSING: { label: '处理中', cls: 'info' },
  MERCHANT_AGREED: { label: '已同意', cls: 'success' },
  MERCHANT_REJECTED: { label: '已拒绝', cls: 'muted' },
  ARBITRATING: { label: '仲裁中', cls: 'warn' },
  RESOLVED: { label: '已裁定', cls: 'muted' },
  REFUNDING: { label: '退款中', cls: 'warn' },
  COMPLETED: { label: '已完成', cls: 'success' },
  CANCELLED: { label: '已取消', cls: 'muted' },
}

const STATEMENT_MAP: Record<string, { label: string; cls: string }> = {
  PENDING: { label: '待结算', cls: 'warn' },
  FROZEN: { label: '冻结', cls: 'muted' },
  SETTLED: { label: '已结算', cls: 'success' },
}

const MERCHANT_MAP: Record<string, { label: string; cls: string }> = {
  ACTIVE: { label: '营业中', cls: 'success' },
  RESTING: { label: '休息中', cls: 'muted' },
  BANNED: { label: '已冻结', cls: 'danger' },
  PENDING: { label: '待审核', cls: 'warn' },
}

function resolve(kind: Kind, status: string, label?: string) {
  const map = kind === 'order' ? ORDER_MAP : kind === 'product' ? PRODUCT_MAP : kind === 'aftersale' ? AFTERSALE_MAP : kind === 'statement' ? STATEMENT_MAP : MERCHANT_MAP
  const found = map[status]
  return { label: label || found?.label || status, cls: found?.cls || 'muted' }
}

type Props = {
  kind: Kind
  status: string | undefined
  label?: string
}

export default function StatusBadge({ kind, status, label }: Props) {
  const { label: text, cls } = resolve(kind, status || '', label)
  return <Text className={`mch-badge mch-badge-${cls}`}>{text}</Text>
}
