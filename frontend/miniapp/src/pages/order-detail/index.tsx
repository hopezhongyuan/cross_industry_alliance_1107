import { useLoad, useRouter, showToast } from '@tarojs/taro'
import { View, Text, Input, Button } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError, type OrderRow } from '../../api'
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

export default function OrderDetail() {
  const router = useRouter()
  const orderId = Number(router.params.id)
  const [order, setOrder] = useState<OrderRow | null>(null)
  const [error, setError] = useState('')
  const [showAfterSale, setShowAfterSale] = useState(false)
  const [showReview, setShowReview] = useState(false)
  const [amount, setAmount] = useState('')
  const [reason, setReason] = useState('')
  const [score, setScore] = useState(5)
  const [reviewText, setReviewText] = useState('')

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

  async function action(task: () => Promise<unknown>, success: string) {
    try {
      await task()
      showToast({ title: success, icon: 'success' })
      await load()
    } catch (exc) {
      setError(exc instanceof ApiError ? `${exc.code}：${exc.message}` : '操作失败')
    }
  }

  async function submitAfterSale() {
    const fen = Number(amount)
    if (!fen) {
      setError('请输入退款金额（分）')
      return
    }
    await action(
      () =>
        api.applyAfterSale({
          order_id: orderId,
          type: 'REFUND_ONLY',
          reason_code: 'SERVICE_ISSUE',
          request_amount: fen,
          description: reason,
        }),
      '售后已提交',
    )
    setShowAfterSale(false)
  }

  async function submitReview() {
    await action(() => api.review(orderId, score, reviewText), '评价已提交')
    setShowReview(false)
  }

  const showCode = order && ['FULFILLING', 'COMPLETED', 'AFTER_SALE'].includes(order.status)
  const codes = order?.verify_codes ?? []
  const steps = order?.timeline ?? order?.status_logs ?? []

  return (
    <View className="page">
      <View className="title">订单详情</View>
      {error && <View className="muted" aria-live="polite">{error}</View>}
      {order && (
        <View className="card">
          <View className="row">
            <Text className="muted">ORDER {order.order_no}</Text>
            <Text className="tag">{statusLabel[order.status] ?? order.status}</Text>
          </View>
          <View className="row"><Text>商品金额</Text><Text className="price">{formatMoney(order.payable_amount)}</Text></View>
          <View className="row"><Text>已退款</Text><Text>{formatMoney(order.refunded_amount)}</Text></View>
          {order.appointment && (
            <View className="row">
              <Text>预约时段</Text>
              <Text>{order.appointment.slot_date} {order.appointment.start_time}</Text>
            </View>
          )}
          {order.items?.map((item) => (
            <View key={item.id} className="row">
              <Text className="card-title">{item.title} × {item.quantity}</Text>
              <Text>{formatMoney(item.amount)}</Text>
            </View>
          ))}
        </View>
      )}

      {showCode && (
        <View className="card">
          <View className="muted" style={{ marginBottom: '8px' }}>核销凭证</View>
          {codes.length ? (
            codes.map((code) => (
              <View key={code.code} className="row">
                <Text style={{ fontFamily: 'monospace', fontSize: '32px', letterSpacing: '4px' }}>{code.code}</Text>
                <Text className="tag">{code.status}</Text>
              </View>
            ))
          ) : (
            <View className="muted">商户接单后生成核销码</View>
          )}
          <View className="muted">请到店出示核销码，由商户扫码核销</View>
        </View>
      )}

      {steps.length > 0 && (
        <View className="card">
          <View className="muted" style={{ marginBottom: '8px' }}>订单进度</View>
          {steps.map((item, index) => (
            <View key={`${item.event}-${index}`} className="timeline-item done">
              <View className="dot" />
              <View>
                <Text style={{ display: 'block' }}>{item.event}</Text>
                <Text className="muted">{formatDateTime(item.created_at)} · {item.operator_type}</Text>
              </View>
            </View>
          ))}
        </View>
      )}

      {order?.status === 'FULFILLING' && (
        <Button className="btn" onClick={() => action(() => api.confirmOrder(orderId), '已确认收货')}>确认收货</Button>
      )}
      {order?.status === 'PENDING_ACCEPT' && (
        <Button className="btn secondary" onClick={() => action(() => api.cancelOrder(orderId), '已取消')}>取消订单</Button>
      )}
      {order?.status === 'COMPLETED' && (
        <View style={{ display: 'flex', gap: '12px' }}>
          <Button className="btn secondary" style={{ flex: 1 }} onClick={() => setShowReview(!showReview)}>评价服务</Button>
          <Button className="btn secondary" style={{ flex: 1 }} onClick={() => setShowAfterSale(!showAfterSale)}>申请售后</Button>
        </View>
      )}

      {showReview && (
        <View className="card">
          <Text className="field-label">评分（1-5）</Text>
          <Input
            className="input"
            name="score"
            type="number"
            value={String(score)}
            onInput={(event) => setScore(Number(event.detail.value) || 5)}
          />
          <Text className="field-label">评价内容</Text>
          <Input
            className="input"
            name="review_content"
            placeholder="请输入评价内容（可选）…"
            value={reviewText}
            onInput={(event) => setReviewText(event.detail.value)}
          />
          <Button className="btn" onClick={submitReview}>提交评价</Button>
        </View>
      )}

      {showAfterSale && (
        <View className="card">
          <Text className="field-label">退款金额（分）</Text>
          <Input
            className="input"
            name="request_amount"
            type="number"
            placeholder="请输入退款金额…"
            value={amount}
            onInput={(event) => setAmount(event.detail.value)}
          />
          <Text className="field-label">问题描述</Text>
          <Input
            className="input"
            name="description"
            placeholder="请描述遇到的问题…"
            value={reason}
            onInput={(event) => setReason(event.detail.value)}
          />
          <Button className="btn" onClick={submitAfterSale}>提交售后</Button>
        </View>
      )}
    </View>
  )
}
