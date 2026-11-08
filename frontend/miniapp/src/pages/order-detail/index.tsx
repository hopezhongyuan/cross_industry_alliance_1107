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
      {error && <View className="muted" aria-live="polite">{error}</View>}
      {order && (
        <View>
          <View className="status-hero">
            <Text className="eyebrow" style={{ color: 'rgba(253,249,240,0.7)' }}>ORDER STATUS</Text>
            <Text className="title" style={{ color: '#fdf9f0', margin: '10px 0 6px' }}>
              {statusLabel[order.status] ?? order.status}
            </Text>
            <Text style={{ display: 'block', color: 'rgba(253,249,240,0.7)', fontSize: '22px' }}>
              {order.order_no}
            </Text>
            <View className="row" style={{ paddingBottom: 0 }}>
              <Text style={{ color: 'rgba(253,249,240,0.7)' }}>实付金额</Text>
              <Text className="price">{formatMoney(order.payable_amount)}</Text>
            </View>
            {order.appointment ? (
              <Text style={{ display: 'block', color: 'rgba(253,249,240,0.7)', marginTop: '8px' }}>
                预约 {order.appointment.slot_date} {order.appointment.start_time}
              </Text>
            ) : null}
          </View>

          {showCode && (
            <View className="code-card">
              <Text className="eyebrow">VERIFY CODE</Text>
              {codes.length ? (
                codes.map((code) => (
                  <View key={code.code}>
                    <Text className="code-value">{code.code}</Text>
                    <Text className="tag">{code.status}</Text>
                  </View>
                ))
              ) : (
                <Text className="muted">商户接单后生成核销码</Text>
              )}
              <Text className="muted" style={{ display: 'block', marginTop: '10px' }}>
                请到店出示核销码，由商户扫码核销
              </Text>
            </View>
          )}

          <View className="card">
            <View className="section-head"><Text>商品明细</Text><Text className="muted">共 {order.items?.length ?? 0} 件</Text></View>
            {(order.items ?? []).map((item) => (
              <View key={item.id} className="order-item">
                <View className="order-thumb">{item.title?.slice(0, 1)}</View>
                <View style={{ flex: 1 }}>
                  <Text style={{ display: 'block', fontSize: '26px' }}>{item.title}</Text>
                  <Text className="muted">× {item.quantity}</Text>
                </View>
                <Text>{formatMoney(item.amount)}</Text>
              </View>
            ))}
            <View className="summary-row" style={{ marginTop: '12px' }}>
              <Text>已退款</Text><Text>{formatMoney(order.refunded_amount)}</Text>
            </View>
          </View>

          {steps.length > 0 && (
            <View className="card">
              <View className="section-head"><Text>订单进度</Text><Text className="muted">实时</Text></View>
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

          {order.status === 'FULFILLING' && (
            <Button className="btn" onClick={() => action(() => api.confirmOrder(orderId), '已确认收货')}>确认收货</Button>
          )}
          {order.status === 'PENDING_ACCEPT' && (
            <Button className="btn secondary" onClick={() => action(() => api.cancelOrder(orderId), '已取消')}>取消订单</Button>
          )}
          {order.status === 'COMPLETED' && (
            <View style={{ display: 'flex', gap: '12px' }}>
              <Button className="btn secondary" style={{ flex: 1 }} onClick={() => setShowReview(!showReview)}>评价服务</Button>
              <Button className="btn secondary" style={{ flex: 1 }} onClick={() => setShowAfterSale(!showAfterSale)}>申请售后</Button>
            </View>
          )}
        </View>
      )}

      {showReview && (
        <View className="card">
          <View className="section-head"><Text>评价服务</Text><Text className="muted">1–5 分</Text></View>
          <Input className="input" name="score" type="number" value={String(score)} onInput={(event) => setScore(Number(event.detail.value) || 5)} />
          <Input className="input" name="review_content" placeholder="说说这次体验…" value={reviewText} onInput={(event) => setReviewText(event.detail.value)} />
          <Button className="btn" onClick={submitReview}>提交评价</Button>
        </View>
      )}

      {showAfterSale && (
        <View className="card">
          <View className="section-head"><Text>申请售后</Text><Text className="muted">按分填写</Text></View>
          <Input className="input" name="request_amount" type="number" placeholder="退款金额（分）…" value={amount} onInput={(event) => setAmount(event.detail.value)} />
          <Input className="input" name="description" placeholder="请描述遇到的问题…" value={reason} onInput={(event) => setReason(event.detail.value)} />
          <Button className="btn" onClick={submitAfterSale}>提交售后</Button>
        </View>
      )}
    </View>
  )
}
