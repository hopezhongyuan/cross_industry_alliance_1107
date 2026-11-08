import { useLoad } from '@tarojs/taro'
import Taro from '@tarojs/taro'
import { View, Text, Button } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError, type CartData } from '../../api'
import { formatMoney } from '../../format'

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
    const result = await Taro.showModal({ title: '移出购物车', content: '确定移出该商品吗？' })
    if (!result.confirm) return
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
      {error && <View className="muted" aria-live="polite">{error}</View>}
      {cart?.items.map((item) => (
        <View key={item.id} className="card">
          <View className="row">
            <Text className="card-title">{item.title}</Text>
            <Text className="price">{formatMoney(item.price_amount)}</Text>
          </View>
          <View className="row">
            <View style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
              <Button
                className="qty-btn"
                aria-label="减少数量"
                onClick={() => change(item.id, Math.max(1, item.quantity - 1))}
              >
                -
              </Button>
              <Text>{item.quantity}</Text>
              <Button className="qty-btn" aria-label="增加数量" onClick={() => change(item.id, item.quantity + 1)}>
                +
              </Button>
            </View>
            <Button className="link-btn" onClick={() => remove(item.id)}>移除</Button>
          </View>
        </View>
      ))}
      {cart && !cart.items.length && <View className="muted">购物车为空</View>}
      <View className="card">
        <View className="row">
          <Text>合计</Text>
          <Text className="price">{formatMoney(cart?.total_amount)}</Text>
        </View>
      </View>
      <Button
        className={`btn ${!cart?.items.length ? 'disabled' : ''}`}
        onClick={cart?.items.length ? checkout : undefined}
      >
        去结算
      </Button>
    </View>
  )
}
