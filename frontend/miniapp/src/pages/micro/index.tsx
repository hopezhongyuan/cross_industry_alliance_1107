import { useLoad, useRouter } from '@tarojs/taro'
import { View, Text } from '@tarojs/components'
import { useState } from 'react'
import { api, ApiError, type DecoPageData } from '../../api'
import MicroPageRenderer from '../../components/MicroPageRenderer'
import BottomNav from '../../components/BottomNav'

export default function MicroPage() {
  const router = useRouter()
  const slug = router.params.slug || 'home'
  const [page, setPage] = useState<DecoPageData | null>(null)
  const [error, setError] = useState('')

  useLoad(async () => {
    try {
      setPage(await api.decoPage(slug))
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : '页面加载失败')
    }
  })

  return (
    <View className="page deco-page-shell">
      {error && <View className="muted">{error}</View>}
      {page ? (
        <View>
          <View className="deco-page-header">
            <Text className="deco-page-title">{page.title}</Text>
          </View>
          <MicroPageRenderer components={page.components} />
        </View>
      ) : null}
      <BottomNav />
    </View>
  )
}
