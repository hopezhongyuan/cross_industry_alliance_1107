import { useEffect, useState } from 'react'
import { View, Image } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { api, type Schemas } from '../api'

type PopupPublic = Schemas['PopupAdPublic']

const STORAGE_PREFIX = 'popup_ad_seen_'

function todayStr(): string {
  const d = new Date()
  return `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`
}

function shouldShow(popup: PopupPublic): boolean {
  if (!popup.id || !popup.frequency) return true
  const key = `${STORAGE_PREFIX}${popup.id}`
  switch (popup.frequency) {
    case 'EVERY_LAUNCH':
      return true
    case 'ONCE_PER_DAY': {
      const last = Taro.getStorageSync(key) as string | ''
      return last !== todayStr()
    }
    case 'ONCE_PER_WEEK': {
      const last = Number(Taro.getStorageSync(key) || 0)
      const weekMs = 7 * 24 * 60 * 60 * 1000
      return !last || Date.now() - last > weekMs
    }
    case 'ONCE_PER_USER':
      return !Taro.getStorageSync(key)
    default:
      return true
  }
}

function markShown(popup: PopupPublic) {
  if (!popup.id || !popup.frequency) return
  const key = `${STORAGE_PREFIX}${popup.id}`
  switch (popup.frequency) {
    case 'ONCE_PER_DAY':
      Taro.setStorageSync(key, todayStr())
      break
    case 'ONCE_PER_WEEK':
      Taro.setStorageSync(key, Date.now())
      break
    case 'ONCE_PER_USER':
      Taro.setStorageSync(key, '1')
      break
    default:
      break
  }
}

function openLink(linkUrl?: string) {
  if (!linkUrl) return
  if (linkUrl.startsWith('/')) {
    Taro.navigateTo({ url: linkUrl }).catch(() => {
      Taro.switchTab({ url: linkUrl }).catch(() => undefined)
    })
    return
  }
  if (linkUrl.startsWith('http')) {
    Taro.setClipboardData({ data: linkUrl })
    Taro.showToast({ title: '链接已复制', icon: 'none' })
    return
  }
}

export default function PopupAd() {
  const [popup, setPopup] = useState<PopupPublic | null>(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined
    const load = async () => {
      try {
        const data = await api.currentPopupAd()
        if (!data || !data.id || !data.image_url) return
        if (!shouldShow(data)) return
        setPopup(data)
        setVisible(true)
        try {
          await api.reportPopupImpression(data.id)
        } catch {
          // 上报失败不影响展示
        }
        markShown(data)
      } catch {
        // 无生效弹窗或接口异常，静默
      }
    }
    timer = setTimeout(load, 1000)
    return () => {
      if (timer) clearTimeout(timer)
    }
  }, [])

  if (!visible || !popup) return null

  return (
    <View
      className="popup-ad-mask"
      onClick={() => setVisible(false)}
    >
      <View className="popup-ad-dialog" onClick={(e) => e.stopPropagation()}>
        <Image
          className="popup-ad-image"
          src={popup.image_url!}
          mode="widthFix"
          onClick={() => {
            openLink(popup.link_url)
            setVisible(false)
          }}
        />
        <View className="popup-ad-close" onClick={() => setVisible(false)}>✕</View>
      </View>
    </View>
  )
}
