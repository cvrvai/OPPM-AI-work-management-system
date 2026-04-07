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
  ArrowLeft, Loader2, Check, Download, Upload, X, AlertTriangle, RotateCcw, Sparkles, Info, ChevronDown, ChevronUp,
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
  const [showGuide, setShowGuide]     = useState(false)
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
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      sheetDataRef.current = spreadsheetData.sheet_data.map((s: any) => ({ ...s, scrollTop: 0, scrollLeft: 0 }))
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
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const normalized = sheets.map((s: any) => ({ ...s, scrollTop: 0, scrollLeft: 0 }))
          isLoadedRef.current      = true
          hasInteractedRef.current = false  // fresh load — skip first onChange
          sheetDataRef.current     = normalized
          setSheetFileName('OPPM Template.xlsx')
          setSheetKey(k => k + 1)
          // Persist to backend (fire-and-forget)
          const token = localStorage.getItem('access_token') ?? ''
          fetch(`/api${wsPath}/projects/${id}/oppm/spreadsheet`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
            body: JSON.stringify({ sheet_data: normalized, file_name: 'OPPM Template.xlsx' }),
          })
        }, () => {}, sheetRef)
      } catch { /* fallthrough — show error state */ }
      if (!cancelled) setAutoLoading(false)
    })()
    return () => { cancelled = true }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ssLoading, spreadsheetData, ws, id])

  // ── Extract display text from a cell (handles rich text inline strings) ──
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const getCellText = (cell: any): string => {
    // Rich text / inline string: concatenate all segment values
    if (cell?.v?.ct?.t === 'inlineStr' && Array.isArray(cell.v.ct.s)) {
      return cell.v.ct.s.reduce((acc: string, seg: any) => acc + (seg.v ?? ''), '')
    }
    return (cell?.v?.m ?? String(cell?.v?.v ?? '')).trim()
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const setPlainText = (cell: any, text: string) => {
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const { ct, ...rest } = cell.v ?? {}
    return { ...cell, v: { ...rest, v: text, m: text } }
  }

  // ── Apply AI fills into sheet celldata ─────────────────
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const applyFillsToSheet = useCallback((
    fills: Record<string, string | null>,
    tasks: { index: string; title: string; deadline: string | null; is_sub: boolean }[],
    members: { slot: number; name: string }[],
  ) => {
    if (!sheetDataRef.current?.length) return

    // ── Task placeholder pattern:
    //   Combined (number + text in one cell): "1. Main task 1", "  1.1 Sub task 1"
    //   Text-only (number in separate left cell): "Sub task 1", "Main task 2"
    const taskPlaceholderRe = /(?:^\s*\d+[\d.]*\s+)?(main task|sub task)\s*\d+/i
    const hasNumPrefix = (text: string) => /^\s*\d+[\d.]*\s+(main task|sub task)/i.test(text)

    // ── Owner column header pattern: single letter A/B/C or "Primary/Owner"
    const ownerColRe = /^[A-C]$|^Primary\/Owner$/i

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const updated = sheetDataRef.current.map((sheet: any) => {
      if (!Array.isArray(sheet.celldata)) return sheet

      // Collect task placeholder cells in row-then-col order so we can replace by index
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const taskCells: { idx: number; cell: any }[] = []
      sheet.celldata.forEach((cell: any, idx: number) => {
        if (taskPlaceholderRe.test(getCellText(cell))) taskCells.push({ idx, cell })
      })
      // Sort by row then column
      taskCells.sort((a, b) => {
        const ra = a.cell.r ?? 0, rb = b.cell.r ?? 0
        if (ra !== rb) return ra - rb
        return (a.cell.c ?? 0) - (b.cell.c ?? 0)
      })

      // Collect owner column header cells (A, B, C, Primary/Owner)
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const ownerHeaderCells: { idx: number; cell: any }[] = []
      sheet.celldata.forEach((cell: any, idx: number) => {
        if (ownerColRe.test(getCellText(cell).trim())) ownerHeaderCells.push({ idx, cell })
      })
      ownerHeaderCells.sort((a, b) => (a.cell.c ?? 0) - (b.cell.c ?? 0))

      // Build mutable copy of celldata
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const celldata: any[] = sheet.celldata.map((cell: any) => {
        const display = getCellText(cell)
        const dl = display.toLowerCase()

        // ── Multi-line merged cell (all 4 text fields in one cell) ──────
        if (/project objective/i.test(dl) && /deliverable output/i.test(dl)) {
          let newText = display
          if (fills.project_objective)
            newText = newText.replace(/Project Objective:.*?(?=\n|$)/i, `Project Objective: ${fills.project_objective}`)
          if (fills.deliverable_output)
            newText = newText.replace(/Deliverable Output\s*:.*?(?=\n|$)/i, `Deliverable Output : ${fills.deliverable_output}`)
          if (fills.start_date)
            newText = newText.replace(/Start Date:.*?(?=\n|$)/i, `Start Date: ${fills.start_date}`)
          if (fills.deadline)
            newText = newText.replace(/Deadline:.*?(?=\n|$)/i, `Deadline: ${fills.deadline}`)
          if (newText === display) return cell
          return setPlainText(cell, newText)
        }

        // ── Single-field header cells ────────────────────────────────────
        let newText: string | null = null
        if (/project leader/i.test(dl) && fills.project_leader)
          newText = `Project Leader: ${fills.project_leader}`
        else if (/project name/i.test(dl) && fills.project_name)
          newText = `Project Name: ${fills.project_name}`

        if (!newText) return cell
        return setPlainText(cell, newText)
      })

      // ── Fill task placeholder rows in order ──────────────────
      taskCells.forEach(({ idx }, i) => {
        const task = tasks[i]
        if (!task) return
        const indent = task.is_sub ? '   ' : ''
        const deadline = task.deadline ? `  (${task.deadline})` : ''
        const originalText = getCellText(celldata[idx])
        // If number prefix is in a separate left cell, write title only; otherwise write full label
        const text = hasNumPrefix(originalText)
          ? `${indent}${task.index}  ${task.title}${deadline}`
          : `${indent}${task.title}${deadline}`
        celldata[idx] = setPlainText(celldata[idx], text)
      })

      // ── Fill owner column headers with member names ───────────
      ownerHeaderCells.forEach(({ idx }, i) => {
        const m = members.find(mb => mb.slot === i)
        if (!m) return
        celldata[idx] = setPlainText(celldata[idx], m.name)
      })

      return { ...sheet, celldata, scrollTop: 0, scrollLeft: 0 }
    })
    sheetDataRef.current = updated
  // eslint-disable-next-line react-hooks/exhaustive-deps
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
      const { fills, tasks = [], members = [] } = await res.json()
      applyFillsToSheet(fills, tasks, members)
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
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        sheetDataRef.current = sheets.map((s: any) => ({ ...s, scrollTop: 0, scrollLeft: 0 }))
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
              title="AI fills: Project Name, Leader, Objective, Deliverable Output, Start Date, Deadline"
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
            title="Download auto-generated OPPM report with all objectives, tasks, timeline, owners, costs, and risks from database"
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

      {/* ── How-to guide (collapsible) ──────────────────── */}
      <div className="mt-2 -mx-4 sm:-mx-6 px-4 sm:px-6">
        <button
          onClick={() => setShowGuide(g => !g)}
          className="flex w-full items-center gap-2 rounded-lg border border-indigo-200 bg-indigo-50/60 px-4 py-2 text-left transition-colors hover:bg-indigo-50"
        >
          <Info className="h-4 w-4 text-indigo-500 shrink-0" />
          <span className="flex-1 text-xs font-semibold text-indigo-700">How to use this OPPM view</span>
          {showGuide
            ? <ChevronUp className="h-3.5 w-3.5 text-indigo-400" />
            : <ChevronDown className="h-3.5 w-3.5 text-indigo-400" />}
        </button>
        {showGuide && (
          <div className="mt-1 rounded-lg border border-indigo-200 bg-white px-4 py-3 space-y-3">
            <div>
              <p className="text-xs font-bold text-indigo-800 mb-1">📝 This spreadsheet is your editable OPPM template</p>
              <p className="text-[11px] text-gray-600">You can type directly into any cell. The template shows placeholder text like "Main task 1", "Sub task 1" — replace them with your actual project tasks.</p>
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="rounded-lg bg-violet-50 border border-violet-200 p-3">
                <p className="text-xs font-bold text-violet-800 flex items-center gap-1.5"><Sparkles className="h-3.5 w-3.5" /> AI Fill</p>
                <p className="text-[11px] text-violet-700 mt-1">Auto-fills: <strong>Project Name</strong>, <strong>Project Leader</strong>, <strong>Objective</strong>, <strong>Deliverable Output</strong>, <strong>Start Date</strong>, and <strong>Deadline</strong> from your project data. Click it after setting up the project details.</p>
              </div>
              <div className="rounded-lg bg-blue-50 border border-blue-200 p-3">
                <p className="text-xs font-bold text-blue-800 flex items-center gap-1.5"><Download className="h-3.5 w-3.5" /> Download OPPM</p>
                <p className="text-[11px] text-blue-700 mt-1">Generates a <strong>complete OPPM report</strong> from your database: objectives, tasks (main + sub), timeline dots, owner priorities, costs, deliverables, risks — all auto-populated.</p>
              </div>
            </div>
            <div>
              <p className="text-xs font-bold text-gray-700 mb-1">Recommended workflow:</p>
              <ol className="text-[11px] text-gray-600 space-y-0.5 list-decimal list-inside">
                <li>Go to <strong>Project Detail</strong> → create <strong>Objectives</strong>, <strong>Main Tasks</strong>, and <strong>Sub-Tasks</strong></li>
                <li>Come back here → click <strong>AI Fill</strong> to populate the template header</li>
                <li>Edit the spreadsheet cells directly to customize the layout</li>
                <li>Click <strong>Save</strong> to preserve your edits</li>
                <li>Click <strong>Download OPPM</strong> anytime to get a full auto-generated report</li>
              </ol>
            </div>
          </div>
        )}
      </div>

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

