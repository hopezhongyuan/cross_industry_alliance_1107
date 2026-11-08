import { useLoad, useRouter, showToast } from '@tarojs/taro'
import { View, Text, Input } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError, type OrderRow } from '../../api'

export default function OrderDetail() {
  const router = useRouter()
  const orderId = Number(router.params.id)
  const [order, setOrder] = useState<OrderRow | null>(null)
  const [error, setError] = useState('')
  const [showAfterSale, setShowAfterSale] = useState(false)
  const [amount, setAmount] = useState('')
  const [reason, setReason] = useState('')

  async function load() {
    try {
      const result = await api.order(orderId)
      setOrder(result)
      setAmount(String(result.payable_amount))
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : '加载失败')
    }
  }

  useLoad(load)

  async function confirmReceive() {
    try {
      await api.confirmOrder(orderId)
      showToast({ title: '已确认收货', icon: 'success' })
      await load()
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : '操作失败')
    }
  }

  async function cancel() {
    try {
      await api.cancelOrder(orderId)
      showToast({ title: '已取消', icon: 'success' })
      await load()
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : '取消失败')
    }
  }

  async function submitAfterSale() {
    const fen = Number(amount)
    if (!fen) {
      setError('请输入退款金额（分）')
      return
    }
    try {
      await api.applyAfterSale({
        order_id: orderId,
        type: 'REFUND_ONLY',
        reason_code: 'SERVICE_ISSUE',
        request_amount: fen,
        description: reason,
      })
      setShowAfterSale(false)
      showToast({ title: '售后已提交', icon: 'success' })
      await load()
    } catch (exc) {
      setError(exc instanceof ApiError ? `${exc.code}：${exc.message}` : '申请失败')
    }
  }

  return (
    <View className="page">
      <View className="title">订单详情</View>
      {error && <View className="muted">{error}</View>}
      {order && (
        <View className="card">
          <View className="row"><Text>订单号</Text><Text>{order.order_no}</Text></View>
          <View className="row"><Text>状态</Text><Text className="tag">{order.status}</Text></View>
          <View className="row"><Text>应付</Text><Text className="price">¥{(order.payable_amount / 100).toFixed(2)}</Text></View>
          <View className="row"><Text>已退</Text><Text>¥{(order.refunded_amount / 100).toFixed(2)}</Text></View>
          {order.verify_codes?.map((code) => (
            <View key={code.code} className="row"><Text>核销码</Text><Text className="tag">{code.code}</Text></View>
          ))}
        </View>
      )}

      {order?.status === 'FULFILLING' && (
        <View className="btn" onClick={confirmReceive}>确认收货</View>
      )}
      {order?.status === 'PENDING_ACCEPT' && (
        <View className="btn secondary" onClick={cancel}>取消订单</View>
      )}
      {order?.status === 'COMPLETED' && (
        <View className="btn secondary" onClick={() => setShowAfterSale(!showAfterSale)}>申请售后</View>
      )}

      {showAfterSale && (
        <View className="card">
          <Input className="input" placeholder="退款金额（分）" value={amount} onInput={(event) => setAmount(event.detail.value)} />
          <Input className="input" placeholder="问题描述" value={reason} onInput={(event) => setReason(event.detail.value)} />
          <View className="btn" onClick={submitAfterSale}>提交售后</View>
        </View>
      )}
    </View>
  )
}
