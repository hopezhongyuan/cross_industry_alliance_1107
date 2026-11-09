import { useLoad, showToast } from '@tarojs/taro'
import Taro from '@tarojs/taro'
import { View, Text, Button, Input } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError, type Schemas } from '../../../api'
import { formatDateTime, formatMoney } from '../../../format'
import MerchantHeader from '../../../components/merchant/MerchantHeader'
import StatusBadge from '../../../components/merchant/StatusBadge'
import EmptyState from '../../../components/merchant/EmptyState'

const TABS = [
  { value: 'PENDING', label: '待处理', param: 'merchant_decision' },
  { value: '', label: '全部', param: 'none' },
  { value: 'AGREED', label: '已同意', param: 'merchant_decision' },
  { value: 'REJECTED', label: '已拒绝', param: 'merchant_decision' },
]

type Row = Schemas['MerchantAfterSaleRow']

export default function MerchantAfterSales() {
  const [items, setItems] = useState<Row[]>([])
  const [decision, setDecision] = useState('PENDING')
  const [profile, setProfile] = useState<Schemas['MerchantProfile'] | null>(null)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState<number | null>(null)

  async function load(nextDecision = decision) {
    try {
      setDecision(nextDecision)
      const params = nextDecision ? { merchant_decision: nextDecision } : {}
      const result = await api.merchantAfterSales(params)
      setItems(result.items)
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
    load('PENDING')
  })

  async function decide(id: number | undefined, decision: 'AGREE' | 'REJECT') {
    if (!id) return
    let reason = ''
    if (decision === 'REJECT') {
      const result = (await Taro.showModal({
        title: '拒绝售后',
        editable: true,
        placeholderText: '请输入拒绝原因',
      } as unknown as Parameters<typeof Taro.showModal>[0])) as unknown as { confirm: boolean; content?: string }
      if (!result.confirm) return
      reason = result.content || '不符合售后条件'
    }
    setBusyId(id)
    try {
      await api.decideAfterSale(id, decision, reason)
      showToast({ title: decision === 'AGREE' ? '已同意' : '已拒绝', icon: 'success' })
      await load()
    } catch (exc) {
      setError(exc instanceof ApiError ? `${exc.code}：${exc.message}` : '操作失败')
    } finally {
      setBusyId(null)
    }
  }

  return (
    <View className="page">
      {profile && <MerchantHeader name={profile.name || ''} shortName={profile.short_name} logoUrl={profile.logo_url} showSettings={false} />}
      <View className="title">售后审核</View>

      <View className="mch-tabs">
        {TABS.map((tab) => (
          <Button
            key={tab.value || 'ALL'}
            className={`mch-tab ${decision === tab.value ? 'active' : ''}`}
            onClick={() => load(tab.value)}
          >
            {tab.label}
          </Button>
        ))}
      </View>

      {error && <View className="muted" style={{ marginBottom: 12 }}>{error}</View>}

      {items.length > 0 ? items.map((item) => (
        <View key={item.id} className="card">
          <View className="row">
            <Text style={{ fontSize: '26px' }}>{item.after_sale_no}</Text>
            <StatusBadge kind="aftersale" status={item.status} />
          </View>
          <View className="row">
            <Text className="muted">订单 {item.order_no}</Text>
            <Text className="muted">{item.type_label}</Text>
          </View>
          <View className="row">
            <Text className="muted">申请金额</Text>
            <Text className="price">{formatMoney(item.request_amount)}</Text>
          </View>
          {item.deadline_at && (
            <Text className="muted">处理截止：{formatDateTime(item.deadline_at)}</Text>
          )}
          {item.merchant_decision === 'PENDING' && (
            <View className="mch-actions">
              <Button className="btn" disabled={busyId === item.id} onClick={() => decide(item.id, 'AGREE')}>同意</Button>
              <Button className="btn secondary" disabled={busyId === item.id} onClick={() => decide(item.id, 'REJECT')}>拒绝</Button>
            </View>
          )}
          {item.merchant_decision !== 'PENDING' && (
            <Text className="muted">处理结果：{item.merchant_decision_label}{item.merchant_reason ? `（${item.merchant_reason}）` : ''}</Text>
          )}
        </View>
      )) : (
        <EmptyState text="暂无售后申请" icon="↩️" />
      )}
    </View>
  )
}
