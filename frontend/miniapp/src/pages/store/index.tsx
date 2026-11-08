import { useLoad, useRouter } from '@tarojs/taro'
import { View, Text, Navigator } from '@tarojs/components'
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

  return (
    <View className="page">
      <View className="card">
        <View className="title" style={{ marginBottom: '8px' }}>{store?.name ?? '门店'}</View>
        <View className="muted">{store?.category_name} · {store?.address}</View>
        <View style={{ display: 'flex', gap: '10px', marginTop: '12px' }}>
          <Text className="tag">营业中</Text>
          <Text className="tag">到店服务</Text>
          <Text className="tag">资质已核验</Text>
        </View>
      </View>
      <View className="muted" style={{ marginBottom: '12px' }}>在售服务</View>
      {error && <View className="muted" aria-live="polite">{error}</View>}
      {products.map((product) => (
        <Navigator key={product.id} url={`/pages/product/index?id=${product.id}`} className="card">
          <View className="row">
            <Text className="card-title">{product.title}</Text>
            <Text className="price">{formatMoney(product.price)}</Text>
          </View>
          <View className="muted">{product.subtitle || '到店核销'}</View>
        </Navigator>
      ))}
      {!products.length && !error && <View className="muted">该门店暂无在售商品</View>}
    </View>
  )
}
