import { useLoad, useRouter } from '@tarojs/taro'
import { View, Text } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError, type OrderRow } from '../../../api'
import { formatMoney } from '../../../format'

const STATUS_LABEL: Record<string, string> = {
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

export default function MerchantOrderDetail() {
  const router = useRouter()
  const orderId = Number(router.params.id)
  const [order, setOrder] = useState<OrderRow | null>(null)
  const [error, setError] = useState('')

  useLoad(async () => {
    try {
      setOrder(await api.merchantOrder(orderId))
    } catch (exc) {
      setError(exc instanceof ApiError ? `${exc.code}：${exc.message}` : '加载失败')
    }
  })

  return (
    <View className="page">
      <View className="title">订单分账</View>
      {error && <View className="muted" aria-live="polite">{error}</View>}
      {order && (
        <View className="card">
          <View className="row">
            <Text className="muted">{order.order_no}</Text>
            <Text className="tag">{STATUS_LABEL[order.status] ?? order.status}</Text>
          </View>
          <View className="row"><Text>商品实付</Text><Text className="price">{formatMoney(order.product_amount ?? 0)}</Text></View>
          <View className="row"><Text>配送费</Text><Text>{formatMoney(order.delivery_fee ?? 0)}</Text></View>
          <View className="row"><Text>平台佣金</Text><Text>{formatMoney(order.platform_income_amount ?? 0)}</Text></View>
          <View className="row"><Text>商家应得</Text><Text>{formatMoney(order.merchant_income_amount ?? 0)}</Text></View>
          <View className="row"><Text>已退款</Text><Text>{formatMoney(order.refunded_amount)}</Text></View>
          <View className="row"><Text>商家承担退款</Text><Text>{formatMoney(order.merchant_refund_amount ?? 0)}</Text></View>
        </View>
      )}

      <View className="muted" style={{ marginBottom: '12px' }}>商品行分账</View>
      {(order?.items ?? []).map((item) => (
        <View key={item.id} className="card">
          <View className="row">
            <Text style={{ fontSize: '28px' }}>{item.title}</Text>
            <Text className="muted">×{item.quantity}</Text>
          </View>
          <View className="row"><Text className="muted">行实付</Text><Text>{formatMoney(item.paid_amount ?? item.amount)}</Text></View>
          <View className="row"><Text className="muted">平台佣金</Text><Text>{formatMoney(item.platform_amount ?? 0)}</Text></View>
          <View className="row"><Text className="muted">商家应得</Text><Text>{formatMoney(item.merchant_amount ?? 0)}</Text></View>
          {item.refund_amount ? (
            <View className="row"><Text className="muted">退款</Text><Text>{formatMoney(item.refund_amount)}</Text></View>
          ) : null}
          {item.refund_amount ? (
            <View className="row">
              <Text className="muted">退款后平台 / 商家</Text>
              <Text>{formatMoney(item.platform_net_amount ?? 0)} / {formatMoney(item.merchant_net_amount ?? 0)}</Text>
            </View>
          ) : null}
        </View>
      ))}
    </View>
  )
}
