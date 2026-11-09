import { useLoad, useDidShow } from '@tarojs/taro'
import { View, Text, Button } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError, type Schemas } from '../../../api'
import { formatMoney, formatDate } from '../../../format'

const TABS: Array<{ value: 'UNUSED' | 'USED' | 'EXPIRED'; label: string }> = [
  { value: 'UNUSED', label: '可使用' },
  { value: 'USED', label: '已使用' },
  { value: 'EXPIRED', label: '已过期' },
]

export default function MyCoupons() {
  const [tab, setTab] = useState<'UNUSED' | 'USED' | 'EXPIRED'>('UNUSED')
  const [items, setItems] = useState<Schemas['UserCoupon'][]>([])
  const [error, setError] = useState('')

  async function load(status: 'UNUSED' | 'USED' | 'EXPIRED') {
    try {
      setTab(status)
      const list = await api.myCoupons(status)
      setItems(list)
      setError('')
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : '加载失败')
    }
  }

  useLoad(() => load('UNUSED'))
  useDidShow(() => load(tab))

  function scopeLabel(c: Schemas['Coupon']): string {
    if (c.scope_type === 'ALL') return '全场通用'
    if (c.scope_type === 'CATEGORY') return '指定类目'
    return '指定商品'
  }

  return (
    <View className="page">
      <Text className="eyebrow">MY COUPONS</Text>
      <View className="title">我的优惠券</View>

      <View className="mch-tabs">
        {TABS.map((t) => (
          <Button key={t.value} className={`mch-tab ${tab === t.value ? 'active' : ''}`} onClick={() => load(t.value)}>
            {t.label}
          </Button>
        ))}
      </View>

      {error && <View className="muted" style={{ marginBottom: 12 }}>{error}</View>}

      {items.length === 0 ? (
        <View style={{ textAlign: 'center', padding: '80px 0', color: '#9b917f', fontSize: 26 }}>
          {tab === 'UNUSED' ? '暂无可用优惠券，去领券中心看看吧' : '暂无记录'}
        </View>
      ) : (
        items.map((uc) => {
          const c = uc.coupon ?? ({} as Schemas['Coupon'])
          const isPlatform = c.type === 'PLATFORM'
          const isUnused = uc.status === 'UNUSED'
          return (
            <View
              key={uc.id}
              className="card"
              style={{ display: 'flex', padding: 0, overflow: 'hidden', opacity: isUnused ? 1 : 0.55 }}
            >
              <View
                style={{
                  width: '200px',
                  background: isPlatform ? 'linear-gradient(135deg, #2e7d32, #66bb6a)' : 'linear-gradient(135deg, #d9552f, #ff8a65)',
                  color: '#fff',
                  padding: '24px 16px',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'center',
                  alignItems: 'center',
                }}
              >
                <Text style={{ fontSize: 22, opacity: 0.85 }}>¥</Text>
                <Text style={{ fontSize: 52, fontWeight: 700, lineHeight: 1.1 }}>{(c.face_value ?? 0) / 100}</Text>
                <Text style={{ fontSize: 22, opacity: 0.9, marginTop: 4 }}>
                  {(c.min_amount ?? 0) > 0 ? `满${(c.min_amount! / 100).toFixed(0)}可用` : '无门槛'}
                </Text>
              </View>
              <View style={{ flex: 1, padding: '20px 20px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                <View>
                  <Text style={{ fontSize: 28, fontWeight: 600 }}>{c.name}</Text>
                  <Text className="muted" style={{ display: 'block', marginTop: 6, fontSize: 24 }}>
                    {scopeLabel(c)} · {c.merchant_name || '平台'}
                  </Text>
                  <Text className="muted" style={{ display: 'block', marginTop: 4, fontSize: 22 }}>
                    {isUnused ? `有效期至 ${formatDate(c.valid_to)}` : uc.order_no ? `订单 ${uc.order_no}` : formatDate(uc.used_at)}
                  </Text>
                </View>
                <View style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 8 }}>
                  <Text
                    style={{
                      fontSize: 22,
                      padding: '2px 10px',
                      borderRadius: 4,
                      background: isPlatform ? '#e8f5e9' : '#fff3e0',
                      color: isPlatform ? '#2e7d32' : '#ef6c00',
                    }}
                  >
                    {isPlatform ? '平台券' : '商户券'}
                  </Text>
                </View>
              </View>
            </View>
          )
        })
      )}
    </View>
  )
}
