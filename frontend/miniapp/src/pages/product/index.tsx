import { useLoad, useRouter, showToast } from '@tarojs/taro'
import Taro from '@tarojs/taro'
import { View, Text, Button } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError, type ProductDetail } from '../../api'
import { formatMoney } from '../../format'

export default function ProductDetailPage() {
  const router = useRouter()
  const productId = Number(router.params.id)
  const [detail, setDetail] = useState<ProductDetail | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useLoad(() => {
    api
      .product(productId)
      .then(setDetail)
      .catch((exc) => setError(exc instanceof ApiError ? exc.message : '加载失败'))
  })

  function skuId(): number | null {
    return detail?.skus?.[0]?.id ?? null
  }

  async function addToCart() {
    if (!detail) return
    setBusy(true)
    try {
      await api.addCart(detail.id, skuId(), 1)
      showToast({ title: '已加入购物车', icon: 'success' })
    } catch (exc) {
      showToast({ title: exc instanceof ApiError ? exc.message : '加入失败', icon: 'none' })
    } finally {
      setBusy(false)
    }
  }

  function buyNow() {
    if (!detail) return
    const sku = skuId()
    Taro.navigateTo({
      url: `/pages/checkout/index?mode=direct&product_id=${detail.id}${sku ? `&sku_id=${sku}` : ''}&quantity=1`,
    })
  }

  return (
    <View className="page" style={{ paddingBottom: '140px' }}>
      <View className="card" style={{ background: 'linear-gradient(160deg,#efe7da,#ffffff)' }}>
        <Text style={{ fontSize: '52px', fontWeight: 700, color: '#6b4f2a' }}>
          {detail?.title?.slice(0, 1) ?? '商'}
        </Text>
      </View>
      <View className="card">
        <View style={{ display: 'flex', gap: '10px', marginBottom: '12px' }}>
          <Text className="tag">{detail?.type === 'SERVICE' ? '到店服务' : '实物商品'}</Text>
          {detail?.appointment_required && <Text className="tag">可预约</Text>}
          {detail?.refund_policy && <Text className="tag">{detail.refund_policy}</Text>}
        </View>
        <View className="title" style={{ marginBottom: '8px' }}>{detail?.title ?? '—'}</View>
        <View className="price">{formatMoney(detail?.price)}</View>
        <View className="muted" style={{ marginTop: '12px' }}>{detail?.description || detail?.subtitle}</View>
        <View className="rule-card">
          {detail?.verify_days ? (
            <View className="rule-line"><Text>核销有效期</Text><Text>支付后 {detail.verify_days} 天内</Text></View>
          ) : null}
          <View className="rule-line">
            <Text>预约方式</Text>
            <Text>{detail?.appointment_required ? '下单时选择时段' : '无需预约'}</Text>
          </View>
          <View className="rule-line">
            <Text>退款规则</Text>
            <Text>{detail?.refund_policy || '按平台售后规则'}</Text>
          </View>
          <View className="rule-line"><Text>门店地址</Text><Text>{detail?.merchant_address || '—'}</Text></View>
        </View>
      </View>

      {detail?.appointment_required && (
        <View className="card">
          <View className="muted" style={{ marginBottom: '8px' }}>可预约时段（下单时选择）</View>
          {(detail.slots ?? []).map((slot) => (
            <View key={slot.id} className="row">
              <Text>{slot.slot_date} {slot.start_time}-{slot.end_time}</Text>
              <Text className="muted">余 {slot.remaining}</Text>
            </View>
          ))}
          {!detail.slots?.length && <View className="muted">暂无可预约时段</View>}
        </View>
      )}

      {error && <View className="muted" aria-live="polite">{error}</View>}

      <View className="fixed-bar">
        <Button className="btn secondary" style={{ flex: 1, marginTop: 0 }} onClick={busy ? undefined : addToCart}>
          加入购物车
        </Button>
        <Button className="btn" style={{ flex: 1, marginTop: 0 }} onClick={buyNow}>立即购买</Button>
      </View>
    </View>
  )
}
