import { View, Text } from '@tarojs/components'
import Taro from '@tarojs/taro'

type Props = {
  icon: string
  label: string
  to: string
  badge?: number
  bg?: string
  color?: string
}

export default function QuickAction({ icon, label, to, badge, bg = '#f1eadc', color = '#201d19' }: Props) {
  return (
    <View className="mch-quick" onClick={() => Taro.navigateTo({ url: to })}>
      <View className="mch-quick-icon" style={{ background: bg, color }}>
        <Text>{icon}</Text>
        {badge ? <Text className="mch-quick-badge">{badge > 99 ? '99+' : badge}</Text> : null}
      </View>
      <Text className="mch-quick-label">{label}</Text>
    </View>
  )
}
