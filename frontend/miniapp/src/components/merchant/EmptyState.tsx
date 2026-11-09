import { View, Text } from '@tarojs/components'

type Props = {
  text?: string
  icon?: string
}

export default function EmptyState({ text = '暂无数据', icon = '📭' }: Props) {
  return (
    <View className="mch-empty">
      <Text className="mch-empty-icon">{icon}</Text>
      <Text className="mch-empty-text">{text}</Text>
    </View>
  )
}
