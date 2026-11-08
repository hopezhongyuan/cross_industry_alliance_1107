import { useLoad } from '@tarojs/taro'
import Taro from '@tarojs/taro'
import { View, Text } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError, type OrderRow } from '../../api'

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

export default function Orders() {
  const [items, setItems] = useState<OrderRow[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  async function load() {
    setLoading(true)
    try {
      setItems(await api.orders())
      setError('')
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useLoad(load)

  return (
    <View className="page">
      <View className="title">我的订单</View>
      {error && <View className="muted">{error}</View>}
      {items.map((order) => (
        <View
          key={order.id}
          className="card"
          onClick={() => Taro.navigateTo({ url: `/pages/order-detail/index?id=${order.id}` })}
        >
          <View className="row">
            <Text>{order.order_no}</Text>
            <Text className="tag">{statusLabel[order.status] ?? order.status}</Text>
          </View>
          <View className="row">
            <Text className="muted">{order.created_at}</Text>
            <Text className="price">¥{(order.payable_amount / 100).toFixed(2)}</Text>
          </View>
        </View>
      ))}
      {!loading && !items.length && <View className="muted">暂无订单</View>}
    </View>
  )
}
