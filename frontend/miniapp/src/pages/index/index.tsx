import { useLoad } from '@tarojs/taro'
import Taro from '@tarojs/taro'
import { View, Text, Image } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError, clearToken, getToken, type ProductRow } from '../../api'

export default function Index() {
  const [items, setItems] = useState<ProductRow[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  async function load() {
    setLoading(true)
    setError('')
    try {
      setItems(await api.products())
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useLoad(() => {
    if (!getToken()) clearToken()
    load()
  })

  return (
    <View className="page">
      <View className="title">附近好店</View>
      {error && <View className="muted">{error}</View>}
      {items.map((item) => (
        <View
          key={item.id}
          className="card"
          onClick={() => Taro.navigateTo({ url: `/pages/product/index?id=${item.id}` })}
        >
          <View className="row">
            <Text style={{ fontSize: '30px', fontWeight: 600 }}>{item.title}</Text>
            <Text className="price">¥{(item.price / 100).toFixed(2)}</Text>
          </View>
          <View className="muted">{item.subtitle || item.merchant?.name || '到店消费'}</View>
        </View>
      ))}
      {!loading && !items.length && !error && <View className="muted">暂无商品，请先由商户发布</View>}
      {loading && <View className="muted">加载中…</View>}
    </View>
  )
}
