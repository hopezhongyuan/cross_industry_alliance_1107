import { useLoad, showToast } from '@tarojs/taro'
import Taro from '@tarojs/taro'
import { View, Text, Input } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError, getToken, type CartData } from '../../api'

export default function Checkout() {
  const [cart, setCart] = useState<CartData | null>(null)
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [address, setAddress] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useLoad(() => {
    api
      .cart()
      .then(setCart)
      .catch((exc) => setError(exc instanceof ApiError ? exc.message : '加载失败'))
  })

  async function submit() {
    if (!getToken()) {
      Taro.navigateTo({ url: '/pages/login/index' })
      return
    }
    if (!cart?.merchant_id || !cart.items.length) return
    if (!name || !phone) {
      setError('请填写联系人与电话')
      return
    }
    setSubmitting(true)
    setError('')
    try {
      const order = await api.createOrder({
        merchant_id: cart.merchant_id,
        order_type: 'EXPRESS',
        items: cart.items.map((item) => ({ product_id: item.product_id, sku_id: item.sku_id, quantity: item.quantity })),
        contact: { name, phone, address_detail: address },
        remark: '',
      })
      await api.mockPay(order.id)
      showToast({ title: '支付成功', icon: 'success' })
      setTimeout(() => Taro.switchTab({ url: '/pages/orders/index' }), 800)
    } catch (exc) {
      setError(exc instanceof ApiError ? `${exc.code}：${exc.message}` : '下单失败')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <View className="page">
      <View className="title">确认订单</View>
      {error && <View className="muted">{error}</View>}
      <View className="card">
        <View className="row"><Text>商品合计</Text><Text className="price">¥{((cart?.total_amount ?? 0) / 100).toFixed(2)}</Text></View>
        <View className="muted">{cart?.items.map((item) => `${item.title} × ${item.quantity}`).join('，')}</View>
      </View>
      <View className="card">
        <Input className="input" placeholder="联系人姓名" value={name} onInput={(event) => setName(event.detail.value)} />
        <Input className="input" placeholder="联系电话" value={phone} onInput={(event) => setPhone(event.detail.value)} />
        <Input className="input" placeholder="收货地址" value={address} onInput={(event) => setAddress(event.detail.value)} />
      </View>
      <View className={`btn ${submitting ? 'disabled' : ''}`} onClick={submitting ? undefined : submit}>
        {submitting ? '提交中…' : '提交订单并支付'}
      </View>
    </View>
  )
}
