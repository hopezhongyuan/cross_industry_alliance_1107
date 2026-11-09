import { useLoad, useRouter, showToast } from '@tarojs/taro'
import Taro from '@tarojs/taro'
import { View, Text, Button } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError, type Schemas } from '../../api'
import { formatMoney, formatDate } from '../../format'

export default function CouponCenter() {
  const router = useRouter()
  const merchantId = router.params.merchant_id ? Number(router.params.merchant_id) : undefined
  const [coupons, setCoupons] = useState<Schemas['Coupon'][]>([])
  const [claimed, setClaimed] = useState<Set<number>>(new Set())
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function load() {
    try {
      const list = await api.couponCenter(merchantId)
      setCoupons(list)
      setError('')
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : '加载失败')
    }
  }

  useLoad(() => {
    load()
  })

  async function handleClaim(coupon: Schemas['Coupon']) {
    if (!coupon.id || loading) return
    setLoading(true)
    try {
      await api.claimCoupon(coupon.id)
      setClaimed((prev) => new Set(prev).add(coupon.id!))
      showToast({ title: '领取成功', icon: 'success' })
    } catch (exc) {
      const msg = exc instanceof ApiError ? exc.message : '领取失败'
      showToast({ title: msg, icon: 'none' })
    } finally {
      setLoading(false)
    }
  }

  function scopeLabel(c: Schemas['Coupon']): string {
    if (c.scope_type === 'ALL') return '全场通用'
    if (c.scope_type === 'CATEGORY') return '指定类目'
    return '指定商品'
  }

  return (
    <View className="page">
      <Text className="eyebrow">COUPON CENTER</Text>
      <View className="title">领券中心</View>
      {merchantId ? <Text className="muted">当前店铺可用券</Text> : <Text className="muted">平台券与参与商户券</Text>}

      {error && <View className="muted" style={{ marginTop: 12 }}>{error}</View>}

      {coupons.length === 0 ? (
        <View style={{ textAlign: 'center', padding: '80px 0', color: '#9b917f', fontSize: 26 }}>
          暂无可领取优惠券
        </View>
      ) : (
        coupons.map((c) => {
          const isPlatform = c.type === 'PLATFORM'
          const isClaimed = claimed.has(c.id!)
          return (
            <View key={c.id} className="card" style={{ display: 'flex', padding: 0, overflow: 'hidden' }}>
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
                <Text style={{ fontSize: 52, fontWeight: 700, lineHeight: 1.1 }}>
                  {(c.face_value ?? 0) / 100}
                </Text>
                <Text style={{ fontSize: 22, opacity: 0.9, marginTop: 4 }}>
                  {(c.min_amount ?? 0) > 0 ? `满${(c.min_amount! / 100).toFixed(0)}可用` : '无门槛'}
                </Text>
              </View>
              <View style={{ flex: 1, padding: '20px 20px 20px 24px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                <View>
                  <View style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Text style={{ fontSize: 28, fontWeight: 600 }}>{c.name}</Text>
                    <Text
                      style={{
                        fontSize: 20,
                        padding: '2px 8px',
                        borderRadius: 4,
                        background: isPlatform ? '#e8f5e9' : '#fff3e0',
                        color: isPlatform ? '#2e7d32' : '#ef6c00',
                      }}
                    >
                      {isPlatform ? '平台券' : '商户券'}
                    </Text>
                  </View>
                  <Text className="muted" style={{ display: 'block', marginTop: 6, fontSize: 24 }}>
                    {scopeLabel(c)} · {c.merchant_name || '平台'}
                  </Text>
                  <Text className="muted" style={{ display: 'block', marginTop: 4, fontSize: 22 }}>
                    有效期 {formatDate(c.valid_from)} ~ {formatDate(c.valid_to)}
                  </Text>
                  {c.remaining_stock !== null && c.remaining_stock !== undefined && (
                    <Text className="muted" style={{ display: 'block', marginTop: 2, fontSize: 22 }}>
                      剩余 {c.remaining_stock} 张
                    </Text>
                  )}
                </View>
                <View style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 12 }}>
                  <Button
                    className="btn"
                    style={{ margin: 0, width: '160px' }}
                    disabled={isClaimed || loading}
                    onClick={() => handleClaim(c)}
                  >
                    {isClaimed ? '已领取' : '立即领取'}
                  </Button>
                </View>
              </View>
            </View>
          )
        })
      )}

      <View style={{ height: 40 }} />
      <Button className="btn secondary" onClick={() => Taro.navigateTo({ url: '/pages/me/coupons/index' })}>
        查看我的优惠券
      </Button>
    </View>
  )
}
