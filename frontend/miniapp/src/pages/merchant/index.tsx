import { useLoad, navigateTo } from '@tarojs/taro'
import { View, Text, Button } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError, type OrderRow, type Schemas } from '../../api'
import { formatMoney } from '../../format'
import MerchantHeader from '../../components/merchant/MerchantHeader'
import MetricGrid from '../../components/merchant/MetricGrid'
import MetricCard from '../../components/merchant/MetricCard'
import QuickActions from '../../components/merchant/QuickActions'
import QuickAction from '../../components/merchant/QuickAction'
import SectionTitle from '../../components/merchant/SectionTitle'
import StatusBadge from '../../components/merchant/StatusBadge'
import EmptyState from '../../components/merchant/EmptyState'

export default function MerchantHome() {
  const [profile, setProfile] = useState<Schemas['MerchantProfile'] | null>(null)
  const [dash, setDash] = useState<Schemas['MerchantDashboard'] | null>(null)
  const [orders, setOrders] = useState<OrderRow[]>([])
  const [error, setError] = useState('')

  async function load() {
    try {
      const [p, d, o] = await Promise.all([
        api.profile(),
        api.dashboard(),
        api.merchantOrders('PENDING_ACCEPT'),
      ])
      setProfile(p)
      setDash(d)
      setOrders(o)
      setError('')
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : '加载失败')
    }
  }

  useLoad(() => {
    load()
  })

  return (
    <View className="page">
      {profile && (
        <MerchantHeader
          name={profile.name || ''}
          shortName={profile.short_name}
          logoUrl={profile.logo_url}
          statusLabel={profile.status_label}
        />
      )}

      {dash && (
        <MetricGrid>
          <MetricCard value={dash.today_orders ?? 0} label="今日订单" to="/pages/merchant/orders/index" />
          <MetricCard value={formatMoney(dash.today_sales_amount ?? 0)} label="今日销售额" accent="#d9552f" to="/pages/merchant/orders/index" />
          <MetricCard value={dash.pending_orders ?? 0} label="待处理" accent="#ef6c00" to="/pages/merchant/orders/index" />
          <MetricCard value={formatMoney(dash.available_balance ?? 0)} label="可提现余额" accent="#2e7d32" to="/pages/merchant/account/index" />
        </MetricGrid>
      )}

      <QuickActions>
        <QuickAction icon="🎫" label="核销" to="/pages/merchant/verify/index" bg="#e8f5e9" color="#2e7d32" />
        <QuickAction
          icon="📦"
          label="商品管理"
          to="/pages/merchant/products/index"
          bg="#fff3e0"
          color="#ef6c00"
          badge={dash?.pending_products}
        />
        <QuickAction
          icon="📋"
          label="订单列表"
          to="/pages/merchant/orders/index"
          bg="#e3f2fd"
          color="#1565c0"
          badge={dash?.pending_orders}
        />
        <QuickAction
          icon="↩️"
          label="售后审核"
          to="/pages/merchant/after-sales/index"
          bg="#fdecea"
          color="#c62828"
          badge={dash?.pending_after_sales}
        />
        <QuickAction icon="💰" label="我的账户" to="/pages/merchant/account/index" bg="#f3e5f5" color="#6a1b9a" />
        <QuickAction icon="⚙️" label="设置" to="/pages/merchant/settings/index" bg="#f1eadc" color="#5d4037" />
      </QuickActions>

      <SectionTitle title="待处理订单" moreTo="/pages/merchant/orders/index" />
      {error && <View className="muted" style={{ marginBottom: 12 }}>{error}</View>}
      {orders.length > 0 ? (
        orders.map((order) => (
          <View key={order.id} className="card">
            <View className="row">
              <Text style={{ fontSize: '26px' }}>{order.order_no}</Text>
              <StatusBadge kind="order" status={order.status} />
            </View>
            <View className="row">
              <Text className="muted">{order.created_at}</Text>
              <Text className="price">{formatMoney(order.payable_amount)}</Text>
            </View>
            <View className="mch-actions">
              <Button className="btn" onClick={() => navigateTo({ url: '/pages/merchant/orders/index' })}>去处理</Button>
            </View>
          </View>
        ))
      ) : (
        <EmptyState text="暂无待处理订单" icon="✅" />
      )}
    </View>
  )
}
