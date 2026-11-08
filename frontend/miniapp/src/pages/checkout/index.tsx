import { useLoad, useRouter, showToast } from '@tarojs/taro'
import Taro from '@tarojs/taro'
import { View, Text, Input, Button } from '@tarojs/components'
import { useEffect, useState } from 'react'
import { api, ApiError, getToken, type AddressRow, type CartData, type ProductDetail } from '../../api'
import { formatMoney } from '../../format'

type OrderResult = { order_no: string; id: number; payable_amount: number }

export default function Checkout() {
  const router = useRouter()
  const mode = router.params.mode === 'direct' ? 'direct' : 'cart'
  const directProductId = Number(router.params.product_id || 0)
  const directSkuId = router.params.sku_id ? Number(router.params.sku_id) : null
  const directQuantity = Number(router.params.quantity || 1)

  const [cart, setCart] = useState<CartData | null>(null)
  const [product, setProduct] = useState<ProductDetail | null>(null)
  const [addresses, setAddresses] = useState<AddressRow[]>([])
  const [addressId, setAddressId] = useState<number | null>(null)
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [manualAddress, setManualAddress] = useState('')
  const [slotId, setSlotId] = useState<number | null>(null)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<OrderResult | null>(null)

  useLoad(async () => {
    if (!getToken()) {
      Taro.navigateTo({ url: '/pages/login/index' })
      return
    }
    try {
      if (mode === 'direct') {
        const detail = await api.product(directProductId)
        setProduct(detail)
        setSlotId(detail.slots?.[0]?.id ?? null)
      } else {
        setCart(await api.cart())
      }
      const list = await api.addresses().catch(() => [] as AddressRow[])
      setAddresses(list)
      const preferred = list.find((item) => item.is_default) ?? list[0]
      if (preferred) {
        setAddressId(preferred.id)
        setName(preferred.receiver_name)
        setPhone(preferred.phone)
      }
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : '加载失败')
    }
  })

  useEffect(() => {
    const chosen = addresses.find((item) => item.id === addressId)
    if (chosen) {
      setName(chosen.receiver_name)
      setPhone(chosen.phone)
    }
  }, [addressId, addresses])

  const merchantId = mode === 'direct' ? product?.merchant_id : cart?.merchant_id
  const orderType = mode === 'direct' && product?.type === 'SERVICE' ? 'SERVICE' : 'EXPRESS'
  const totalAmount =
    mode === 'direct' ? (product?.price ?? 0) * directQuantity : cart?.total_amount ?? 0
  const needSlot = mode === 'direct' && Boolean(product?.appointment_required)

  async function submit() {
    if (!merchantId) return
    if (!name || !phone) {
      setError('请填写联系人与电话')
      return
    }
    if (needSlot && !slotId) {
      setError('请选择预约时段')
      return
    }
    setSubmitting(true)
    setError('')
    try {
      const chosen = addresses.find((item) => item.id === addressId)
      const payload: Parameters<typeof api.createOrder>[0] = {
        merchant_id: merchantId,
        order_type: orderType,
        items:
          mode === 'direct'
            ? [{ product_id: directProductId, sku_id: directSkuId, quantity: directQuantity }]
            : (cart?.items ?? []).map((item) => ({
                product_id: item.product_id,
                sku_id: item.sku_id,
                quantity: item.quantity,
              })),
        contact: {
          name,
          phone,
          address_detail: chosen ? `${chosen.city}${chosen.district}${chosen.detail}` : manualAddress,
        },
        remark: '',
      }
      if (needSlot && slotId) payload.appointment = { slot_id: slotId }
      const order = await api.createOrder(payload)
      await api.mockPay(order.id)
      setResult({ id: order.id, order_no: order.order_no, payable_amount: order.payable_amount })
      showToast({ title: '支付成功', icon: 'success' })
    } catch (exc) {
      setError(exc instanceof ApiError ? `${exc.code}：${exc.message}` : '下单失败')
    } finally {
      setSubmitting(false)
    }
  }

  if (result) {
    return (
      <View className="page">
        <View className="card" style={{ textAlign: 'center' }}>
          <Text className="tag">支付成功</Text>
          <View className="title" style={{ marginTop: '16px' }}>已通知商户接单</View>
          <View className="rule-line"><Text>订单号</Text><Text>{result.order_no}</Text></View>
          <View className="rule-line"><Text>支付金额</Text><Text>{formatMoney(result.payable_amount)}</Text></View>
          <Button className="btn" onClick={() => Taro.redirectTo({ url: `/pages/order-detail/index?id=${result.id}` })}>
            查看订单
          </Button>
          <Button className="btn secondary" onClick={() => Taro.switchTab({ url: '/pages/index/index' })}>
            返回首页
          </Button>
        </View>
      </View>
    )
  }

  return (
    <View className="page">
      <View className="title">确认订单</View>
      {error && <View className="muted" aria-live="polite">{error}</View>}

      <View className="card">
        <View className="row"><Text>商品合计</Text><Text className="price">{formatMoney(totalAmount)}</Text></View>
        {mode === 'direct' ? (
          <View className="muted">{product?.title} × {directQuantity}</View>
        ) : (
          <View className="muted">{cart?.items.map((item) => `${item.title} × ${item.quantity}`).join('，')}</View>
        )}
      </View>

      {needSlot && (
        <View className="card">
          <View className="muted" style={{ marginBottom: '8px' }}>预约时段</View>
          <View style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
            {(product?.slots ?? []).map((slot) => (
              <Button
                key={slot.id}
                className={`chip ${slotId === slot.id ? 'active' : ''}`}
                onClick={() => setSlotId(slot.id)}
              >
                {slot.slot_date} {slot.start_time}
              </Button>
            ))}
          </View>
          {!product?.slots?.length && <View className="muted">暂无可选时段</View>}
        </View>
      )}

      {addresses.length > 0 && (
        <View className="card">
          <View className="muted" style={{ marginBottom: '8px' }}>收货地址</View>
          {addresses.map((item) => (
            <Button key={item.id} className="rule-btn" onClick={() => setAddressId(item.id)}>
              <Text style={{ display: 'block', color: '#1f2933' }}>
                {addressId === item.id ? '● ' : '○ '}{item.receiver_name} {item.phone}
              </Text>
              <Text style={{ display: 'block' }}>{item.city}{item.district}{item.detail}</Text>
            </Button>
          ))}
        </View>
      )}
      {!addresses.length && (
        <View className="card">
          <Text className="field-label">收货地址</Text>
          <Input
            className="input"
            name="address"
            placeholder="请输入详细地址…"
            value={manualAddress}
            onInput={(event) => setManualAddress(event.detail.value)}
          />
        </View>
      )}

      <View className="card">
        <Text className="field-label">联系人姓名</Text>
        <Input
          className="input"
          name="receiver_name"
          placeholder="请输入联系人姓名…"
          value={name}
          onInput={(event) => setName(event.detail.value)}
        />
        <Text className="field-label">联系电话</Text>
        <Input
          className="input"
          name="receiver_phone"
          type="number"
          placeholder="请输入联系电话…"
          value={phone}
          onInput={(event) => setPhone(event.detail.value)}
        />
      </View>

      <Button className={`btn ${submitting ? 'disabled' : ''}`} onClick={submitting ? undefined : submit}>
        {submitting ? '提交中…' : '提交订单并支付'}
      </Button>
    </View>
  )
}
