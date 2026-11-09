import { View } from '@tarojs/components'
import type { ReactNode } from 'react'

type Props = { children: ReactNode }

export default function QuickActions({ children }: Props) {
  return <View className="mch-quick-grid">{children}</View>
}
