import { Loader2 } from 'lucide-react'

export function SuspenseFallback() {
  return (
    <div className="flex h-[60vh] items-center justify-center">
      <div className="flex flex-col items-center gap-3">
        <Loader2 className="h-8 w-8 animate-spin text-[#6b6b6b]" />
        <p className="text-sm text-[#6b6b6b]">Loading...</p>
      </div>
    </div>
  )
}
