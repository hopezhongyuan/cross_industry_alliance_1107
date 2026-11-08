import Taro from '@tarojs/taro'
import { View, Text } from '@tarojs/components'

const menus = [
  { label: '订单处理', url: '/pages/merchant/orders/index' },
  { label: '核销', url: '/pages/merchant/verify/index' },
  { label: '账单与提现', url: '/pages/merchant/statements/index' },
]

export default function MerchantHome() {
  return (
    <View className="page">
      <View className="title">商户中心</View>
      {menus.map((menu) => (
        <View key={menu.url} className="card" onClick={() => Taro.navigateTo({ url: menu.url })}>
          <Text style={{ fontSize: '30px' }}>{menu.label}</Text>
        </View>
      ))}
      <View className="muted">仅本门店数据可见；店员不可见金额与提现。</View>
    </View>
  )
}
