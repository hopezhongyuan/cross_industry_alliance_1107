import { View, Text } from '@tarojs/components'
import Taro from '@tarojs/taro'

type Props = {
  value: string | number
  label: string
  sub?: string
  to?: string
  accent?: string
}

export default function MetricCard({ value, label, sub, to, accent = '#201d19' }: Props) {
  function handleClick() {
    if (to) Taro.navigateTo({ url: to })
  }
  return (
    <View className="mch-metric" onClick={to ? handleClick : undefined}>
      <Text className="mch-metric-value" style={{ color: accent }}>{value}</Text>
      <Text className="mch-metric-label">{label}</Text>
      {sub && <Text className="mch-metric-sub">{sub}</Text>}
    </View>
  )
}
