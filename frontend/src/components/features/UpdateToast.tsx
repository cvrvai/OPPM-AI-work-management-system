import { useEffect, useState } from 'react'
import { RefreshCw, X } from 'lucide-react'

/**
 * UpdateToast — shown when a new service worker is waiting.
 * Users can click "Update" to skip waiting and reload, or dismiss.
 */
export function UpdateToast() {
  const [show, setShow] = useState(false)

  useEffect(() => {
    const handler = (e: Event) => {
      // vite-plugin-pwa dispatches this custom event
      if ((e as CustomEvent).detail?.type === 'waiting') {
        setShow(true)
      }
    }
    window.addEventListener('vite-pwa:update-ready', handler)
    return () => window.removeEventListener('vite-pwa:update-ready', handler)
  }, [])

  if (!show) return null

  return (
    <div className="fixed bottom-4 right-4 z-50 flex items-center gap-3 rounded-lg border border-[#e9e9e7] bg-white px-4 py-3 shadow-lg">
      <div className="flex items-center gap-2 text-sm text-[#37352f]">
        <RefreshCw className="h-4 w-4 text-[#6b6b6b]" />
        <span>A new version is available.</span>
      </div>
      <button
        onClick={() => {
          // Tell the waiting SW to activate, then reload
          navigator.serviceWorker?.getRegistration().then((reg) => {
            reg?.waiting?.postMessage({ type: 'SKIP_WAITING' })
            window.location.reload()
          })
        }}
        className="rounded-md bg-[#2d2d2d] px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-[#1a1a1a]"
      >
        Update
      </button>
      <button
        onClick={() => setShow(false)}
        className="rounded-md p-1 text-[#6b6b6b] transition-colors hover:bg-[#f7f6f3]"
        aria-label="Dismiss"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  )
}
