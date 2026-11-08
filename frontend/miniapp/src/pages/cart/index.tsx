import { useLoad } from '@tarojs/taro'
import Taro from '@tarojs/taro'
import { View, Text } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError, type CartData } from '../../api'

export default function Cart() {
  const [cart, setCart] = useState<CartData | null>(null)
  const [error, setError] = useState('')

  async function load() {
    try {
      setCart(await api.cart())
      setError('')
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : '加载失败')
    }
  }

  useLoad(load)

  async function change(itemId: number, quantity: number) {
    try {
      setCart(await api.updateCart(itemId, { quantity }))
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : '更新失败')
    }
  }

  async function remove(itemId: number) {
    try {
      await api.removeCart(itemId)
      await load()
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : '删除失败')
    }
  }

  function checkout() {
    if (!cart || !cart.items.length) return
    Taro.navigateTo({ url: '/pages/checkout/index' })
  }

  return (
    <View className="page">
      <View className="title">购物车</View>
      {error && <View className="muted">{error}</View>}
      {cart?.items.map((item) => (
        <View key={item.id} className="card">
          <View className="row">
            <Text style={{ fontSize: '28px' }}>{item.title}</Text>
            <Text className="price">¥{(item.price_amount / 100).toFixed(2)}</Text>
          </View>
          <View className="row">
            <View style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
              <Text className="tag" onClick={() => change(item.id, Math.max(1, item.quantity - 1))}>-</Text>
              <Text>{item.quantity}</Text>
              <Text className="tag" onClick={() => change(item.id, item.quantity + 1)}>+</Text>
            </View>
            <Text className="muted" onClick={() => remove(item.id)}>移除</Text>
          </View>
        </View>
      ))}
      {cart && !cart.items.length && <View className="muted">购物车为空</View>}
      <View className="card">
        <View className="row">
          <Text>合计</Text>
          <Text className="price">¥{((cart?.total_amount ?? 0) / 100).toFixed(2)}</Text>
        </View>
      </View>
      <View className={`btn ${!cart?.items.length ? 'disabled' : ''}`} onClick={cart?.items.length ? checkout : undefined}>
        去结算
      </View>
    </View>
  )
}
