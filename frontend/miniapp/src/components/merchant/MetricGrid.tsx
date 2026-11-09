import { View } from '@tarojs/components'
import type { ReactNode } from 'react'

type Props = { children: ReactNode }

export default function MetricGrid({ children }: Props) {
  return <View className="mch-metric-grid">{children}</View>
}
