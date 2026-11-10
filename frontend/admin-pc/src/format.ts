const moneyFormatter = new Intl.NumberFormat('zh-CN', {
  style: 'currency',
  currency: 'CNY',
  minimumFractionDigits: 2,
})

const dateTimeFormatter = new Intl.DateTimeFormat('zh-CN', {
  dateStyle: 'medium',
  timeStyle: 'short',
})

export function formatMoney(fen: number | null | undefined): string {
  return moneyFormatter.format((fen ?? 0) / 100)
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return dateTimeFormatter.format(date)
}

export const INDUSTRY_OPTIONS: Array<{ value: string; label: string }> = [
  { value: 'RESTAURANT', label: '餐饮' },
  { value: 'ACCOMMODATION', label: '酒店民宿' },
  { value: 'BEAUTY', label: '美容美发' },
  { value: 'FITNESS', label: '健身运动' },
  { value: 'RETAIL', label: '零售' },
  { value: 'LIFE_SERVICE', label: '生活服务' },
  { value: 'OTHER', label: '其他' },
]
