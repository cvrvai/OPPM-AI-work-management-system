import { useToastStore } from '@/stores/toastStore'
import { CheckCircle, XCircle, Info, X } from 'lucide-react'
import { cn } from '@/lib/utils'

export function ToastContainer() {
  const toasts = useToastStore((s) => s.toasts)
  const removeToast = useToastStore((s) => s.removeToast)

  if (toasts.length === 0) return null

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={cn(
            'flex items-center gap-2 rounded-lg border px-4 py-3 shadow-lg transition-all',
            toast.type === 'success' && 'border-green-200 bg-green-50 text-green-800',
            toast.type === 'error' && 'border-red-200 bg-red-50 text-red-800',
            toast.type === 'info' && 'border-border bg-white text-text'
          )}
        >
          {toast.type === 'success' && <CheckCircle className="h-4 w-4 shrink-0" />}
          {toast.type === 'error' && <XCircle className="h-4 w-4 shrink-0" />}
          {toast.type === 'info' && <Info className="h-4 w-4 shrink-0" />}
          <span className="text-sm font-medium">{toast.message}</span>
          <button
            onClick={() => removeToast(toast.id)}
            className="ml-2 rounded p-0.5 hover:bg-black/5"
            aria-label="Dismiss"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      ))}
    </div>
  )
}
