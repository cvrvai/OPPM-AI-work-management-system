/**
 * OPPMView — FortuneSheet-based interactive OPPM spreadsheet
 *
 * Each project stores its own OPPM template (sheet_data) in the backend.
 * On first visit the bundled default XLSX is auto-loaded, converted to
 * FortuneSheet JSON, persisted, and displayed interactively.
 * Users can replace it at any time by importing a new XLSX file.
 *
 * Workspace / project switching is handled with a synchronous ref-reset
 * to prevent FortuneSheet from briefly rendering stale data and crashing.
 */

import React, { useState, useRef, useCallback, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api, ApiError } from '@/lib/api'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import {
  ArrowLeft, Loader2, Check, Download, Upload, X, AlertTriangle, RotateCcw, Sparkles,
} from 'lucide-react'
import { useChatContext } from '@/hooks/useChatContext'
import { useWorkspaceNavGuard } from '@/hooks/useWorkspaceNavGuard'
import { Workbook } from '@fortune-sheet/react'
import '@fortune-sheet/react/dist/index.css'
import { transformExcelToFortune } from '@corbe30/fortune-excel'
import defaultTemplateUrl from '@/assets/OPPM Template (1).xlsx?url'

// ══════════════════════════════════════════════════════════════
// OPPMView
// ══════════════════════════════════════════════════════════════
export function OPPMView() {
  const { id }  = useParams<{ id: string }>()
  const qc      = useQueryClient()
  const ws      = useWorkspaceStore(s => s.currentWorkspace)
  const wsPath  = ws ? `/v1/workspaces/${ws.id}` : ''

  // Redirect to /projects when workspace changes — prevents cross-workspace 404s
  useWorkspaceNavGuard()

  // ── Project title (selected from cached projects list — never causes 404) ─
  const { data: projectTitle = 'OPPM' } = useQuery<{ id: string; title: string }[], Error, string>({
    queryKey: ['projects', ws?.id],
    queryFn: async () => {
      const res = await api.get<{ items: { id: string; title: string }[] }>(`${wsPath}/projects`)
      return res.items ?? []
    },
    select: (projects) => projects.find(p => p.id === id)?.title ?? 'OPPM',
    enabled: !!(ws?.id && id),
    staleTime: 5 * 60 * 1000,
  })
  useChatContext('project', id, projectTitle)

  // ── Spreadsheet state ──────────────────────────────────
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const sheetDataRef   = useRef<any[] | null>(null)
  const [sheetKey, setSheetKey]             = useState(0)
  const [sheetFileName, setSheetFileName]   = useState<string | null>(null)
  const [sheetSaving, setSheetSaving]       = useState(false)
  const [sheetSaved, setSheetSaved]         = useState(false)
  const [hasUnsaved, setHasUnsaved]         = useState(false)
  const [autoLoading, setAutoLoading]       = useState(false)
  const [aiFilling, setAiFilling]           = useState(false)
  const [aiFillError, setAiFillError]       = useState<string | null>(null)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const sheetRef     = useRef<any>(null)
  // isLoadedRef: true once data is set into the Workbook — prevents background
  // refetches from re-mounting the Workbook while the user is editing.
  const isLoadedRef   = useRef(false)
  // hasInteractedRef: true after the first user op — FortuneSheet fires onChange
  // immediately on mount with a normalised version of the data (may strip content).
  // We skip onChange until the user actually changes something.
  const hasInteractedRef = useRef(false)

  // ── Import state ────────────────────────────────────────
  const [importing, setImporting]     = useState(false)
  const [importError, setImportError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // ── Synchronous reset when project / workspace changes ─
  // Must happen before JSX evaluates sheetDataRef.current to prevent
  // FortuneSheet briefly rendering stale data and throwing an error.
  const projectKey = `${id ?? ''}-${ws?.id ?? ''}`
  const prevKeyRef = useRef(projectKey)
  if (prevKeyRef.current !== projectKey) {
    prevKeyRef.current   = projectKey
    sheetDataRef.current = null   // clear immediately — no stale render
  }

  // Async cleanup (state reset) after project / workspace change
  useEffect(() => {
    sheetDataRef.current = null
    isLoadedRef.current      = false
    hasInteractedRef.current = false
    setSheetKey(k => k + 1)
    setSheetFileName(null)
    setAutoLoading(false)
    setSheetSaving(false)
    setSheetSaved(false)
    setHasUnsaved(false)
    setAiFilling(false)
    setAiFillError(null)
    setImportError(null)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, ws?.id])

  // ── Spreadsheet query ──────────────────────────────────
  const spreadsheetQKey = ['oppm-spreadsheet', id, ws?.id] as const
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const { data: spreadsheetData, isLoading: ssLoading } = useQuery<{ sheet_data: any[]; file_name: string | null } | null>({
    queryKey: spreadsheetQKey,
    queryFn: async () => {
      try {
        return await api.get<{ sheet_data: any[]; file_name: string | null }>(`${wsPath}/projects/${id}/oppm/spreadsheet`)
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) return null
        throw e
      }
    },
    enabled: !!(ws && id),
    staleTime: Infinity,          // never refetch in the background during a session
    refetchOnWindowFocus: false,  // do not remount Workbook when user switches tabs
    retry: false,
  })

  // Sync fetched data into ref — only on first load, never on background refetches
  useEffect(() => {
    if (spreadsheetData?.sheet_data && !isLoadedRef.current) {
      isLoadedRef.current = true
      sheetDataRef.current = spreadsheetData.sheet_data
      setSheetFileName(spreadsheetData.file_name ?? null)
      setSheetKey(k => k + 1)
    }
  }, [spreadsheetData])

  // Auto-load bundled default template when no template is saved.
  // sharedStrings text is parsed by transformExcelToFortune without needing a
  // mounted Workbook. sheetRef is only used (optionally) for setColumnWidth;
  // FortuneSheet also reads config.columnlen from the data prop on mount.
  useEffect(() => {
    if (ssLoading || autoLoading || spreadsheetData?.sheet_data || !ws || !id) return
    let cancelled = false
    ;(async () => {
      setAutoLoading(true)
      try {
        const res = await fetch(defaultTemplateUrl)
        if (!res.ok) { if (!cancelled) setAutoLoading(false); return }
        const blob = await res.blob()
        const file = new File([blob], 'OPPM Template.xlsx', {
          type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        await transformExcelToFortune(file, (sheets: any[]) => {
          if (cancelled) return
          isLoadedRef.current      = true
          hasInteractedRef.current = false  // fresh load — skip first onChange
          sheetDataRef.current     = sheets
          setSheetFileName('OPPM Template.xlsx')
          setSheetKey(k => k + 1)
          // Persist to backend (fire-and-forget)
          const token = localStorage.getItem('access_token') ?? ''
          fetch(`/api${wsPath}/projects/${id}/oppm/spreadsheet`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
            body: JSON.stringify({ sheet_data: sheets, file_name: 'OPPM Template.xlsx' }),
          })
        }, () => {}, sheetRef)
      } catch { /* fallthrough — show error state */ }
      if (!cancelled) setAutoLoading(false)
    })()
    return () => { cancelled = true }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ssLoading, spreadsheetData, ws, id])

  // ── Apply AI fills into sheet celldata ─────────────────
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const applyFillsToSheet = useCallback((fills: Record<string, string | null>) => {
    if (!sheetDataRef.current?.length) return
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const updated = sheetDataRef.current.map((sheet: any) => {
      if (!Array.isArray(sheet.celldata)) return sheet
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const celldata = sheet.celldata.map((cell: any) => {
        const display: string = cell?.v?.m ?? String(cell?.v?.v ?? '')
        const dl = display.toLowerCase()

        let newText: string | null = null
        if (/project leader/i.test(dl) && fills.project_leader)
          newText = `Project Leader: ${fills.project_leader}`
        else if (/project name/i.test(dl) && fills.project_name)
          newText = `Project Name: ${fills.project_name}`
        else if (/project objective/i.test(dl) && fills.project_objective)
          newText = `Project Objective: ${fills.project_objective}`
        else if (/deliverable output/i.test(dl) && fills.deliverable_output)
          newText = `Deliverable Output : ${fills.deliverable_output}`
        else if (/start date/i.test(dl) && fills.start_date)
          newText = `Start Date: ${fills.start_date}`
        else if (/^deadline/i.test(dl) && fills.deadline)
          newText = `Deadline: ${fills.deadline}`

        if (!newText) return cell
        return { ...cell, v: { ...cell.v, v: newText, m: newText } }
      })
      return { ...sheet, celldata }
    })
    sheetDataRef.current = updated
  }, [])

  // ── AI Fill callback ─────────────────────────────────────
  const handleAiFill = useCallback(async () => {
    if (!ws || !id) return
    setAiFilling(true)
    setAiFillError(null)
    try {
      const token = localStorage.getItem('access_token') ?? ''
      const res = await fetch(`/api${wsPath}/projects/${id}/ai/oppm-fill`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({}),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body?.detail ?? `AI service returned ${res.status}`)
      }
      const { fills } = await res.json()
      applyFillsToSheet(fills)
      setHasUnsaved(true)
      setSheetKey(k => k + 1)  // re-render Workbook with updated data
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'AI fill failed'
      setAiFillError(msg)
    } finally {
      setAiFilling(false)
    }
  }, [ws, id, wsPath, applyFillsToSheet])

  // ── Manual save callback ────────────────────────────────
  const saveSheetToBackend = useCallback(async () => {
    if (!ws || !id || !sheetDataRef.current) return
    setSheetSaving(true)
    setSheetSaved(false)
    try {
      await fetch(`/api${wsPath}/projects/${id}/oppm/spreadsheet`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('access_token') ?? ''}`,
        },
        body: JSON.stringify({ sheet_data: sheetDataRef.current, file_name: sheetFileName }),
      })
      setHasUnsaved(false)
      setSheetSaved(true)
      setTimeout(() => setSheetSaved(false), 2000)
    } finally {
      setSheetSaving(false)
    }
  }, [ws, id, wsPath, sheetFileName])

  // ── Import XLSX ─────────────────────────────────────────
  const handleImport = async (file: File) => {
    if (!ws || !id) return
    setImporting(true)
    setImportError(null)
    try {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      await transformExcelToFortune(file, (sheets: any[]) => {
        sheetDataRef.current = sheets
        setSheetFileName(file.name)
        setSheetKey(k => k + 1)
        setHasUnsaved(true)
      }, () => {}, sheetRef)
    } catch {
      setImportError('Failed to parse XLSX file')
    } finally {
      setImporting(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  // ── Reset to default template ───────────────────────────
  const handleResetTemplate = async () => {
    if (!ws || !id) return
    if (!confirm('Reset to the default OPPM template? Your current template will be deleted.')) return
    const token = localStorage.getItem('access_token')
    await fetch(`/api${wsPath}/projects/${id}/oppm/spreadsheet`, {
      method: 'DELETE',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    sheetDataRef.current = null
    setSheetFileName(null)
    setSheetKey(k => k + 1)
    qc.invalidateQueries({ queryKey: spreadsheetQKey })
  }

  // ── Download OPPM export ────────────────────────────────
  const handleDownload = async () => {
    if (!ws || !id) return
    const token = localStorage.getItem('access_token')
    try {
      const res = await fetch(`/api/v1/workspaces/${ws.id}/projects/${id}/oppm/export`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (!res.ok) return
      const blob = await res.blob()
      const url  = URL.createObjectURL(blob)
      const a    = document.createElement('a')
      a.href = url
      a.download = `oppm-${projectTitle ?? id}.xlsx`
      document.body.appendChild(a)
      a.click()
      URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch { /* intentional */ }
  }

  // ── Derived ─────────────────────────────────────────────
  const hasSheet    = !!(sheetDataRef.current && sheetDataRef.current.length > 0)
  const isResolving = ssLoading || autoLoading

  // ════════════════════════════════════════════════════════
  // RENDER
  // ════════════════════════════════════════════════════════
  return (
    <div className="font-['Inter',system-ui,sans-serif]">

      {/* ── Sticky action bar ──────────────────────────────── */}
      <div className="sticky top-0 z-30 bg-white border-b border-gray-200 shadow-sm -mx-4 sm:-mx-6 px-4 sm:px-6">
        <div className="flex flex-wrap items-center gap-2 py-2">
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
            <h1 className="text-sm font-bold text-gray-900 truncate">{projectTitle ?? '…'}</h1>
          </div>

          {/* Import XLSX */}
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={importing}
            className="inline-flex items-center gap-1.5 rounded-lg border border-blue-300 bg-blue-50 px-3 py-1.5 text-xs font-semibold text-blue-700 hover:bg-blue-100 shadow-sm transition-colors disabled:opacity-50"
            title="Replace template with a new XLSX file"
          >
            {importing
              ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
              : <Upload className="h-3.5 w-3.5" />}
            Import XLSX
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".xlsx"
            className="hidden"
            onChange={e => {
              const f = e.target.files?.[0]
              if (f) handleImport(f)
            }}
          />

          {/* AI Fill */}
          {hasSheet && (
            <button
              onClick={handleAiFill}
              disabled={aiFilling}
              className="inline-flex items-center gap-1.5 rounded-lg border border-violet-300 bg-violet-50 px-3 py-1.5 text-xs font-semibold text-violet-700 hover:bg-violet-100 shadow-sm transition-colors disabled:opacity-50"
              title="Use AI to fill in project name, leader, dates, objective and deliverable output"
            >
              {aiFilling
                ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                : <Sparkles className="h-3.5 w-3.5" />}
              {aiFilling ? 'Filling…' : 'AI Fill'}
            </button>
          )}

          {/* Download */}
          <button
            onClick={handleDownload}
            className="inline-flex items-center gap-1.5 rounded-lg bg-blue-700 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-800 shadow-sm transition-colors"
          >
            <Download className="h-3.5 w-3.5" />
            Download OPPM
          </button>

          {/* Reset to default template */}
          {hasSheet && (
            <button
              onClick={handleResetTemplate}
              className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-xs font-semibold text-gray-600 hover:bg-gray-50 shadow-sm transition-colors"
              title="Reset to default OPPM template"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              Reset
            </button>
          )}

          {/* Manual save button */}
          {hasSheet && (
            <button
              onClick={saveSheetToBackend}
              disabled={sheetSaving || !hasUnsaved}
              className="inline-flex items-center gap-1.5 rounded-lg border border-green-300 bg-green-50 px-3 py-1.5 text-xs font-semibold text-green-700 hover:bg-green-100 shadow-sm transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              title={hasUnsaved ? 'Save changes to server' : 'No unsaved changes'}
            >
              {sheetSaving
                ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                : sheetSaved
                  ? <Check className="h-3.5 w-3.5" />
                  : <Check className="h-3.5 w-3.5" />}
              {sheetSaving ? 'Saving…' : sheetSaved ? 'Saved' : 'Save'}
            </button>
          )}
        </div>
      </div>

      {/* AI fill error banner ───────────────────────────── */}
      {aiFillError && (
        <div className="mt-2 -mx-4 sm:-mx-6 px-4 sm:px-6">
          <div className="flex items-start gap-2 rounded-lg bg-amber-50 border border-amber-200 px-4 py-2.5">
            <AlertTriangle className="h-4 w-4 text-amber-500 mt-0.5 shrink-0" />
            <p className="flex-1 text-xs text-amber-800">{aiFillError}</p>
            <button onClick={() => setAiFillError(null)} className="text-amber-400 hover:text-amber-600">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* Import error banner ──────────────────────────── */}
      {importError && (
        <div className="mt-2 -mx-4 sm:-mx-6 px-4 sm:px-6">
          <div className="flex items-start gap-2 rounded-lg bg-red-50 border border-red-200 px-4 py-2.5">
            <AlertTriangle className="h-4 w-4 text-red-500 mt-0.5 shrink-0" />
            <p className="flex-1 text-xs text-red-800">{importError}</p>
            <button onClick={() => setImportError(null)} className="text-red-400 hover:text-red-600">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* ── Main content ─────────────────────────────────── */}
      {/* keyed by projectKey — ensures FortuneSheet fully unmounts on switch */}
      <div key={projectKey} className="mt-3">
        {isResolving ? (
          <div className="flex items-center justify-center py-24 gap-3">
            <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
            <span className="text-sm text-gray-500">Loading OPPM spreadsheet…</span>
          </div>
        ) : hasSheet ? (
          <div
            className="bg-white border border-gray-300 rounded-lg overflow-hidden"
            style={{ height: 'calc(100vh - 116px)', minHeight: 500 }}
          >
            <Workbook
              key={sheetKey}
              ref={sheetRef}
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              data={sheetDataRef.current as any[]}
              onChange={(data: any) => {
                // Skip the first onChange that FortuneSheet fires on mount.
                // That emission can be a normalised/stripped version of the data
                // which would corrupt sheetDataRef and cause empty saves.
                if (!hasInteractedRef.current) return
                sheetDataRef.current = data
              }}
              onOp={() => {
                hasInteractedRef.current = true  // first real user interaction
                setHasUnsaved(true)              // mark as having unsaved changes
              }}
            />
          </div>
        ) : (
          // Auto-load failed
          <div className="flex flex-col items-center justify-center py-24 gap-4">
            <p className="text-sm text-gray-500">Failed to load the OPPM template.</p>
            <button
              onClick={() => {
                sheetDataRef.current = null
                setAutoLoading(false)
                qc.invalidateQueries({ queryKey: spreadsheetQKey })
              }}
              className="inline-flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              <RotateCcw className="h-4 w-4" />
              Try again
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

