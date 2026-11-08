import { View, Text, Navigator } from '@tarojs/components'

const menus = [
  { label: '商品管理', url: '/pages/merchant/products/index' },
  { label: '平台商品', url: '/pages/merchant/templates/index' },
  { label: '商品分类', url: '/pages/merchant/product-categories/index' },
  { label: '订单处理', url: '/pages/merchant/orders/index' },
  { label: '核销', url: '/pages/merchant/verify/index' },
  { label: '账单与提现', url: '/pages/merchant/statements/index' },
]

export default function MerchantHome() {
  return (
    <View className="page">
      <View className="title">商户中心</View>
      {menus.map((menu) => (
        <Navigator key={menu.url} url={menu.url} className="card">
          <Text style={{ fontSize: '30px' }}>{menu.label}</Text>
        </Navigator>
      ))}
      <View className="muted">仅本门店数据可见；店员不可见金额与提现。</View>
    </View>
  )
}
