import { View, Text, Image } from '@tarojs/components'
import Taro from '@tarojs/taro'

type Props = {
  name: string
  shortName?: string
  logoUrl?: string
  statusLabel?: string
  showSettings?: boolean
}

export default function MerchantHeader({ name, shortName, logoUrl, statusLabel = '营业中', showSettings = true }: Props) {
  const display = shortName || name
  return (
    <View className="mch-header">
      <View className="mch-header-main">
        {logoUrl ? (
          <Image className="mch-logo" src={logoUrl} mode="aspectFill" />
        ) : (
          <View className="mch-logo mch-logo-fallback">{display.slice(0, 1)}</View>
        )}
        <View className="mch-header-text">
          <Text className="mch-header-name">{name}</Text>
          <View className="mch-header-sub">
            <Text className="mch-status-dot" />
            <Text className="mch-status-text">{statusLabel}</Text>
          </View>
        </View>
      </View>
      {showSettings && (
        <View
          className="mch-header-action"
          onClick={() => Taro.navigateTo({ url: '/pages/merchant/settings/index' })}
        >
          <Text className="mch-header-icon">⚙</Text>
        </View>
      )}
    </View>
  )
}
