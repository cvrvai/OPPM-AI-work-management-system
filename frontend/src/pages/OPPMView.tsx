/**
 * OPPMView — minimal scaffold workspace.
 *
 * This phase intentionally removes the current OPPM feature flows
 * (saved template loading, AI fill, download/export, guide/tool controls)
 * to focus on rebuilding layout structure step-by-step.
 */

import React, { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Loader2 } from 'lucide-react'
import { Workbook } from '@fortune-sheet/react'
import '@fortune-sheet/react/dist/index.css'
import { useWorkspaceNavGuard } from '@/hooks/useWorkspaceNavGuard'
import { buildOppmScratchSheet } from '@/lib/oppmSheetBuilder'

// ══════════════════════════════════════════════════════════════
// OPPMView
// ══════════════════════════════════════════════════════════════
export function OPPMView() {
  const { id } = useParams<{ id: string }>()

  // Keep workspace-switch guard active while the page is simplified.
  useWorkspaceNavGuard()

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const sheetDataRef = useRef<any[] | null>(null)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const sheetRef = useRef<any>(null)
  const [sheetKey, setSheetKey] = useState(0)

  // Always mount the generated scaffold sheet for this phase.
  useEffect(() => {
    sheetDataRef.current = buildOppmScratchSheet()
    setSheetKey((k) => k + 1)
  }, [id])

  const hasSheet = !!(sheetDataRef.current && sheetDataRef.current.length > 0)

  return (
    <div className="font-['Inter',system-ui,sans-serif]">
      <div className="sticky top-0 z-30 bg-white border-b border-gray-200 shadow-sm -mx-4 sm:-mx-6 px-4 sm:px-6">
        <div className="flex items-center gap-2 py-2">
          <Link
            to={`/projects/${id}`}
            className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500 hover:text-gray-800 transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>

          <div className="min-w-0 flex-1">
            <p className="text-[9px] font-bold uppercase tracking-widest text-gray-400">
              One Page Project Manager
            </p>
            <h1 className="text-sm font-bold text-gray-900 truncate">OPPM Layout Scaffold</h1>
          </div>
        </div>
      </div>

      <div className="mt-3">
        {hasSheet ? (
          <div
            className="bg-white border border-gray-300 rounded-lg overflow-hidden"
            style={{ height: 'calc(100vh - 116px)', minHeight: 500 }}
          >
            <Workbook
              key={sheetKey}
              ref={sheetRef}
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              data={sheetDataRef.current as any[]}
              allowEdit={false}
              showToolbar={false}
              onChange={() => {}}
              onOp={() => {}}
            />
          </div>
        ) : (
          <div className="flex items-center justify-center py-24 gap-3">
            <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
            <span className="text-sm text-gray-500">Loading OPPM scaffold…</span>
          </div>
        )}
      </div>
    </div>
  )
}
