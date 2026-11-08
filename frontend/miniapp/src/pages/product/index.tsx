import { useLoad, useRouter, showToast } from '@tarojs/taro'
import { View, Text } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError } from '../../api'

type Detail = {
  id: number
  title: string
  subtitle?: string
  detail?: string
  price: number
  merchant?: { name: string }
  skus?: Array<{ id: number; price: number; stock: number }>
}

export default function ProductDetail() {
  const router = useRouter()
  const [detail, setDetail] = useState<Detail | null>(null)
  const [error, setError] = useState('')
  const [adding, setAdding] = useState(false)

  useLoad(() => {
    const id = Number(router.params.id)
    api
      .product(id)
      .then((result) => setDetail(result))
      .catch((exc) => setError(exc instanceof ApiError ? exc.message : '加载失败'))
  })

  async function addToCart() {
    if (!detail) return
    setAdding(true)
    try {
      await api.addCart(detail.id, detail.skus?.[0]?.id ?? null, 1)
      showToast({ title: '已加入购物车', icon: 'success' })
    } catch (exc) {
      showToast({ title: exc instanceof ApiError ? exc.message : '加入失败', icon: 'none' })
    } finally {
      setAdding(false)
    }
  }

  return (
    <View className="page">
      <View className="card">
        <View className="title">{detail?.title ?? '—'}</View>
        <View className="muted">{detail?.merchant?.name}</View>
        <View className="price" style={{ marginTop: '16px' }}>
          ¥{detail ? (detail.price / 100).toFixed(2) : '0.00'}
        </View>
        <View className="muted" style={{ marginTop: '16px' }}>
          {detail?.detail || detail?.subtitle || '暂无详细说明'}
        </View>
      </View>
      {error && <View className="muted">{error}</View>}
      <View className={`btn ${adding ? 'disabled' : ''}`} onClick={adding ? undefined : addToCart}>
        加入购物车
      </View>
    </View>
  )
}
