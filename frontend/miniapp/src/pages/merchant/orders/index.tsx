import { useLoad, showToast } from '@tarojs/taro'
import Taro from '@tarojs/taro'
import { View, Text, Input, Button } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError, type OrderRow } from '../../../api'
import { formatDateTime, formatMoney } from '../../../format'

export default function MerchantOrders() {
  const [items, setItems] = useState<OrderRow[]>([])
  const [status, setStatus] = useState('PENDING_ACCEPT')
  const [error, setError] = useState('')
  const [logistics, setLogistics] = useState('')

  async function load(nextStatus = status) {
    try {
      setStatus(nextStatus)
      setItems(await api.merchantOrders(nextStatus))
      setError('')
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : '加载失败')
    }
  }

  useLoad(() => load('PENDING_ACCEPT'))

  async function accept(id: number) {
    try {
      await api.acceptOrder(id)
      showToast({ title: '已接单', icon: 'success' })
      await load()
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : '操作失败')
    }
  }

  async function reject(id: number) {
    const result = (await Taro.showModal({
      title: '拒绝订单',
      editable: true,
      placeholderText: '请输入拒单原因',
    } as unknown as Parameters<typeof Taro.showModal>[0])) as unknown as { confirm: boolean; content?: string }
    if (!result.confirm) return
    try {
      await api.rejectOrder(id, result.content || '无法履约')
      showToast({ title: '已拒单并退款', icon: 'success' })
      await load()
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : '操作失败')
    }
  }

  async function ship(id: number) {
    try {
      await api.shipOrder(id, logistics, '')
      showToast({ title: '已发货', icon: 'success' })
      await load()
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : '操作失败')
    }
  }

  const tabs = ['PENDING_ACCEPT', 'PENDING_FULFILL', 'FULFILLING', 'COMPLETED']

  return (
    <View className="page">
      <View className="title">订单处理</View>
      <View style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', marginBottom: '16px' }}>
        {tabs.map((tab) => (
          <Button key={tab} className={`chip ${status === tab ? 'active' : ''}`} onClick={() => load(tab)}>
            {tab}
          </Button>
        ))}
      </View>
      {error && <View className="muted" aria-live="polite">{error}</View>}
      {items.map((order) => (
        <View key={order.id} className="card">
          <View className="row"><Text>{order.order_no}</Text><Text className="tag">{order.status}</Text></View>
          <View className="row"><Text className="muted">{formatDateTime(order.created_at)}</Text><Text className="price">{formatMoney(order.payable_amount)}</Text></View>
          {order.status === 'PENDING_ACCEPT' && (
            <View className="row">
              <Button className="btn" style={{ flex: 1, marginRight: '12px', marginTop: 0 }} onClick={() => accept(order.id)}>接单</Button>
              <Button className="btn secondary" style={{ flex: 1, marginTop: 0 }} onClick={() => reject(order.id)}>拒单</Button>
            </View>
          )}
          {order.status === 'PENDING_FULFILL' && (
            <View>
              <Text className="field-label">物流公司（可选）</Text>
              <Input
                className="input"
                name="logistics_company"
                placeholder="请输入物流公司…"
                value={logistics}
                onInput={(event) => setLogistics(event.detail.value)}
              />
              <Button className="btn" style={{ marginTop: 0 }} onClick={() => ship(order.id)}>发货</Button>
            </View>
          )}
          {order.status === 'FULFILLING' && (
            <Button className="btn secondary" style={{ marginTop: 0 }} onClick={() => Taro.navigateTo({ url: '/pages/merchant/verify/index' })}>
              去核销
            </Button>
          )}
        </View>
      ))}
      {!items.length && <View className="muted">当前状态下暂无订单</View>}
    </View>
  )
}
