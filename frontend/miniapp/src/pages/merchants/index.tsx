import { useLoad } from '@tarojs/taro'
import Taro from '@tarojs/taro'
import { View, Text, Input, Button, Image } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError, type CategoryRow, type StoreRow } from '../../api'
import BottomNav from '../../components/BottomNav'

const DEFAULT_LAT = 30.2741
const DEFAULT_LNG = 120.1551

export default function MerchantsPage() {
  const [stores, setStores] = useState<StoreRow[]>([])
  const [categories, setCategories] = useState<CategoryRow[]>([])
  const [categoryId, setCategoryId] = useState(0)
  const [keyword, setKeyword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  async function load(query = keyword, category = categoryId) {
    setLoading(true)
    setError('')
    try {
      const result = await api.stores({
        lat: DEFAULT_LAT,
        lng: DEFAULT_LNG,
        category: category || undefined,
        q: query || undefined,
      })
      setStores(result.items)
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useLoad(async () => {
    try {
      setCategories(await api.categories())
    } catch (ignored) {
      setCategories([])
    }
    await load('', 0)
  })

  function pickCategory(id: number) {
    const next = categoryId === id ? 0 : id
    setCategoryId(next)
    load(keyword, next)
  }

  return (
    <View className="page" style={{ paddingBottom: '80px' }}>
      <Text className="eyebrow">NEARBY</Text>
      <View className="title">附近好店</View>

      <View className="deco-search" style={{ marginBottom: '14px' }}>
        <Input
          className="deco-search-input"
          placeholder="搜索门店或服务…"
          value={keyword}
          onInput={(event) => setKeyword(event.detail.value)}
          onConfirm={() => load()}
        />
        <Button className="deco-search-button" onClick={() => load()}>搜索</Button>
      </View>

      <View className="sku-row" style={{ marginBottom: '18px' }}>
        <View className={`sku-chip ${categoryId === 0 ? 'active' : ''}`} onClick={() => pickCategory(0)}>全部</View>
        {categories.filter((item) => !item.parent).map((item) => (
          <View
            key={item.id}
            className={`sku-chip ${categoryId === item.id ? 'active' : ''}`}
            onClick={() => pickCategory(item.id)}
          >
            {item.name}
          </View>
        ))}
      </View>

      {error && <View className="muted" aria-live="polite">{error}</View>}
      {loading && <View className="muted">正在寻找附近好店…</View>}
      {stores.map((store) => (
        <View key={store.id} className="store-card" onClick={() => Taro.navigateTo({ url: `/pages/store/index?id=${store.id}` })}>
          {store.logo_url ? (
            <Image className="store-mark" src={store.logo_url} mode="aspectFill" />
          ) : (
            <View className="store-mark">{store.name.slice(0, 1)}</View>
          )}
          <View className="store-body">
            <View className="row" style={{ paddingTop: 0 }}>
              <Text style={{ fontSize: '30px', fontWeight: 600 }}>{store.name}</Text>
              <Text className="muted">
                {store.distance_meters != null ? `${(store.distance_meters / 1000).toFixed(1)}km` : '附近'}
              </Text>
            </View>
            <Text className="muted" style={{ display: 'block' }}>{store.category_name || '到店服务'} · {store.address}</Text>
            <View style={{ display: 'flex', gap: '8px', marginTop: '10px' }}>
              <Text className="tag">营业中</Text>
              <Text className="tag">到店服务</Text>
            </View>
          </View>
        </View>
      ))}
      {!loading && !stores.length && !error && <View className="muted">附近暂无营业门店</View>}
      <BottomNav />
    </View>
  )
}
