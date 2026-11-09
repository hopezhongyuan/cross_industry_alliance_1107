import { PropsWithChildren } from 'react'
import './app.css'
import PopupAd from './components/PopupAd'

function App({ children }: PropsWithChildren) {
  return (
    <>
      {children}
      <PopupAd />
    </>
  )
}

export default App
