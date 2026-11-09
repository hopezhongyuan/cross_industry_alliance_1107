import { useLoad, showToast } from '@tarojs/taro'
import { View, Text, Button } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError, type Schemas } from '../../api'
import { formatDateTime } from '../../format'

const TABS = [
  { value: '', label: '全部' },
  { value: 'CONSUMPTION', label: '消费' },
  { value: 'SIGNIN', label: '签到' },
  { value: 'SHARE', label: '分享' },
  { value: 'REVIEW', label: '评价' },
]

const BIZ_LABEL: Record<string, string> = {
  CONSUMPTION: '消费返积分',
  SIGNIN: '签到',
  SHARE: '分享',
  REGISTER: '注册',
  REVIEW: '评价',
  ADMIN_ADJUST: '后台调整',
}

export default function PointsPage() {
  const [account, setAccount] = useState<Schemas['PointAccount'] | null>(null)
  const [rules, setRules] = useState<Schemas['PointsConfig'] | null>(null)
  const [items, setItems] = useState<Schemas['PointTransaction'][]>([])
  const [tab, setTab] = useState('')
  const [signedToday, setSignedToday] = useState(false)
  const [error, setError] = useState('')
  const [loadingSignin, setLoadingSignin] = useState(false)

  async function load(nextTab = tab) {
    try {
      setTab(nextTab)
      const [acc, txns] = await Promise.all([api.pointAccount(), api.pointTransactions(nextTab)])
      setAccount(acc)
      setItems(txns.items)
      // 判断今日是否已签到
      const today = new Date().toISOString().slice(0, 10)
      setSignedToday(txns.items.some((t) => t.biz_type === 'SIGNIN' && (t.created_at || '').slice(0, 10) === today))
      setError('')
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : '加载失败')
    }
  }

  useLoad(async () => {
    try {
      setRules(await api.pointRules())
    } catch { /* ignore */ }
    load('')
  })

  async function handleSignin() {
    if (signedToday || loadingSignin) return
    setLoadingSignin(true)
    try {
      const result = await api.pointSignin()
      showToast({ title: `+${result.delta} 积分`, icon: 'success' })
      setSignedToday(true)
      await load()
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : '签到失败')
    } finally {
      setLoadingSignin(false)
    }
  }

  return (
    <View className="page">
      {/* 积分余额卡 */}
      <View style={{
        background: 'linear-gradient(150deg, #232f2a, #6b7a55)',
        borderRadius: 18, padding: 28, marginBottom: 20, color: '#fdf9f0',
      }}>
        <Text style={{ fontSize: 24, opacity: 0.78 }}>我的积分</Text>
        <View style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginTop: 8 }}>
          <Text style={{ fontSize: 60, fontWeight: 700, fontFamily: "'Songti SC', serif" }}>
            {account?.balance ?? 0}
          </Text>
        </View>
        <View style={{ display: 'flex', gap: 24, marginTop: 14, fontSize: 22, opacity: 0.78 }}>
          <Text>累计获得 {account?.total_earned ?? 0}</Text>
          <Text>累计消耗 {account?.total_spent ?? 0}</Text>
        </View>
      </View>

      {/* 签到 */}
      <View className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <View>
          <Text style={{ fontSize: 30, fontWeight: 600 }}>每日签到</Text>
          <View style={{ fontSize: 22, color: '#7b7468', marginTop: 4 }}>
            今日可得 {rules?.signin_points ?? 5} 积分
          </View>
        </View>
        <Button
          className={`btn ${signedToday ? 'secondary' : ''}`}
          style={{ margin: 0 }}
          disabled={signedToday || loadingSignin}
          onClick={handleSignin}
        >
          {signedToday ? '已签到' : loadingSignin ? '签到中…' : '签到'}
        </Button>
      </View>

      {/* 规则说明 */}
      {rules && (
        <View className="card">
          <View className="title" style={{ fontSize: 28, padding: 0, marginBottom: 12 }}>积分规则</View>
          <View style={{ fontSize: 24, color: '#7b7468', lineHeight: 1.9 }}>
            <Text>• 每消费 {rules.consumption_rate} 分（约 {(rules.consumption_rate! / 100).toFixed(2)} 元）获得 1 积分</Text>
            {rules.consumption_max_per_order ? <Text>（单笔上限 {rules.consumption_max_per_order} 积分）</Text> : null}
            {'\n'}
            <Text>• 每日签到 +{rules.signin_points} 积分{'\n'}</Text>
            <Text>• 分享商品/店铺 +{rules.share_points} 积分，每日上限 {rules.share_daily_limit} 次{'\n'}</Text>
            <Text>• 新用户注册 +{rules.register_points} 积分{'\n'}</Text>
            <Text>• 订单评价 +{rules.review_points} 积分</Text>
          </View>
        </View>
      )}

      {/* 明细 */}
      <View className="title" style={{ marginTop: 8 }}>积分明细</View>
      <View className="mch-tabs">
        {TABS.map((t) => (
          <Button key={t.value || 'ALL'} className={`mch-tab ${tab === t.value ? 'active' : ''}`} onClick={() => load(t.value)}>
            {t.label}
          </Button>
        ))}
      </View>

      {error && <View className="muted" style={{ marginBottom: 12 }}>{error}</View>}

      {items.length > 0 ? items.map((t) => (
        <View key={t.id} className="card">
          <View className="row">
            <Text style={{ fontSize: 26 }}>{t.remark || BIZ_LABEL[t.biz_type || ''] || t.biz_type}</Text>
            <Text style={{ fontSize: 30, fontWeight: 600, color: (t.delta ?? 0) >= 0 ? '#2e7d32' : '#c62828' }}>
              {(t.delta ?? 0) >= 0 ? '+' : ''}{t.delta}
            </Text>
          </View>
          <View className="row">
            <Text className="muted">{formatDateTime(t.created_at)}</Text>
            <Text className="muted">余额 {t.balance_after}</Text>
          </View>
        </View>
      )) : (
        <View style={{ textAlign: 'center', padding: 60, color: '#9b917f', fontSize: 26 }}>暂无积分明细</View>
      )}
    </View>
  )
}
