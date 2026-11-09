import { View, Input, Text } from '@tarojs/components'

type Props = {
  value: string
  placeholder?: string
  onChange: (v: string) => void
  onSearch?: () => void
}

export default function SearchBar({ value, placeholder = '搜索…', onChange, onSearch }: Props) {
  return (
    <View className="mch-search">
      <Text className="mch-search-icon">🔍</Text>
      <Input
        className="mch-search-input"
        value={value}
        placeholder={placeholder}
        confirmType="search"
        onInput={(e) => onChange(e.detail.value)}
        onConfirm={onSearch}
      />
    </View>
  )
}
