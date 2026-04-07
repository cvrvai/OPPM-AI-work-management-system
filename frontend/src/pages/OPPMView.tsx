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
  ArrowLeft, Loader2, Download, X, AlertTriangle, RotateCcw, Sparkles, Info, ChevronDown, ChevronUp, ChevronLeft, ChevronRight,
} from 'lucide-react'
import { useChatContext } from '@/hooks/useChatContext'
import { useWorkspaceNavGuard } from '@/hooks/useWorkspaceNavGuard'
import { Workbook } from '@fortune-sheet/react'
import '@fortune-sheet/react/dist/index.css'
import { transformExcelToFortune } from '@corbe30/fortune-excel'
import defaultTemplateUrl from '@/assets/OPPM Template (1).xlsx?url'

type OPPMFillPriority = 'A' | 'B' | 'C'
type OPPMFillTimelineStatus = 'planned' | 'in_progress' | 'completed' | 'at_risk' | 'blocked'
type OPPMFillTimelineQuality = 'good' | 'average' | 'bad'

type OPPMFillMap = Record<string, string | null>

type OPPMFillOwner = {
  member_id: string
  priority: OPPMFillPriority
}

type OPPMFillTimeline = {
  week_start: string
  status: OPPMFillTimelineStatus | null
  quality: OPPMFillTimelineQuality | null
}

type OPPMFillTask = {
  index: string
  title: string
  deadline: string | null
  status?: string | null
  is_sub: boolean
  owners?: OPPMFillOwner[]
  timeline?: OPPMFillTimeline[]
}

type OPPMFillMember = {
  id: string
  slot: number
  name: string
}

type OPPMFillPayload = {
  fills: OPPMFillMap
  tasks?: OPPMFillTask[]
  members?: OPPMFillMember[]
}

const TIMELINE_STATUS_SYMBOL: Record<OPPMFillTimelineStatus, string> = {
  planned: '□',
  in_progress: '●',
  completed: '■',
  at_risk: '●',
  blocked: '●',
}

const TIMELINE_STATUS_COLOR: Record<OPPMFillTimelineStatus, string> = {
  planned: '#333333',
  in_progress: '#333333',
  completed: '#333333',
  at_risk: '#D97706',
  blocked: '#DC2626',
}

const TIMELINE_QUALITY_COLOR: Record<OPPMFillTimelineQuality, string> = {
  good: '#166534',
  average: '#D97706',
  bad: '#DC2626',
}

const FALLBACK_COLUMN_WIDTH = 72
const PREVIEW_OWNER_COLUMN_WIDTH = 72
const PREVIEW_LEGEND_COLUMN_WIDTHS = [42, 84, 84, 84]
const PREVIEW_LEGEND_TITLE_ROW_HEIGHT = 24
const PREVIEW_LEGEND_BODY_ROW_HEIGHT = 22
const PREVIEW_MIN_TASK_ROWS = 16

