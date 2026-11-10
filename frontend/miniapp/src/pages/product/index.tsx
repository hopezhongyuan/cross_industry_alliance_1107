import { useLoad, useRouter, useShareAppMessage, showToast } from '@tarojs/taro'
import Taro from '@tarojs/taro'
import { View, Text, Button, Image } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError, type ProductDetail } from '../../api'
import { formatMoney } from '../../format'

const WEEKDAY_LABELS: Record<number, string> = {
  1: '周一',
  2: '周二',
  3: '周三',
  4: '周四',
  5: '周五',
  6: '周六',
  7: '周日',
}

function couponValidityText(detail: ProductDetail): string {
  if (detail.valid_type === 'PERMANENT') return '永久有效'
  if (detail.valid_type === 'RANGE') {
    const from = detail.valid_from ? detail.valid_from.slice(0, 10) : '—'
    const to = detail.valid_to ? detail.valid_to.slice(0, 10) : '—'
    return `${from} 至 ${to}`
  }
  return detail.valid_days ? `支付后 ${detail.valid_days} 天内` : '以门店说明为准'
}

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
          {detail?.type === 'COUPON' ? (
            <View className="rule-line"><Text>卡券有效期</Text><Text>{couponValidityText(detail)}</Text></View>
          ) : detail?.verify_days ? (
            <View className="rule-line"><Text>核销有效期</Text><Text>支付后 {detail.verify_days} 天内</Text></View>
          ) : null}
          {detail?.type === 'COUPON' && (
            <View className="rule-line">
              <Text>可核销次数</Text>
              <Text>{detail?.verify_count ?? 1} 次（每次一个独立核销码）</Text>
            </View>
          )}
          {detail?.type === 'COUPON' && detail?.usable_weekdays?.length ? (
            <View className="rule-line">
              <Text>可用星期</Text>
              <Text>{detail.usable_weekdays.map((d) => WEEKDAY_LABELS[d] ?? d).join('、')}</Text>
            </View>
          ) : null}
          {detail?.type === 'COUPON' && detail?.exclude_holidays ? (
            <View className="rule-line"><Text>节假日</Text><Text>法定节假日不可用，请以门店说明为准</Text></View>
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
