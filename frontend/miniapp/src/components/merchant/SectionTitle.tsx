import { View, Text } from '@tarojs/components'
import Taro from '@tarojs/taro'

type Props = {
  title: string
  moreTo?: string
  moreText?: string
}

export default function SectionTitle({ title, moreTo, moreText = '查看全部' }: Props) {
  return (
    <View className="mch-section-title">
      <Text className="mch-section-title-text">{title}</Text>
      {moreTo && (
        <View className="mch-section-more" onClick={() => Taro.navigateTo({ url: moreTo })}>
          <Text>{moreText} ›</Text>
        </View>
      )}
    </View>
  )
}
