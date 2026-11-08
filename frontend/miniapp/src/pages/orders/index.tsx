import { useLoad, useRouter } from '@tarojs/taro'
import { View, Text, Navigator, Button } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError, type OrderRow } from '../../api'
import BottomNav from '../../components/BottomNav'
import { formatDateTime, formatMoney } from '../../format'

const statusLabel: Record<string, string> = {
  PENDING_PAYMENT: '待支付',
  PENDING_ACCEPT: '待接单',
  PENDING_FULFILL: '待履约',
  FULFILLING: '配送/服务中',
  COMPLETED: '已完成',
  AFTER_SALE: '售后中',
  REFUNDING: '退款中',
  REFUNDED: '已退款',
  CLOSED: '已关闭',
}

const TABS = [
  { value: '', label: '全部' },
  { value: 'PENDING_ACCEPT', label: '待接单' },
  { value: 'PENDING_FULFILL', label: '待履约' },
  { value: 'COMPLETED', label: '已完成' },
]

export default function Orders() {
  const router = useRouter()
  const [items, setItems] = useState<OrderRow[]>([])
  const [status, setStatus] = useState(router.params.status || '')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  async function load(nextStatus = status) {
    setLoading(true)
    setStatus(nextStatus)
    setError('')
    try {
      setItems(await api.orders(nextStatus))
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useLoad(() => load(router.params.status || ''))

  return (
    <View className="page">
      <Text className="eyebrow">MY ORDERS</Text>
      <View className="title">订单</View>
      <View className="sku-row" style={{ marginBottom: '18px' }}>
        {TABS.map((tab) => (
          <Button
            key={tab.value || 'ALL'}
            className={`chip ${status === tab.value ? 'active' : ''}`}
            onClick={() => load(tab.value)}
          >
            {tab.label}
          </Button>
        ))}
      </View>
      {error && <View className="muted" aria-live="polite">{error}</View>}
      {loading && <View className="muted">加载中…</View>}
      {items.map((order) => (
        <Navigator key={order.id} url={`/pages/order-detail/index?id=${order.id}`} className="order-card">
          <View className="row" style={{ paddingTop: 0 }}>
            <Text className="muted">ORDER · {order.order_no}</Text>
            <Text className="tag">{statusLabel[order.status] ?? order.status}</Text>
          </View>
          <View className="row">
            <View>
              <Text style={{ display: 'block', fontSize: '30px', fontWeight: 600 }}>{order.merchant_name || '门店订单'}</Text>
              <Text className="muted">{formatDateTime(order.created_at)}</Text>
            </View>
            <Text className="price">{formatMoney(order.payable_amount)}</Text>
          </View>
        </Navigator>
      ))}
      {!loading && !items.length && <View className="muted">暂无订单</View>}
      <BottomNav />
    </View>
  )
}