const HORIZONTAL_SCROLL_STEP = 420

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
  // rawSheetRef: immutable snapshot of the clean converted template (set once on load).
  // AI Fill resets sheetDataRef from this before applying fills — makes fill idempotent.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const rawSheetRef    = useRef<any[] | null>(null)
  const [sheetKey, setSheetKey]             = useState(0)
  const [sheetFileName, setSheetFileName]   = useState<string | null>(null)
  const [autoLoading, setAutoLoading]       = useState(false)
  const [aiFilling, setAiFilling]           = useState(false)
  const [aiFillError, setAiFillError]       = useState<string | null>(null)
  const [isFilled, setIsFilled]             = useState(false)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const sheetRef     = useRef<any>(null)
  const layoutNormalizedRef = useRef(false)
  // isLoadedRef: true once data is set into the Workbook — prevents background
  // refetches from re-mounting the Workbook while the user is editing.
  const isLoadedRef   = useRef(false)

  // ── Guide state ─────────────────────────────────────────
  const [showGuide, setShowGuide]     = useState(false)

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
    rawSheetRef.current  = null
    isLoadedRef.current  = false
    setSheetKey(k => k + 1)
    setSheetFileName(null)
    setAutoLoading(false)
    setAiFilling(false)
    setAiFillError(null)
    setIsFilled(false)
    layoutNormalizedRef.current = false
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
      const normalized = spreadsheetData.sheet_data.map((s: any) => ({ ...s, scrollTop: 0, scrollLeft: 0 }))
      sheetDataRef.current = normalized
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

  // ── Always load blank XLSX template into rawSheetRef ───────────────────
  // rawSheetRef is the reset point for AI Fill. It must always be the BLANK default
  // template, NOT the backend's stored sheet_data (which may already be filled).
  // This effect runs on every project/workspace change independently of display data.
  useEffect(() => {
    if (!ws || !id) return
    let cancelled = false
    ;(async () => {
      try {
        const res = await fetch(defaultTemplateUrl)
        if (!res.ok || cancelled) return
        const blob = await res.blob()
        const file = new File([blob], 'OPPM Template.xlsx', {
          type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        await transformExcelToFortune(file, (sheets: any[]) => {
          if (cancelled) return
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          rawSheetRef.current = (sheets as any[]).map((s: any) => ({ ...s, scrollTop: 0, scrollLeft: 0 }))
        }, () => {}, sheetRef)
      } catch { /* ignore — rawSheetRef stays as-is */ }
    })()
    return () => { cancelled = true }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, ws?.id])

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
  const setPlainText = (cell: any, text: string, overrides: Record<string, unknown> = {}) => {
    const value = { ...(cell.v ?? {}) }
    delete value.ct
    return { ...cell, v: { ...value, v: text, m: text, ...overrides } }
  }

  const getTimelineMarker = (status?: string | null, quality?: string | null) => {
    const statusKey: OPPMFillTimelineStatus =
      status === 'in_progress' || status === 'completed' || status === 'at_risk' || status === 'blocked'
        ? status
        : 'planned'
    const color =
      quality === 'good' || quality === 'average' || quality === 'bad'
        ? TIMELINE_QUALITY_COLOR[quality]
        : TIMELINE_STATUS_COLOR[statusKey]
    return { symbol: TIMELINE_STATUS_SYMBOL[statusKey], color }
  }

  // ── Apply AI fills into sheet celldata ─────────────────
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const applyFillsToSheet = useCallback((
    fills: OPPMFillMap,
    tasks: OPPMFillTask[],
    members: OPPMFillMember[],
  ) => {
    if (!sheetDataRef.current?.length) return

    // ── Owner column header pattern: matches the OPPM template's member label cells
    // ("Project Leader", "Member 1", etc. plus legacy "Primary/Owner" labels)
    const ownerColRe = /^Project\s*Leader$|^Primary\s*\/\s*Owner$|^Member\s*\d+$|^Primary\s*Helper$|^Secondary\s*Helper$/i

    // ── Timeline columns M–AC (0-indexed 12–28), 17 slots ────
    const TL_COL_START = 12   // Excel col M
    const TL_COL_END   = 28   // Excel col AC
    const TL_COL_COUNT = TL_COL_END - TL_COL_START + 1  // 17

    // Parse ISO date string ("YYYY-MM-DD") → Date | null
    const parseISODate = (s: string | null | undefined): Date | null => {
      if (!s) return null
      const d = new Date(s)
      return isNaN(d.getTime()) ? null : d
    }

    // Build 17 evenly-spaced dates across the project timeline
    const projStart    = parseISODate(fills.start_date)
    const projDeadline = parseISODate(fills.deadline)
    const timelineDates: (Date | null)[] = Array(TL_COL_COUNT).fill(null)
    if (projStart && projDeadline) {
      const totalMs = projDeadline.getTime() - projStart.getTime()
      for (let i = 0; i < TL_COL_COUNT; i++) {
        const frac = i / (TL_COL_COUNT - 1)
        timelineDates[i] = new Date(projStart.getTime() + frac * totalMs)
      }
    }

    // col index → Date map (only populated when project dates are known)
    const colToDate = new Map<number, Date>()
    timelineDates.forEach((d, i) => { if (d) colToDate.set(TL_COL_START + i, d) })

    // Short date label: "16-Feb-26"
    const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    const fmtDate = (d: Date): string =>
      `${d.getDate()}-${MONTHS[d.getMonth()]}-${String(d.getFullYear()).slice(-2)}`

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const updated = sheetDataRef.current.map((sheet: any) => {
      if (!Array.isArray(sheet.celldata)) return sheet

      // Collect owner column header cells (A, B, C, Primary/Owner)
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const ownerHeaderCells: { idx: number; cell: any }[] = []
      sheet.celldata.forEach((cell: any, idx: number) => {
        if (ownerColRe.test(getCellText(cell).trim())) ownerHeaderCells.push({ idx, cell })
      })
      ownerHeaderCells.sort((a, b) => (a.cell.c ?? 0) - (b.cell.c ?? 0))
      const ownerColumnIndexes = Array.from(new Set(ownerHeaderCells.map(({ cell }) => cell.c))).sort((a, b) => a - b)

      // Build mutable copy of celldata
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const celldata: any[] = sheet.celldata.map((cell: any) => {
        const display = getCellText(cell)
        const dl = display.toLowerCase()

        // ── Update timeline date-header cells (Excel serial in cols 12–28) ──
        // After fortune-excel conversion, date serials may be stored as number in v.v,
        // or as a string in v.m (showing "44454.0"). Detect by display text pattern.
        if (colToDate.size > 0 && cell.c >= TL_COL_START && cell.c <= TL_COL_END) {
          const serialStr = display.trim()
          const serialNum = parseFloat(serialStr)
          const isRawSerial = (
            /^\d{5}(\.\d*)?$/.test(serialStr) && !isNaN(serialNum) &&
            serialNum > 40000 && serialNum < 80000
          ) || (
            typeof cell?.v?.v === 'number' && cell.v.v > 40000 && cell.v.v < 80000
          )
          if (isRawSerial) {
            const newDate = timelineDates[cell.c - TL_COL_START]
            if (newDate) return setPlainText(cell, fmtDate(newDate))
          }
        }

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
        else if (/project completed by/i.test(dl)) {
          const completedBy = (fills.completed_by_text ?? fills.deadline ?? '').trim()
          if (completedBy) newText = `Project Completed By: ${completedBy}`
        } else if (/people working on the project/i.test(dl)) {
          const peopleCount = (fills.people_count ?? '').trim()
          if (peopleCount) newText = `# People working on the project: ${peopleCount}`
        }

        if (!newText) return cell
        return setPlainText(cell, newText)
      })

      // ── Find Major Tasks column by locating its header cell ──────────────
      // Uses the topmost "Major Tasks" cell — the header never changes during fills,
      // so this is robust even when task rows have been filled/overwritten before.
      let taskCol = 8           // fallback: col I (0-indexed)
      let taskHeaderRow = Infinity as number
      sheet.celldata.forEach((cell: any) => {
        if (/^Major Tasks/i.test(getCellText(cell)) && cell.r < taskHeaderRow) {
          taskCol = cell.c
          taskHeaderRow = cell.r
        }
      })
      if (taskHeaderRow === Infinity) taskHeaderRow = 4  // fallback: Excel row 5

      // ── Find the column that contains the "Main task N" placeholder ──────
      // In this template col H has "1. Main task 1" as a single cell (one column
      // left of the "Major Tasks" header); sub-task titles are in col I (taskCol).
      // We scan the first data row to detect the actual main-task content column.
      let mainTaskCol = taskCol - 1   // default: one column left of header
      sheet.celldata.forEach((cell: any) => {
        if (cell.r === taskHeaderRow + 1 && /main task/i.test(getCellText(cell))) {
          mainTaskCol = cell.c
        }
      })

      // ── Position index (row,col → celldata index) ──────────────────────
      const posIndex = new Map<string, number>()
      celldata.forEach((cell: any, idx: number) => posIndex.set(`${cell.r},${cell.c}`, idx))

      // Helper: upsert a cell by (r,c) position
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const upsertCell = (r: number, c: number, newCell: any) => {
        const key = `${r},${c}`
        if (posIndex.has(key)) {
          celldata[posIndex.get(key)!] = newCell
        } else {
          posIndex.set(key, celldata.length)
          celldata.push(newCell)
        }
      }

      const ensureCell = (r: number, c: number) => {
        const key = `${r},${c}`
        const existingIdx = posIndex.get(key)
        if (existingIdx !== undefined) return celldata[existingIdx]

        const newCell = { r, c, v: {} }
        posIndex.set(key, celldata.length)
        celldata.push(newCell)
        return newCell
      }

      // ── Fill task rows positionally ─────────────────────────────────────
      // Objectives (is_sub=false) → mainTaskCol (col H: "1. Main task 1" template cell)
      // Sub-tasks  (is_sub=true)  → taskCol     (col I: "Sub task N" template cell)
      tasks.forEach((task, i) => {
        const r = taskHeaderRow + 1 + i
        let targetCol: number
        let text: string
        if (!task.is_sub) {
          // Write to col H (mainTaskCol): replaces "1. Main task 1" with real objective title
          targetCol = mainTaskCol
          text = `${task.index}. ${task.title}`
        } else {
          // Write to col I (taskCol): replaces "Sub task N" with "  Title  (deadline)"
          // The index ("1.1") is already in the template's col H cell — not duplicated here
          targetCol = taskCol
          const deadline = task.deadline ? `  (${task.deadline})` : ''
          text = `  ${task.title}${deadline}`
        }
        const existingIdx = posIndex.get(`${r},${targetCol}`)
        const baseCell = existingIdx !== undefined ? celldata[existingIdx] : { r, c: targetCol, v: {} }
        upsertCell(r, targetCol, setPlainText(baseCell, text))
      })

      // ── Fill owner/member section by label text ───────────────────────
      // The lower-right section has explicit labels like "Project Leader",
      // "Member 1", and legacy "Primary/Owner" helper labels. Use those
      // labels directly so the same columns can also be reused for task A/B/C fills.
      const leaderName = (fills.project_leader ?? '').trim()
      const leaderMemberId = (fills.project_leader_member_id ?? '').trim()
      const namedMembers = members.filter((member) => (member.name ?? '').trim())
      const hasMemberFillData = namedMembers.length > 0 || !!leaderName
      const memberPool = members.filter((mb) => {
        const name = (mb.name ?? '').trim()
        return !!name && mb.id !== leaderMemberId
      })
      const ownerColumns = new Map<string, number>()

      ownerHeaderCells.forEach(({ idx, cell }) => {
        const label = getCellText(cell).trim()

        if (/^Project\s*Leader$/i.test(label) || /^Primary\s*\/\s*Owner$/i.test(label)) {
          if (!leaderName) return
          celldata[idx] = setPlainText(celldata[idx], leaderName)
          if (leaderMemberId && !ownerColumns.has(leaderMemberId)) ownerColumns.set(leaderMemberId, cell.c)
          return
        }

        const memberMatch = label.match(/^Member\s*(\d+)$/i)
        if (memberMatch) {
          const slot = Number(memberMatch[1]) - 1
          const member = memberPool[slot]
          if (!member) return
          celldata[idx] = setPlainText(celldata[idx], member.name)
          if (!ownerColumns.has(member.id)) ownerColumns.set(member.id, cell.c)
          return
        }

        if (/^Primary\s*Helper$/i.test(label)) {
          const member = memberPool[0]
          if (!member) return
          celldata[idx] = setPlainText(celldata[idx], member.name)
          if (!ownerColumns.has(member.id)) ownerColumns.set(member.id, cell.c)
          return
        }

        if (/^Secondary\s*Helper$/i.test(label)) {
          const member = memberPool[1]
          if (!member) return
          celldata[idx] = setPlainText(celldata[idx], member.name)
          if (!ownerColumns.has(member.id)) ownerColumns.set(member.id, cell.c)
        }
      })

      // ── Compact unused owner/member columns in the preview sheet ─────
      const existingVisibleOwners = ownerHeaderCells.reduce((count, { idx }) => {
        const text = getCellText(celldata[idx]).trim()
        return text && !ownerColRe.test(text) ? count + 1 : count
      }, 0)
      const targetVisibleOwnerCount = hasMemberFillData
        ? Math.max(namedMembers.length, leaderName ? 1 : 0)
        : (existingVisibleOwners || ownerColumnIndexes.length)
      const visibleOwnerCount = Math.max(
        1,
        Math.min(
          ownerColumnIndexes.length,
          targetVisibleOwnerCount,
        ),
      )
      const removedOwnerColumns = ownerColumnIndexes.slice(visibleOwnerCount)
      const removedOwnerCount = removedOwnerColumns.length

      // ── Fill task owner priorities (A/B/C) by mapped member columns ─────
      tasks.forEach((task, i) => {
        const r = taskHeaderRow + 1 + i
        ;(task.owners ?? []).forEach((owner) => {
          const col = ownerColumns.get(owner.member_id)
          if (col === undefined) return
          const existingIdx = posIndex.get(`${r},${col}`)
          const baseCell = existingIdx !== undefined ? celldata[existingIdx] : { r, c: col, v: {} }
          upsertCell(r, col, setPlainText(baseCell, owner.priority, {
            fc: '#111111',
            bl: 1,
            ht: 0,
            vt: 0,
          }))
        })
      })

      // ── Place timeline identity markers for each task ──────────────────
      if (colToDate.size > 0) {
        const placeTimelineMarker = (r: number, c: number, status?: string | null, quality?: string | null) => {
          const marker = getTimelineMarker(status, quality)
          const existingIdx = posIndex.get(`${r},${c}`)
          const baseCell = existingIdx !== undefined ? celldata[existingIdx] : { r, c, v: {} }
          upsertCell(r, c, setPlainText(baseCell, marker.symbol, {
            ct: { fa: '@', t: 's' },
            fc: marker.color,
            ht: 0,
            vt: 0,
          }))
        }

        tasks.forEach((task, i) => {
          const r = taskHeaderRow + 1 + i
          const timelineEntries = task.timeline ?? []

          if (timelineEntries.length > 0) {
            timelineEntries.forEach((entry) => {
              const timelineDate = parseISODate(entry.week_start)
              if (!timelineDate) return

              let bestCol = TL_COL_START
              let bestDiff = Infinity
              colToDate.forEach((d, c) => {
                const diff = Math.abs(d.getTime() - timelineDate.getTime())
                if (diff < bestDiff) { bestDiff = diff; bestCol = c }
              })

              placeTimelineMarker(r, bestCol, entry.status, entry.quality)
            })
            return
          }

          if (!task.deadline) return
          const taskDeadline = parseISODate(task.deadline)
          if (!taskDeadline) return

          const fallbackStatus: OPPMFillTimelineStatus =
            task.status === 'completed'
              ? 'completed'
              : task.status === 'in_progress'
                ? 'in_progress'
                : 'planned'

          let bestCol = TL_COL_START
          let bestDiff = Infinity
          colToDate.forEach((d, c) => {
            const diff = Math.abs(d.getTime() - taskDeadline.getTime())
            if (diff < bestDiff) { bestDiff = diff; bestCol = c }
          })

          placeTimelineMarker(r, bestCol, fallbackStatus, null)
        })
      }

      const taskStartRow = taskHeaderRow + 1
      const taskSectionRowCount = Math.max(tasks.length, PREVIEW_MIN_TASK_ROWS)
      const legendStartColumn = (ownerColumnIndexes[ownerColumnIndexes.length - 1] ?? TL_COL_END) + 1
      const legendColumns = Array.from({ length: PREVIEW_LEGEND_COLUMN_WIDTHS.length }, (_, index) => legendStartColumn + index)
      const legendStartCol = legendColumns[0]
      const legendEndCol = legendColumns[legendColumns.length - 1] ?? legendStartColumn
      const legendBodyStartCol = legendColumns[1] ?? legendEndCol
      const legendBlocks = [
        {
          startRow: taskStartRow + 1,
          title: 'Priority',
          titleOverrides: {
            ht: 0,
          },
          rows: [
            ['A', 'Primary'],
            ['B', 'Secondary'],
            ['C', 'Support'],
          ] as Array<[string, string]>,
        },
        {
          startRow: taskStartRow + taskSectionRowCount,
          title: 'Project Identity Symbol',
          titleOverrides: {
            ht: 1,
            fs: 10,
          },
          rows: [
            ['□', 'Start'],
            ['●', 'In Progress'],
            ['■', 'Complete'],
          ] as Array<[string, string]>,
        },
      ]

      const isCellInLegendZone = (r: number, c: number) => legendBlocks.some(({ startRow, rows }) => {
        const endRow = startRow + rows.length
        return r >= startRow && r <= endRow && c >= legendStartCol && c <= legendEndCol
      })

      const doesRangeOverlapLegendZone = (r1: number, r2: number, c1: number, c2: number) => legendBlocks.some(({ startRow, rows }) => {
        const endRow = startRow + rows.length
        return !(r2 < startRow || r1 > endRow || c2 < legendStartCol || c1 > legendEndCol)
      })

      const config = { ...(sheet.config ?? {}) }
      const ownerPriorityHeaderCell = sheet.celldata
        .filter((cell: any) => /Owner\s*\/\s*Priority/i.test(getCellText(cell)))
        .sort((a: any, b: any) => (a.r ?? 0) - (b.r ?? 0))[0]
      const nextMerge = Object.fromEntries(
        Object.entries(config.merge ?? {}).filter(([, merge]) => {
          if (!merge || typeof merge !== 'object') return true
          const mergeInfo = merge as { r: number; c: number; rs?: number; cs?: number }
          const endRow = mergeInfo.r + (mergeInfo.rs ?? 1) - 1
          const endCol = mergeInfo.c + (mergeInfo.cs ?? 1) - 1
          return !doesRangeOverlapLegendZone(mergeInfo.r, endRow, mergeInfo.c, endCol)
        }),
      ) as Record<string, { r: number; c: number; rs: number; cs: number }>
      // Build the mutable border list.
      // Strategy: clip range entries at legendStartCol instead of dropping them entirely.
      // The Excel template stores the Owner/Priority grid and the legend area as ONE combined
      // border-all range. The old filter dropped the whole entry when any part touched the
      // legend zone, wiping all Owner/Priority borders. We now clip the column span to stop
      // just before legendStartCol so the owner grid borders survive.
      const nextBorderInfo: any[] = (Array.isArray(config.borderInfo) ? config.borderInfo : []).flatMap((entry: any) => {
        if (entry?.rangeType === 'cell' && entry.value) {
          // Drop only cell borders that sit inside the legend zone (re-drawn below)
          return isCellInLegendZone(entry.value.row_index, entry.value.col_index) ? [] : [entry]
        }
        if (entry?.rangeType === 'range' && Array.isArray(entry.range)) {
          const clipped = entry.range.flatMap((range: any) => {
            const col = Array.isArray(range?.column) ? range.column as [number, number] : [0, 0] as [number, number]
            if (col[1] < legendStartCol) return [range]                               // fully left of legend – keep
            if (col[0] >= legendStartCol) return [] as typeof entry.range              // fully inside legend – drop
            return [{ ...range, column: [col[0], legendStartCol - 1] }]               // overlaps – clip right edge
          })
          return clipped.length > 0 ? [{ ...entry, range: clipped }] : []
        }
        return [entry]
      })

      const overlappingLegendMergeAnchors = new Set<string>()
      celldata.forEach((cell: any) => {
        const mergeInfo = cell?.mc
        if (!mergeInfo || !('rs' in mergeInfo) || !('cs' in mergeInfo)) return

        const startRow = typeof mergeInfo.r === 'number' ? mergeInfo.r : cell.r
        const startCol = typeof mergeInfo.c === 'number' ? mergeInfo.c : cell.c
        const endRow = startRow + (mergeInfo.rs ?? 1) - 1
        const endCol = startCol + (mergeInfo.cs ?? 1) - 1

        if (doesRangeOverlapLegendZone(startRow, endRow, startCol, endCol)) {
          overlappingLegendMergeAnchors.add(`${startRow},${startCol}`)
        }
      })

      if (overlappingLegendMergeAnchors.size > 0) {
        for (let index = 0; index < celldata.length; index += 1) {
          const cell = celldata[index]
          const mergeInfo = cell?.mc
          if (!mergeInfo) continue

          const anchorRow = typeof mergeInfo.r === 'number' ? mergeInfo.r : cell.r
          const anchorCol = typeof mergeInfo.c === 'number' ? mergeInfo.c : cell.c
          if (!overlappingLegendMergeAnchors.has(`${anchorRow},${anchorCol}`)) continue

          const nextCell = { ...cell }
          delete nextCell.mc
          celldata[index] = nextCell
        }
      }

      const clearLegendBlock = (startRow: number, rowCount: number) => {
        const endRow = startRow + rowCount
        for (let row = startRow; row <= endRow; row += 1) {
          for (let column = legendStartCol; column <= legendEndCol; column += 1) {
            const baseCell = { ...ensureCell(row, column) }
            delete baseCell.mc
            upsertCell(row, column, setPlainText(baseCell, '', {
              bg: '#FFFFFF',
              fc: '#111111',
              ht: 0,
              vt: 0,
            }))
          }
        }
      }

      const setMergeRegion = (startRow: number, startCol: number, endRow: number, endCol: number) => {
        const rs = endRow - startRow + 1
        const cs = endCol - startCol + 1
        const topLeftCell = { ...ensureCell(startRow, startCol) }
        upsertCell(startRow, startCol, {
          ...topLeftCell,
          mc: { r: startRow, c: startCol, rs, cs },
        })
        nextMerge[`${startRow}_${startCol}`] = { r: startRow, c: startCol, rs, cs }

        for (let row = startRow; row <= endRow; row += 1) {
          for (let column = startCol; column <= endCol; column += 1) {
            if (row === startRow && column === startCol) continue
            const coveredCell = { ...ensureCell(row, column) }
            upsertCell(row, column, {
              ...coveredCell,
              mc: { r: startRow, c: startCol },
            })
          }
        }
      }

      const addLegendBorder = (startRow: number, rowCount: number) => {
        const endRow = startRow + rowCount
        for (let r = startRow; r <= endRow; r += 1) {
          for (let c = legendStartCol; c <= legendEndCol; c += 1) {
            const isTitle = r === startRow
            addCellBorder(r, c, {
              l: c === legendStartCol || (!isTitle && c === legendBodyStartCol) ? { color: '#000000', style: '1' } : undefined,
              r: c === legendEndCol || (!isTitle && c === legendStartCol) ? { color: '#000000', style: '1' } : undefined,
              t: { color: '#000000', style: '1' },
              b: { color: '#000000', style: '1' },
            })
          }
        }
      }

      const addCellBorder = (
        row: number,
        column: number,
        sides: Partial<Record<'l' | 'r' | 't' | 'b', { color: string; style: string }>>,
      ) => {
        const borderVal: Record<string, unknown> = {
          row_index: row,
          col_index: column,
        }
        if (sides.l) borderVal.l = sides.l
        if (sides.r) borderVal.r = sides.r
        if (sides.t) borderVal.t = sides.t
        if (sides.b) borderVal.b = sides.b

        nextBorderInfo.push({
          rangeType: 'cell',
          value: borderVal,
        })
      }

      const writeLegendBlock = (
        startRow: number,
        title: string,
        rows: Array<[string, string]>,
        titleOverrides: Record<string, unknown> = {},
      ) => {
        clearLegendBlock(startRow, rows.length)
        setMergeRegion(startRow, legendStartCol, startRow, legendEndCol)

        const titleBase = { ...ensureCell(startRow, legendStartCol) }
        upsertCell(startRow, legendStartCol, setPlainText(titleBase, title, {
          bg: '#FFFFFF',
          bl: 1,
          ht: 0,
          vt: 0,
          fc: '#111111',
          ...titleOverrides,
        }))

        rows.forEach(([symbol, label], rowOffset) => {
          const row = startRow + rowOffset + 1
          setMergeRegion(row, legendBodyStartCol, row, legendEndCol)

          const symbolBase = { ...ensureCell(row, legendStartCol) }
          upsertCell(row, legendStartCol, setPlainText(symbolBase, symbol, {
            bg: '#FFFFFF',
            bl: 1,
            ht: 0,
            vt: 0,
            fc: '#111111',
          }))

          const labelBase = { ...ensureCell(row, legendBodyStartCol) }
          upsertCell(row, legendBodyStartCol, setPlainText(labelBase, label, {
            bg: '#FFFFFF',
            ht: 1,
            vt: 0,
            fc: '#111111',
          }))
        })

        addLegendBorder(startRow, rows.length)
      }

      legendBlocks.forEach(({ startRow, title, rows, titleOverrides }) => writeLegendBlock(startRow, title, rows, titleOverrides))

      const visibleOwnerColumns = ownerColumnIndexes.slice(0, visibleOwnerCount)
      const ownerBlockStartCol = ownerPriorityHeaderCell?.c ?? visibleOwnerColumns[0]
      const ownerHeaderEndCol = ownerPriorityHeaderCell
        ? ownerPriorityHeaderCell.c + ((ownerPriorityHeaderCell?.mc?.cs ?? 1) - 1)
        : ownerBlockStartCol
      const ownerBlockEndCol = Math.max(
        ownerHeaderEndCol ?? ownerBlockStartCol ?? 0,
        visibleOwnerColumns[visibleOwnerColumns.length - 1] ?? ownerHeaderEndCol ?? ownerBlockStartCol ?? 0,
      )
      const ownerBlockStartRow = ownerPriorityHeaderCell?.r ?? taskHeaderRow
      // Extend the borders all the way down to include the vertical ownership names at the bottom
      const lowestOwnerHeaderRow = ownerHeaderCells.reduce((maxRow, { cell }) => Math.max(maxRow, cell.r ?? 0), 0)
      const ownerBlockEndRow = Math.max(
        taskStartRow + taskSectionRowCount - 1,
        lowestOwnerHeaderRow,
      )

      // Re-draw the Owner/Priority block borders using ONLY the visible owner columns.
      // ownerBlockEndCol (from the template header merge span) may point to hidden columns, so
      // we do NOT use it here. Instead we derive the column list from visibleOwnerColumns, which
      // is already the set of un-hidden owner columns. Every cell gets b+r so internal grid lines
      // are automatic; l is only on the first column and t is only on the first row.
      const ownerColsForBorder: number[] =
        visibleOwnerColumns.length > 0
          ? visibleOwnerColumns
          : typeof ownerBlockStartCol === 'number'
            ? [ownerBlockStartCol]
            : []

      if (ownerColsForBorder.length > 0 && typeof ownerBlockStartRow === 'number') {
        for (let row = ownerBlockStartRow; row <= ownerBlockEndRow; row += 1) {
          for (let ci = 0; ci < ownerColsForBorder.length; ci += 1) {
            const col = ownerColsForBorder[ci]
            addCellBorder(row, col, {
              l: ci === 0 ? { color: '#000000', style: '1' } : undefined,
              r: { color: '#000000', style: '1' },   // every col → internal dividers + outer right
              t: row === ownerBlockStartRow ? { color: '#000000', style: '1' } : undefined,
              b: { color: '#000000', style: '1' },   // every row → grid lines + outer bottom
            })
          }
        }
      }

      const nextColumnlen: Record<string, number> = { ...(config.columnlen ?? {}) }
      const nextColhidden: Record<string, number> = { ...(config.colhidden ?? {}) }
      const nextRowlen: Record<string, number> = { ...(config.rowlen ?? {}) }
      const nextCustomHeight: Record<string, number> = { ...(config.customHeight ?? {}) }

      legendBlocks.forEach(({ startRow, rows }) => {
        nextRowlen[String(startRow)] = PREVIEW_LEGEND_TITLE_ROW_HEIGHT
        nextCustomHeight[String(startRow)] = 1
        rows.forEach((_, index) => {
          const row = startRow + index + 1
          nextRowlen[String(row)] = PREVIEW_LEGEND_BODY_ROW_HEIGHT
          nextCustomHeight[String(row)] = 1
        })
      })

      ownerColumnIndexes.forEach((columnIndex, index) => {
        nextColumnlen[String(columnIndex)] = PREVIEW_OWNER_COLUMN_WIDTH
        if (index < visibleOwnerCount) delete nextColhidden[String(columnIndex)]
        else nextColhidden[String(columnIndex)] = 0
      })

      if (removedOwnerCount === 0) {
        ownerColumnIndexes.forEach((columnIndex) => delete nextColhidden[String(columnIndex)])
      }

      legendColumns.forEach((columnIndex, index) => {
        nextColumnlen[String(columnIndex)] = PREVIEW_LEGEND_COLUMN_WIDTHS[index] ?? FALLBACK_COLUMN_WIDTH
        delete nextColhidden[String(columnIndex)]
      })

      const nextConfig = {
        ...config,
        merge: nextMerge,
        borderInfo: nextBorderInfo,
        columnlen: nextColumnlen,
        colhidden: nextColhidden,
        rowlen: nextRowlen,
        customHeight: nextCustomHeight,
      }

      return {
        ...sheet,
        celldata,
        config: nextConfig,
        scrollTop: 0,
        scrollLeft: 0,
      }
    })
    sheetDataRef.current = updated
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!sheetDataRef.current?.length || layoutNormalizedRef.current) return
    layoutNormalizedRef.current = true
    applyFillsToSheet({}, [], [])
    setSheetKey(k => k + 1)
  }, [applyFillsToSheet, sheetKey])

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
      const payload = await res.json() as OPPMFillPayload
      const { fills, tasks = [], members = [] } = payload
      // Reset to raw template snapshot before applying — makes fill idempotent on repeated clicks
      if (rawSheetRef.current) {
        sheetDataRef.current = JSON.parse(JSON.stringify(rawSheetRef.current))
      }
      applyFillsToSheet(fills, tasks, members)
      setIsFilled(true)
      // Persist filled sheet to backend so it loads correctly on next visit
      try {
        const saveToken = localStorage.getItem('access_token') ?? ''
        fetch(`/api${wsPath}/projects/${id}/oppm/spreadsheet`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${saveToken}` },
          body: JSON.stringify({ sheet_data: sheetDataRef.current, file_name: sheetFileName ?? 'OPPM Template.xlsx' }),
        })
      } catch { /* fire-and-forget */ }
      setSheetKey(k => k + 1)  // re-render Workbook with updated data
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'AI fill failed'
      setAiFillError(msg)
    } finally {
      setAiFilling(false)
    }
  }, [ws, id, wsPath, applyFillsToSheet])

  // ── Reset to clean template ────────────────────────────
  const handleReset = useCallback(() => {
    if (!rawSheetRef.current) return
    sheetDataRef.current = JSON.parse(JSON.stringify(rawSheetRef.current))
    setIsFilled(false)
    setAiFillError(null)
    setSheetKey(k => k + 1)
  }, [])

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

  const handleHorizontalScroll = useCallback((direction: 'left' | 'right') => {
    const workbookApi = sheetRef.current
    if (!workbookApi?.scroll || !workbookApi?.getSheet) return

    const activeSheet = workbookApi.getSheet()
    const currentScrollLeft = Number(activeSheet?.scrollLeft ?? 0)
    const nextScrollLeft = direction === 'left'
      ? Math.max(0, currentScrollLeft - HORIZONTAL_SCROLL_STEP)
      : currentScrollLeft + HORIZONTAL_SCROLL_STEP

    workbookApi.scroll({ scrollLeft: nextScrollLeft })
  }, [])

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

          {/* Reset to blank template */}
          {hasSheet && (
            <div className="inline-flex items-center rounded-lg border border-gray-300 bg-white shadow-sm overflow-hidden">
              <button
                onClick={() => handleHorizontalScroll('left')}
                className="inline-flex items-center gap-1 border-r border-gray-300 px-3 py-1.5 text-xs font-semibold text-gray-600 hover:bg-gray-50 transition-colors"
                title="Scroll the OPPM sheet to the left"
              >
                <ChevronLeft className="h-3.5 w-3.5" />
                Left
              </button>
              <button
                onClick={() => handleHorizontalScroll('right')}
                className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-semibold text-gray-600 hover:bg-gray-50 transition-colors"
                title="Scroll the OPPM sheet to the right"
              >
                Right
                <ChevronRight className="h-3.5 w-3.5" />
              </button>
            </div>
          )}

          {hasSheet && (
            <button
              onClick={handleReset}
              disabled={aiFilling}
              className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-xs font-semibold text-gray-600 hover:bg-gray-50 shadow-sm transition-colors disabled:opacity-50"
              title="Reset to blank template"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              Reset
            </button>
          )}

          {/* AI Fill */}
          {hasSheet && (
            <button
              onClick={handleAiFill}
              disabled={aiFilling}
              className="inline-flex items-center gap-1.5 rounded-lg border border-violet-300 bg-violet-50 px-3 py-1.5 text-xs font-semibold text-violet-700 hover:bg-violet-100 shadow-sm transition-colors disabled:opacity-50"
              title="AI fills the OPPM header, completion panel, owner priorities, and timeline symbols from your project data"
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

      {/* ── How-to guide (collapsible) ────────────────── */}
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
              <p className="text-xs font-bold text-indigo-800 mb-1">�️ This is a read-only OPPM overview</p>
              <p className="text-[11px] text-gray-600">Scroll horizontally and vertically to explore the full OPPM layout. You can use the new <strong>Left</strong> and <strong>Right</strong> buttons in the top bar to move across the sheet faster. Use <strong>AI Fill</strong> to populate the template from your project data, then <strong>Download OPPM</strong> to get the full auto-generated report.</p>
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="rounded-lg bg-violet-50 border border-violet-200 p-3">
                <p className="text-xs font-bold text-violet-800 flex items-center gap-1.5"><Sparkles className="h-3.5 w-3.5" /> AI Fill</p>
                <p className="text-[11px] text-violet-700 mt-1">Auto-fills the template from live project data: <strong>Project Name</strong>, <strong>Project Leader</strong>, <strong>Objective</strong>, <strong>Deliverable Output</strong>, <strong>Start Date</strong>, <strong>Deadline</strong>, <strong>Project Completed By</strong>, owner <strong>A/B/C</strong> priorities, and timeline symbols.</p>
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
              allowEdit={false}
              showToolbar={false}
              onChange={() => {}}
              onOp={() => {}}
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

