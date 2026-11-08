import { useLoad } from '@tarojs/taro'
import Taro from '@tarojs/taro'
import { View, Text, Button, Image } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError, type CartData } from '../../api'
import BottomNav from '../../components/BottomNav'
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
      <Text className="eyebrow">YOUR BAG</Text>
      <View className="title">购物车</View>
      {error && <View className="muted" aria-live="polite">{error}</View>}

      <View className="card">
        <View className="section-head">
          <Text>本店商品</Text>
          <Text className="muted">{cart?.items.length ?? 0} 件</Text>
        </View>
        {cart?.items.map((item) => (
          <View key={item.id} className="cart-item">
            {item.cover_url ? (
              <Image className="cart-thumb" src={item.cover_url} mode="aspectFill" />
            ) : (
              <View className="cart-thumb">{item.title?.slice(0, 1)}</View>
            )}
            <View style={{ flex: 1 }}>
              <Text style={{ display: 'block', fontSize: '26px' }}>{item.title}</Text>
              <Text className="price" style={{ fontSize: '26px' }}>{formatMoney(item.price_amount)}</Text>
              <View style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '10px' }}>
                <View style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                  <Button className="qty-btn" aria-label="减少数量" onClick={() => change(item.id, Math.max(1, item.quantity - 1))}>-</Button>
                  <Text>{item.quantity}</Text>
                  <Button className="qty-btn" aria-label="增加数量" onClick={() => change(item.id, item.quantity + 1)}>+</Button>
                </View>
                <Button className="link-btn" onClick={() => remove(item.id)}>移除</Button>
              </View>
            </View>
          </View>
        ))}
        {cart && !cart.items.length && <View className="muted">购物车为空，去逛逛附近好店吧</View>}
      </View>

      <View className="card">
        <View className="summary-total" style={{ borderTop: 'none', marginTop: 0 }}>
          <Text>合计</Text>
          <Text className="price">{formatMoney(cart?.total_amount)}</Text>
        </View>
        <Button className={`btn ${!cart?.items.length ? 'disabled' : ''}`} onClick={cart?.items.length ? checkout : undefined}>
          去结算
        </Button>
      </View>
      <BottomNav />
    </View>
  )
}
