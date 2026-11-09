import { useLoad, useRouter, showToast } from '@tarojs/taro'
import Taro from '@tarojs/taro'
import { View, Text, Input, Button } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError, getToken, type AddressRow, type CartData, type ProductDetail } from '../../api'
import { formatMoney } from '../../format'

type OrderResult = { order_no: string; id: number; payable_amount: number }
type BatchResult = { group_no: string; total_amount: number }

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
  const [batchResult, setBatchResult] = useState<BatchResult | null>(null)

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

  const directMerchantId = product?.merchant_id
  const directOrderType = product?.type === 'SERVICE' ? 'SERVICE' : 'EXPRESS'
  const directTotal = (product?.price ?? 0) * directQuantity
  const needSlot = mode === 'direct' && Boolean(product?.appointment_required)

  const selectedGroups = (cart?.groups ?? [])
    .map((g) => ({
      merchant_id: g.merchant_id,
      merchant_name: g.merchant_name,
      items: g.items.filter((i) => i.selected),
      selected_amount: g.items.filter((i) => i.selected).reduce((s, i) => s + i.price_amount * i.quantity, 0),
    }))
    .filter((g) => g.items.length > 0)

  const totalAmount = mode === 'direct' ? directTotal : selectedGroups.reduce((s, g) => s + g.selected_amount, 0)

  async function submit() {
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
      const contact = {
        name,
        phone,
        address_detail: chosen ? `${chosen.city}${chosen.district}${chosen.detail}` : manualAddress,
      }

      if (mode === 'direct') {
        if (!directMerchantId) return
        const payload: Parameters<typeof api.createOrder>[0] = {
          merchant_id: directMerchantId,
          order_type: directOrderType,
          items: [{ product_id: directProductId, sku_id: directSkuId, quantity: directQuantity }],
          contact,
          remark: '',
        }
        if (needSlot && slotId) payload.appointment = { slot_id: slotId }
        const order = await api.createOrder(payload)
        await api.mockPay(order.id)
        setResult({ id: order.id, order_no: order.order_no, payable_amount: order.payable_amount })
      } else {
        if (!selectedGroups.length) {
          setError('请先在购物车勾选商品')
          setSubmitting(false)
          return
        }
        const batch = await api.createBatchOrder({
          groups: selectedGroups.map((g) => ({
            merchant_id: g.merchant_id,
            order_type: 'EXPRESS',
            items: g.items.map((i) => ({ product_id: i.product_id, sku_id: i.sku_id, quantity: i.quantity })),
          })),
          contact,
          remark: '',
        })
        await api.mockPayGroup(batch.group_no, batch.total_amount)
        setBatchResult({ group_no: batch.group_no, total_amount: batch.total_amount })
      }
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
        <View className="status-hero">
          <Text className="eyebrow" style={{ color: 'rgba(253,249,240,0.72)' }}>ORDER CONFIRMED</Text>
          <Text className="title" style={{ color: '#fdf9f0', marginTop: '10px' }}>支付成功，已通知商户</Text>
          <View className="rule-line" style={{ color: 'rgba(253,249,240,0.75)' }}>
            <Text>订单号</Text><Text style={{ color: '#fdf9f0' }}>{result.order_no}</Text>
          </View>
          <View className="rule-line" style={{ color: 'rgba(253,249,240,0.75)' }}>
            <Text>支付金额</Text><Text style={{ color: '#fdf9f0' }}>{formatMoney(result.payable_amount)}</Text>
          </View>
        </View>
        <Button className="btn" onClick={() => Taro.redirectTo({ url: `/pages/order-detail/index?id=${result.id}` })}>
          查看订单
        </Button>
        <Button className="btn secondary" onClick={() => Taro.reLaunch({ url: '/pages/index/index' })}>
          返回首页
        </Button>
      </View>
    )
  }

  if (batchResult) {
    return (
      <View className="page">
        <View className="status-hero">
          <Text className="eyebrow" style={{ color: 'rgba(253,249,240,0.72)' }}>ORDERS CONFIRMED</Text>
          <Text className="title" style={{ color: '#fdf9f0', marginTop: '10px' }}>支付成功，已通知各商户</Text>
          <View className="rule-line" style={{ color: 'rgba(253,249,240,0.75)' }}>
            <Text>合单号</Text><Text style={{ color: '#fdf9f0' }}>{batchResult.group_no}</Text>
          </View>
          <View className="rule-line" style={{ color: 'rgba(253,249,240,0.75)' }}>
            <Text>支付金额</Text><Text style={{ color: '#fdf9f0' }}>{formatMoney(batchResult.total_amount)}</Text>
          </View>
        </View>
        <Button className="btn" onClick={() => Taro.redirectTo({ url: '/pages/orders/index' })}>
          查看订单
        </Button>
        <Button className="btn secondary" onClick={() => Taro.reLaunch({ url: '/pages/index/index' })}>
          返回首页
        </Button>
      </View>
    )
  }

  return (
    <View className="page" style={{ paddingBottom: '140px' }}>
      <Text className="eyebrow">CHECKOUT</Text>
      <View className="title">确认订单</View>
      {error && <View className="muted" aria-live="polite">{error}</View>}

      <View className="card">
        <View className="section-head"><Text>商品清单</Text><Text className="muted">{mode === 'direct' ? '直接购买' : '购物车结算'}</Text></View>
        {mode === 'direct' ? (
          <View className="order-item">
            <View className="order-thumb">{product?.title?.slice(0, 1) ?? '商'}</View>
            <View style={{ flex: 1 }}>
              <Text style={{ display: 'block', fontSize: '26px' }}>{product?.title || '商品'}</Text>
              <Text className="muted">× {directQuantity}</Text>
            </View>
            <Text className="price">{formatMoney(directTotal)}</Text>
          </View>
        ) : (
          selectedGroups.map((group) => (
            <View key={group.merchant_id} style={{ borderBottom: '1px solid #efe7d8', paddingBottom: '12px', marginBottom: '12px' }}>
              <View className="section-head" style={{ padding: '0 0 8px' }}>
                <Text style={{ fontWeight: 600 }}>{group.merchant_name}</Text>
                <Text className="muted">{formatMoney(group.selected_amount)}</Text>
              </View>
              {group.items.map((item) => (
                <View key={item.id} className="order-item">
                  <View className="order-thumb">{item.title?.slice(0, 1) ?? '商'}</View>
                  <View style={{ flex: 1 }}>
                    <Text style={{ display: 'block', fontSize: '26px' }}>{item.title}</Text>
                    <Text className="muted">× {item.quantity}</Text>
                  </View>
                  <Text className="price">{formatMoney(item.price_amount * item.quantity)}</Text>
                </View>
              ))}
            </View>
          ))
        )}
      </View>

      {needSlot && (
        <View className="card">
          <View className="section-head"><Text>预约时段</Text><Text className="muted">必选</Text></View>
          <View className="sku-row">
            {(product?.slots ?? []).map((slot) => (
              <View
                key={slot.id}
                className={`sku-chip ${slotId === slot.id ? 'active' : ''}`}
                onClick={() => setSlotId(slot.id)}
              >
                {slot.slot_date} {slot.start_time}
              </View>
            ))}
          </View>
          {!product?.slots?.length && <View className="muted">暂无可选时段</View>}
        </View>
      )}

      <View className="card">
        <View className="section-head"><Text>配送信息</Text><Text className="muted">{addresses.length ? '选择地址' : '手动填写'}</Text></View>
        {addresses.length > 0 ? (
          addresses.map((item) => (
            <View
              key={item.id}
              className={`address-row ${addressId === item.id ? 'selected' : ''}`}
              onClick={() => setAddressId(item.id)}
            >
              <Text style={{ display: 'block', fontSize: '26px' }}>
                {addressId === item.id ? '● ' : '○ '}{item.receiver_name} {item.phone}
              </Text>
              <Text className="muted">{item.city}{item.district}{item.detail}</Text>
            </View>
          ))
        ) : (
          <Input
            className="input"
            name="address"
            placeholder="请输入详细地址…"
            value={manualAddress}
            onInput={(event) => setManualAddress(event.detail.value)}
          />
        )}
        <Text className="field-label">联系人姓名</Text>
        <Input className="input" name="receiver_name" placeholder="请输入联系人姓名…" value={name} onInput={(event) => setName(event.detail.value)} />
        <Text className="field-label">联系电话</Text>
        <Input className="input" name="receiver_phone" type="number" placeholder="请输入联系电话…" value={phone} onInput={(event) => setPhone(event.detail.value)} />
      </View>

      <View className="card">
        <View className="section-head"><Text>费用明细</Text><Text className="muted">实时计算</Text></View>
        <View className="summary-row"><Text>商品金额</Text><Text>{formatMoney(totalAmount)}</Text></View>
        <View className="summary-row"><Text>配送费</Text><Text>{formatMoney(0)}</Text></View>
        <View className="summary-total">
          <Text>应付合计</Text>
          <Text className="price">{formatMoney(totalAmount)}</Text>
        </View>
      </View>

      <View className="fixed-bar buy-bar">
        <View style={{ flex: 1 }}>
          <Text className="muted">应付</Text>
          <Text className="price" style={{ marginLeft: '8px' }}>{formatMoney(totalAmount)}</Text>
        </View>
        <Button
          className={`btn ${submitting ? 'disabled' : ''}`}
          style={{ width: '260px', marginTop: 0 }}
          onClick={submitting ? undefined : submit}
        >
          {submitting ? '提交中…' : '提交并支付'}
        </Button>
      </View>
    </View>
  )
}
