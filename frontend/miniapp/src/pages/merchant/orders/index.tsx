import { useLoad, showToast } from '@tarojs/taro'
import Taro from '@tarojs/taro'
import { View, Text, Input, Button } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError, type OrderRow, type Schemas } from '../../../api'
import { formatDateTime, formatMoney } from '../../../format'
import MerchantHeader from '../../../components/merchant/MerchantHeader'
import StatusBadge from '../../../components/merchant/StatusBadge'
import EmptyState from '../../../components/merchant/EmptyState'

const TABS = [
  { value: 'PENDING_ACCEPT', label: '待接单' },
  { value: 'PENDING_FULFILL', label: '待发货' },
  { value: 'FULFILLING', label: '履约中' },
  { value: 'COMPLETED', label: '已完成' },
  { value: '', label: '全部' },
]

export default function MerchantOrders() {
  const [items, setItems] = useState<OrderRow[]>([])
  const [status, setStatus] = useState('PENDING_ACCEPT')
  const [profile, setProfile] = useState<Schemas['MerchantProfile'] | null>(null)
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

  useLoad(async () => {
    try {
      const p = await api.profile()
      setProfile(p)
    } catch { /* ignore */ }
    load('PENDING_ACCEPT')
  })

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

  return (
    <View className="page">
      {profile && <MerchantHeader name={profile.name || ''} shortName={profile.short_name} logoUrl={profile.logo_url} showSettings={false} />}
      <View className="title">订单列表</View>

      <View className="mch-tabs">
        {TABS.map((tab) => (
          <Button
            key={tab.value || 'ALL'}
            className={`mch-tab ${status === tab.value ? 'active' : ''}`}
            onClick={() => load(tab.value)}
          >
            {tab.label}
          </Button>
        ))}
      </View>

      {error && <View className="muted" style={{ marginBottom: 12 }}>{error}</View>}

      {items.length > 0 ? items.map((order) => (
        <View key={order.id} className="card">
          <View className="row">
            <Text style={{ fontSize: '26px' }}>{order.order_no}</Text>
            <StatusBadge kind="order" status={order.status} />
          </View>
          {order.items && order.items.length > 0 && (
            <Text className="muted">{order.items.map((i) => i.title).join('、')}</Text>
          )}
          <View className="row">
            <Text className="muted">{formatDateTime(order.created_at)}</Text>
            <Text className="price">{formatMoney(order.payable_amount)}</Text>
          </View>
          {order.status === 'PENDING_ACCEPT' && (
            <View className="mch-actions">
              <Button className="btn" onClick={() => accept(order.id)}>接单</Button>
              <Button className="btn secondary" onClick={() => reject(order.id)}>拒单</Button>
            </View>
          )}
          {order.status === 'PENDING_FULFILL' && (
            <View>
              <Text className="mch-field-label">物流公司（可选）</Text>
              <Input
                className="mch-input"
                placeholder="请输入物流公司…"
                value={logistics}
                onInput={(e) => setLogistics(e.detail.value)}
              />
              <Button className="btn" style={{ marginTop: 12 }} onClick={() => ship(order.id)}>发货</Button>
            </View>
          )}
          {order.status === 'FULFILLING' && (
            <Button className="btn secondary" style={{ marginTop: 0 }} onClick={() => Taro.navigateTo({ url: '/pages/merchant/verify/index' })}>
              去核销
            </Button>
          )}
          <Button
            className="chip"
            style={{ marginTop: 12 }}
            onClick={() => Taro.navigateTo({ url: `/pages/merchant/order-detail/index?id=${order.id}` })}
          >
            分账明细
          </Button>
        </View>
      )) : (
        <EmptyState text="当前状态下暂无订单" icon="📋" />
      )}
    </View>
  )
}
