import { useLoad, showToast } from '@tarojs/taro'
import { View, Text, Input, Button } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError, type Schemas } from '../../../api'
import { formatDate, formatMoney } from '../../../format'
import MerchantHeader from '../../../components/merchant/MerchantHeader'
import StatusBadge from '../../../components/merchant/StatusBadge'
import EmptyState from '../../../components/merchant/EmptyState'

const TABS = [
  { value: '', label: '全部' },
  { value: 'PENDING', label: '待结算' },
  { value: 'FROZEN', label: '冻结' },
  { value: 'SETTLED', label: '已结算' },
]

export default function MerchantAccount() {
  const [account, setAccount] = useState<{
    pending_balance: number
    frozen_balance: number
    available_balance: number
    withdrawing_balance: number
  } | null>(null)
  const [items, setItems] = useState<Schemas['StatementItem'][]>([])
  const [status, setStatus] = useState('')
  const [amount, setAmount] = useState('')
  const [profile, setProfile] = useState<Schemas['MerchantProfile'] | null>(null)
  const [error, setError] = useState('')

  async function load(nextStatus = status) {
    try {
      setStatus(nextStatus)
      const [summary, statements] = await Promise.all([api.account(), api.statements(nextStatus)])
      setAccount(summary)
      setItems(statements.items)
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
    load('')
  })

  async function withdraw() {
    const fen = Number(amount)
    if (!fen || fen <= 0) {
      setError('请输入提现金额（分）')
      return
    }
    if (account && fen > account.available_balance) {
      setError('提现金额超过可提现余额')
      return
    }
    try {
      await api.withdraw(fen)
      showToast({ title: '提现已申请', icon: 'success' })
      setAmount('')
      await load()
    } catch (exc) {
      setError(exc instanceof ApiError ? `${exc.code}：${exc.message}` : '提现失败')
    }
  }

  return (
    <View className="page">
      {profile && <MerchantHeader name={profile.name || ''} shortName={profile.short_name} logoUrl={profile.logo_url} showSettings={false} />}
      <View className="title">我的账户</View>

      {account && (
        <View className="card">
          <View className="mch-balance-grid">
            <View className="mch-balance-item">
              <Text className="mch-balance-label">待结算</Text>
              <Text className="mch-balance-value">{formatMoney(account.pending_balance)}</Text>
            </View>
            <View className="mch-balance-item">
              <Text className="mch-balance-label">冻结</Text>
              <Text className="mch-balance-value">{formatMoney(account.frozen_balance)}</Text>
            </View>
            <View className="mch-balance-item highlight">
              <Text className="mch-balance-label">可提现</Text>
              <Text className="mch-balance-value">{formatMoney(account.available_balance)}</Text>
            </View>
            <View className="mch-balance-item">
              <Text className="mch-balance-label">提现中</Text>
              <Text className="mch-balance-value">{formatMoney(account.withdrawing_balance)}</Text>
            </View>
          </View>
          <Text className="mch-field-label">提现金额（分）</Text>
          <Input
            className="mch-input"
            type="number"
            placeholder="请输入提现金额…"
            value={amount}
            onInput={(e) => setAmount(e.detail.value)}
          />
          <Button className="btn" style={{ marginTop: 12 }} onClick={withdraw}>申请提现</Button>
        </View>
      )}

      {error && <View className="muted" style={{ margin: '12px 0' }}>{error}</View>}

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

      {items.length > 0 ? items.map((item) => (
        <View key={`${item.order_no}-${item.due_at}`} className="card">
          <View className="row">
            <Text style={{ fontSize: '26px' }}>{item.order_no}</Text>
            <StatusBadge kind="statement" status={item.status} />
          </View>
          <View className="row">
            <Text className="muted">应结</Text>
            <Text className="price">{formatMoney(item.net_amount)}</Text>
          </View>
          <Text className="muted">完成 {formatDate(item.order_completed_at)} · 到期 {formatDate(item.due_at)}</Text>
        </View>
      )) : (
        <EmptyState text="暂无账单" icon="💰" />
      )}
    </View>
  )
}
