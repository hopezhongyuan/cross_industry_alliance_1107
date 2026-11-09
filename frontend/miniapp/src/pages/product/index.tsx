import { useLoad, useRouter, useShareAppMessage, showToast } from '@tarojs/taro'
import Taro from '@tarojs/taro'
import { View, Text, Button, Image } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError, type ProductDetail } from '../../api'
import { formatMoney } from '../../format'

export default function ProductDetailPage() {
  const router = useRouter()
  const productId = Number(router.params.id)
  const [detail, setDetail] = useState<ProductDetail | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [selectedSkuId, setSelectedSkuId] = useState<number | null>(null)

  useLoad(() => {
    api
      .product(productId)
      .then((data) => {
        setDetail(data)
        setSelectedSkuId(data.skus?.[0]?.id ?? null)
      })
      .catch((exc) => setError(exc instanceof ApiError ? exc.message : '加载失败'))
  })

  useShareAppMessage(() => {
    // 分享赚积分：WeChat 无可靠成功回调，触发分享即上报
    api.pointShare('PRODUCT', productId).catch(() => { /* ignore */ })
    return {
      title: detail?.title || '精选好物',
      path: `/pages/product/index?id=${productId}`,
    }
  })

  const selectedSku = detail?.skus?.find((sku) => sku.id === selectedSkuId) ?? detail?.skus?.[0]
  const price = selectedSku?.price ?? detail?.price ?? 0

  async function addToCart() {
    if (!detail) return
    setBusy(true)
    try {
      await api.addCart(detail.id, selectedSku?.id ?? null, 1)
      showToast({ title: '已加入购物车', icon: 'success' })
    } catch (exc) {
      showToast({ title: exc instanceof ApiError ? exc.message : '加入失败', icon: 'none' })
    } finally {
      setBusy(false)
    }
  }

  function buyNow() {
    if (!detail) return
    Taro.navigateTo({
      url: `/pages/checkout/index?mode=direct&product_id=${detail.id}${selectedSku ? `&sku_id=${selectedSku.id}` : ''}&quantity=1`,
    })
  }

  return (
    <View className="page" style={{ paddingBottom: '150px' }}>
      {error && <View className="muted" aria-live="polite">{error}</View>}

      <View className="product-hero">
        {detail?.cover_url ? (
          <Image className="hero-cover" src={detail.cover_url} mode="aspectFill" />
        ) : (
          <View className="hero-mark">{detail?.title?.slice(0, 1) ?? '商'}</View>
        )}
        <Text className="eyebrow">{detail?.type === 'SERVICE' ? 'LOCAL SERVICE' : 'LOCAL GOODS'}</Text>
        <Text className="product-name">{detail?.title ?? '—'}</Text>
        <View className="price-row">
          <Text className="price">{formatMoney(price)}</Text>
          {detail?.original_price ? (
            <Text className="muted" style={{ textDecoration: 'line-through' }}>{formatMoney(detail.original_price)}</Text>
          ) : null}
        </View>
        <View style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <Text className="tag">{detail?.type === 'SERVICE' ? '到店服务' : '实物商品'}</Text>
          {detail?.appointment_required ? <Text className="tag">可预约</Text> : null}
          {detail?.refund_policy ? <Text className="tag">{detail.refund_policy}</Text> : null}
        </View>
        {(detail?.skus?.length ?? 0) > 0 ? (
          <View style={{ marginTop: '18px' }}>
            <Text className="field-label">选择规格</Text>
            <View className="sku-row">
              {detail?.skus.map((sku) => (
                <View
                  key={sku.id}
                  className={`sku-chip ${selectedSkuId === sku.id ? 'active' : ''}`}
                  onClick={() => setSelectedSkuId(sku.id)}
                >
                  {sku.sku_code} · {formatMoney(sku.price)}
                </View>
              ))}
            </View>
          </View>
        ) : null}
        <View className="merchant-strip">
          <View className="merchant-mark">{detail?.merchant_name?.slice(0, 1) ?? '店'}</View>
          <View style={{ flex: 1 }}>
            <Text style={{ display: 'block', fontSize: '26px' }}>{detail?.merchant_name || '门店'}</Text>
            <Text className="muted">{detail?.merchant_address || '到店体验'}</Text>
          </View>
          <Text className="muted">›</Text>
        </View>
      </View>

      <View className="card">
        <Text className="eyebrow">DETAILS</Text>
        <Text style={{ display: 'block', marginTop: '10px', lineHeight: '1.8' }}>
          {detail?.description || detail?.subtitle || '到店体验，详情请咨询门店。'}
        </Text>
        <View className="rule-card">
          {detail?.verify_days ? (
            <View className="rule-line"><Text>核销有效期</Text><Text>支付后 {detail.verify_days} 天内</Text></View>
          ) : null}
          <View className="rule-line">
            <Text>预约方式</Text>
            <Text>{detail?.appointment_required ? '下单时选择时段' : '无需预约'}</Text>
          </View>
          <View className="rule-line"><Text>退款规则</Text><Text>{detail?.refund_policy || '按平台售后规则'}</Text></View>
          <View className="rule-line"><Text>门店电话</Text><Text>{detail?.merchant_phone || '—'}</Text></View>
        </View>
      </View>

      {detail?.appointment_required && (
        <View className="card">
          <Text className="eyebrow">APPOINTMENT</Text>
          <View className="section-head" style={{ marginTop: '8px' }}>
            <Text>可预约时段</Text>
            <Text className="muted">下单时选择</Text>
          </View>
          {(detail.slots ?? []).map((slot) => (
            <View key={slot.id} className="row">
              <Text>{slot.slot_date} {slot.start_time}-{slot.end_time}</Text>
              <Text className="muted">余 {slot.remaining}</Text>
            </View>
          ))}
          {!detail.slots?.length && <View className="muted">暂无可预约时段</View>}
        </View>
      )}

      <View className="fixed-bar buy-bar">
        <View style={{ flex: 0.8 }}>
          <Text className="muted">合计</Text>
          <Text className="price" style={{ marginLeft: '8px' }}>{formatMoney(price)}</Text>
        </View>
        <Button className="btn secondary" style={{ flex: 1, marginTop: 0 }} onClick={busy ? undefined : addToCart}>
          加入购物车
        </Button>
        <Button className="btn" style={{ flex: 1, marginTop: 0 }} onClick={buyNow}>立即购买</Button>
      </View>
    </View>
  )
}
