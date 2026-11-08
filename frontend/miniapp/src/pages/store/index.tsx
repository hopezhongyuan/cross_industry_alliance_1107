import Taro, { useLoad, useRouter } from '@tarojs/taro'
import { View, Text, Image, Button } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError, type ProductRow, type StoreRow } from '../../api'
import { formatMoney } from '../../format'

export default function StoreDetail() {
  const router = useRouter()
  const storeId = Number(router.params.id)
  const [store, setStore] = useState<StoreRow | null>(null)
  const [products, setProducts] = useState<ProductRow[]>([])
  const [error, setError] = useState('')

  useLoad(async () => {
    try {
      const detail = await api.store(storeId)
      setStore(detail)
      setProducts(await api.products({ merchant: storeId }))
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : '加载失败')
    }
  })

  function openNavigation() {
    if (!store || store.lat === null || store.lng === null) return
    const latitude = Number(store.lat)
    const longitude = Number(store.lng)
    if (Taro.getEnv() === Taro.ENV_TYPE.WEAPP) {
      Taro.openLocation({ latitude, longitude, name: store.name, address: store.address })
      return
    }
    const url = `https://uri.amap.com/marker?position=${longitude},${latitude}&name=${encodeURIComponent(
      store.name,
    )}&src=alliance&coordinate=gaode&callnative=1`
    if (typeof window !== 'undefined') {
      window.open(url, '_blank')
    }
  }

  return (
    <View className="page">
      {error && <View className="muted" aria-live="polite">{error}</View>}
      <View className="merchant-hero">
        {store?.logo_url ? (
          <Image className="avatar-mark" src={store.logo_url} mode="aspectFill" />
        ) : (
          <View className="avatar-mark">{store?.name?.slice(0, 1) ?? '店'}</View>
        )}
        <Text className="eyebrow" style={{ color: 'rgba(253,249,240,0.7)' }}>LOCAL STORE</Text>
        <Text className="title" style={{ margin: '8px 0' }}>{store?.name ?? '门店'}</Text>
        <Text className="muted">{store?.category_name} · {store?.address}</Text>
        <View style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '16px' }}>
          <Text className="tag">营业中</Text>
          <Text className="tag">到店服务</Text>
          <Text className="tag">资质已核验</Text>
        </View>
        {store && store.lat !== null && store.lng !== null && (
          <Button className="btn secondary" style={{ marginTop: '18px' }} onClick={openNavigation}>
            导航到店
          </Button>
        )}
      </View>

      <View className="section-head">
        <Text>在售服务</Text>
        <Text className="muted">{products.length} 件</Text>
      </View>
      {products.map((product) => (
        <View
          key={product.id}
          className="order-card"
          onClick={() => Taro.navigateTo({ url: `/pages/product/index?id=${product.id}` })}
        >
          <View className="row" style={{ paddingTop: 0 }}>
            <View style={{ flex: 1 }}>
              <Text style={{ display: 'block', fontSize: '30px', fontWeight: 600 }}>{product.title}</Text>
              <Text className="muted">{product.subtitle || '到店核销'}</Text>
            </View>
            <Text className="price">{formatMoney(product.price)}</Text>
          </View>
        </View>
      ))}
      {!products.length && !error && <View className="muted">该门店暂无在售商品</View>}
    </View>
  )
}
