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

  async function toggleItem(itemId: number, selected: boolean) {
    try {
      setCart(await api.updateCart(itemId, { selected }))
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : '更新失败')
    }
  }

  async function toggleMerchant(merchantId: number, selected: boolean) {
    if (!cart) return
    try {
      const items = cart.groups.find((g) => g.merchant_id === merchantId)?.items ?? []
      const ids = items.map((i) => i.id)
      await Promise.all(ids.map((id) => api.updateCart(id, { selected })))
      await load()
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : '更新失败')
    }
  }

  async function toggleAll(selected: boolean) {
    if (!cart) return
    try {
      const ids = cart.groups.reduce<number[]>((acc, g) => acc.concat(g.items.map((i) => i.id)), [])
      await Promise.all(ids.map((id) => api.updateCart(id, { selected })))
      await load()
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
    if (!cart || !cart.total_selected_count) return
    Taro.navigateTo({ url: '/pages/checkout/index' })
  }

  const allSelected = Boolean(cart?.groups.length) && cart!.groups.every((g) => g.items.every((i) => i.selected))

  return (
    <View className="page">
      <Text className="eyebrow">YOUR BAG</Text>
      <View className="title">购物车</View>
      {error && <View className="muted" aria-live="polite">{error}</View>}

      {cart?.groups.map((group) => {
        const groupAllSelected = group.items.every((i) => i.selected)
        return (
          <View key={group.merchant_id} className="card">
            <View className="section-head" style={{ justifyContent: 'space-between' }}>
              <View style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Text className={`check ${groupAllSelected ? 'on' : ''}`} onClick={() => toggleMerchant(group.merchant_id, !groupAllSelected)}>
                  {groupAllSelected ? '✓' : ''}
                </Text>
                <Text style={{ fontWeight: 600 }}>{group.merchant_name}</Text>
              </View>
              <Text className="muted">{group.items.length} 件</Text>
            </View>
            {group.items.map((item) => (
              <View key={item.id} className="cart-item">
                <Text
                  className={`check ${item.selected ? 'on' : ''}`}
                  onClick={() => toggleItem(item.id, !item.selected)}
                >
                  {item.selected ? '✓' : ''}
                </Text>
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
          </View>
        )
      })}
      {cart && !cart.groups.length && (
        <View className="card"><View className="muted">购物车为空，去逛逛附近好店吧</View></View>
      )}

      <View className="fixed-bar buy-bar">
        <View style={{ display: 'flex', alignItems: 'center', gap: '10px' }} onClick={() => toggleAll(!allSelected)}>
          <Text className={`check ${allSelected ? 'on' : ''}`}>{allSelected ? '✓' : ''}</Text>
          <Text>全选</Text>
        </View>
        <View style={{ flex: 1, textAlign: 'right', paddingRight: '16px' }}>
          <Text className="muted">合计</Text>
          <Text className="price" style={{ marginLeft: '8px' }}>{formatMoney(cart?.total_selected_amount ?? 0)}</Text>
        </View>
        <Button
          className={`btn ${!cart?.total_selected_count ? 'disabled' : ''}`}
          style={{ width: '200px', marginTop: 0 }}
          onClick={cart?.total_selected_count ? checkout : undefined}
        >
          结算({cart?.total_selected_count ?? 0})
        </Button>
      </View>
      <BottomNav />
    </View>
  )
}
