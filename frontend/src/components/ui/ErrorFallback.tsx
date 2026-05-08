import { AlertTriangle, RotateCcw, Home } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

interface ErrorFallbackProps {
  error: Error | null
  context?: string
  onReset?: () => void
}

export function ErrorFallback({ error, context, onReset }: ErrorFallbackProps) {
  const navigate = useNavigate()

  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center px-6 py-12">
      <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-red-50">
        <AlertTriangle className="h-8 w-8 text-red-500" />
      </div>

      <h2 className="mb-2 text-xl font-semibold text-[#37352f]">
        Something went wrong
      </h2>

      {context && (
        <p className="mb-4 text-sm text-[#6b6b6b]">
          Error in: <span className="font-medium">{context}</span>
        </p>
      )}

      {error?.message && (
        <div className="mb-6 max-w-md rounded-lg bg-[#f7f6f3] px-4 py-3 text-sm text-[#6b6b6b]">
          <code className="break-all font-mono text-xs">{error.message}</code>
        </div>
      )}

      <div className="flex gap-3">
        {onReset && (
          <button
            onClick={onReset}
            className="inline-flex items-center gap-2 rounded-lg bg-[#2d2d2d] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#1a1a1a]"
          >
            <RotateCcw className="h-4 w-4" />
            Try Again
          </button>
        )}

        <button
          onClick={() => navigate('/')}
          className="inline-flex items-center gap-2 rounded-lg border border-[#e9e9e7] bg-white px-4 py-2 text-sm font-medium text-[#37352f] transition-colors hover:bg-[#f7f6f3]"
        >
          <Home className="h-4 w-4" />
          Go Home
        </button>
      </div>
    </div>
  )
}
