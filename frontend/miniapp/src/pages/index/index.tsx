import { useLoad } from '@tarojs/taro'
import { View, Text, Input, Button, Navigator } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError, type CategoryRow, type DecoPageData, type StoreRow } from '../../api'
import BottomNav from '../../components/BottomNav'
import MicroPageRenderer from '../../components/MicroPageRenderer'

const DEFAULT_LAT = 30.2741
const DEFAULT_LNG = 120.1551

export default function Index() {
  const [stores, setStores] = useState<StoreRow[]>([])
  const [categories, setCategories] = useState<CategoryRow[]>([])
  const [categoryId, setCategoryId] = useState(0)
  const [keyword, setKeyword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [home, setHome] = useState<DecoPageData | null>(null)

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
      setHome(await api.decoPage('home'))
      setLoading(false)
      return
    } catch (ignored) {
      setHome(null)
    }
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

  if (home) {
    return (
      <View className="page deco-page-shell">
        <MicroPageRenderer components={home.components} />
        <BottomNav />
      </View>
    )
  }

  return (
    <View className="page">
      <View className="row">
        <Text style={{ fontWeight: 600 }}>杭州 · 西湖区</Text>
        <Text className="muted">3km 内</Text>
      </View>
      <View className="card" style={{ padding: '12px 16px' }}>
        <Input
          className="input"
          name="keyword"
          placeholder="搜索门店或服务…"
          value={keyword}
          onInput={(event) => setKeyword(event.detail.value)}
          onConfirm={() => load()}
        />
        <Button className="link-btn" onClick={() => load()}>搜索</Button>
      </View>

      <View className="card promo">
        <Text style={{ fontSize: '32px', fontWeight: 600 }}>邻里好店，一站直达</Text>
        <Text className="muted">餐饮 · 洗车 · 健身 · 美容 · 亲子</Text>
      </View>

      <View style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', marginBottom: '16px' }}>
        <Button className={`chip ${categoryId === 0 ? 'active' : ''}`} onClick={() => pickCategory(0)}>全部</Button>
        {categories.map((item) => (
          <Button
            key={item.id}
            className={`chip ${categoryId === item.id ? 'active' : ''}`}
            onClick={() => pickCategory(item.id)}
          >
            {item.name}
          </Button>
        ))}
      </View>

      {error && <View className="muted" aria-live="polite">{error}</View>}
      {loading && <View className="muted">加载中…</View>}
      {stores.map((store) => (
        <Navigator key={store.id} url={`/pages/store/index?id=${store.id}`} className="card">
          <View className="row">
            <Text className="card-title">{store.name}</Text>
            <Text className="muted">
              {store.distance_meters != null ? `${(store.distance_meters / 1000).toFixed(1)}km` : '附近'}
            </Text>
          </View>
          <View className="muted">{store.category_name || '到店服务'} · {store.address}</View>
          <View style={{ display: 'flex', gap: '10px', marginTop: '12px' }}>
            <Text className="tag">营业中</Text>
            <Text className="tag">到店服务</Text>
            <Text className="tag">可预约</Text>
          </View>
        </Navigator>
      ))}
      {!loading && !stores.length && !error && <View className="muted">附近暂无营业门店</View>}
      <BottomNav />
    </View>
  )
}
