import { useLoad, showToast } from '@tarojs/taro'
import { View, Text, Input, Button } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError, type Schemas } from '../../../api'
import { formatDate, formatMoney } from '../../../format'

export default function MerchantStatements() {
  const [account, setAccount] = useState<{
    pending_balance: number
    frozen_balance: number
    available_balance: number
    withdrawing_balance: number
  } | null>(null)
  const [items, setItems] = useState<Schemas['StatementItem'][]>([])
  const [status, setStatus] = useState('')
  const [amount, setAmount] = useState('')
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

  useLoad(() => load(''))

  async function withdraw() {
    const fen = Number(amount)
    if (!fen) {
      setError('请输入提现金额（分）')
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
      <View className="title">账单与提现</View>
      {account && (
        <View className="card">
          <View className="row"><Text>待结算</Text><Text>{formatMoney(account.pending_balance)}</Text></View>
          <View className="row"><Text>冻结</Text><Text>{formatMoney(account.frozen_balance)}</Text></View>
          <View className="row"><Text>可提现</Text><Text className="price">{formatMoney(account.available_balance)}</Text></View>
          <View className="row"><Text>提现中</Text><Text>{formatMoney(account.withdrawing_balance)}</Text></View>
          <Text className="field-label">提现金额（分）</Text>
          <Input
            className="input"
            name="withdraw_amount"
            type="number"
            placeholder="请输入提现金额…"
            value={amount}
            onInput={(event) => setAmount(event.detail.value)}
          />
          <Button className="btn" style={{ marginTop: 0 }} onClick={withdraw}>申请提现</Button>
        </View>
      )}
      {error && <View className="muted" aria-live="polite">{error}</View>}
      <View style={{ display: 'flex', gap: '12px', marginBottom: '16px' }}>
        {['', 'PENDING', 'FROZEN', 'SETTLED'].map((tab) => (
          <Button key={tab || 'ALL'} className={`chip ${status === tab ? 'active' : ''}`} onClick={() => load(tab)}>
            {tab || '全部'}
          </Button>
        ))}
      </View>
      {items.map((item) => (
        <View key={`${item.order_no}-${item.due_at}`} className="card">
          <View className="row"><Text>{item.order_no}</Text><Text className="tag">{item.status}</Text></View>
          <View className="row"><Text className="muted">应结</Text><Text className="price">{formatMoney(item.net_amount)}</Text></View>
          <View className="muted">完成 {formatDate(item.order_completed_at)} · 到期 {formatDate(item.due_at)}</View>
        </View>
      ))}
      {!items.length && <View className="muted">暂无账单</View>}
    </View>
  )
}
