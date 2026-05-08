/**
 * GanttChart — pure SVG Gantt with dependency arrows.
 *
 * Each task renders a horizontal bar spanning start_date → due_date.
 * Arrows connect predecessor bar-end to successor bar-start.
 * Tasks without any dates are listed separately below the chart.
 */

import { useMemo, useRef, useState } from 'react'
import type { Task } from '@/types'

// ── Layout constants ──────────────────────────────────────────────────────────
const ROW_HEIGHT = 42
const BAR_HEIGHT = 20
const BAR_RADIUS = 6
const HEADER_HEIGHT = 44
const LABEL_WIDTH = 200
const DATE_COL_WIDTH = 90   // left side date columns
const DAY_PX = 14           // pixels per day
const ARROW_OFFSET = 10     // extra horizontal padding for arrow routing
const TODAY_LINE_WIDTH = 2

// ── Colour maps ───────────────────────────────────────────────────────────────
const STATUS_FILL: Record<Task['status'], string> = {
  todo: '#CBD5E1',       // slate-300
  in_progress: '#60A5FA', // blue-400
  completed: '#34D399',  // emerald-400
}

const STATUS_TEXT: Record<Task['status'], string> = {
  todo: '#475569',
  in_progress: '#1D4ED8',
  completed: '#065F46',
}

const PRIORITY_STROKE: Record<Task['priority'], string> = {
  low: '#94A3B8',
  medium: '#3B82F6',
  high: '#F59E0B',
  critical: '#EF4444',
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function parseDate(iso: string | null): Date | null {
  if (!iso) return null
  const d = new Date(iso)
  return isNaN(d.getTime()) ? null : d
}

function daysDiff(a: Date, b: Date): number {
  return Math.round((b.getTime() - a.getTime()) / 86_400_000)
}

function addDays(d: Date, n: number): Date {
  return new Date(d.getTime() + n * 86_400_000)
}

function fmtMonthYear(d: Date): string {
  return d.toLocaleDateString(undefined, { month: 'short', year: 'numeric' })
}

function fmtShortDate(d: Date): string {
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

// ── Types ─────────────────────────────────────────────────────────────────────
interface TaskRow {
  task: Task
  index: number        // row index in the chart (dated tasks only)
  startDay: number     // offset in days from chart origin
  durationDays: number
  barX: number
  barW: number
  barY: number
  barMidY: number
}

interface Arrow {
  fromX: number
  fromY: number
  toX: number
  toY: number
  color: string
}

// ── Main component ────────────────────────────────────────────────────────────
interface GanttChartProps {
  tasks: Task[]
  onTaskClick?: (task: Task) => void
}

export function GanttChart({ tasks, onTaskClick }: GanttChartProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [tooltip, setTooltip] = useState<{ x: number; y: number; task: Task } | null>(null)

  // Split tasks by whether they have at least one date
  const { datedTasks, undatedTasks } = useMemo(() => {
    const dated = tasks.filter((t) => t.start_date || t.due_date)
    const undated = tasks.filter((t) => !t.start_date && !t.due_date)
    return { datedTasks: dated, undatedTasks: undated }
  }, [tasks])

  // Compute date range with padding
  const { origin, totalDays } = useMemo(() => {
    const dates: Date[] = []
    for (const t of datedTasks) {
      const s = parseDate(t.start_date)
      const e = parseDate(t.due_date)
      if (s) dates.push(s)
      if (e) dates.push(e)
    }
    if (dates.length === 0) {
      const now = new Date()
      return { origin: addDays(now, -7), totalDays: 60 }
    }
    const earliest = new Date(Math.min(...dates.map((d) => d.getTime())))
    const latest = new Date(Math.max(...dates.map((d) => d.getTime())))
    const padStart = addDays(earliest, -7)
    const padEnd = addDays(latest, 14)
    return { origin: padStart, totalDays: Math.max(30, daysDiff(padStart, padEnd)) }
  }, [datedTasks])

  // Build task rows
  const taskRows = useMemo<TaskRow[]>(() => {
    return datedTasks.map((task, index) => {
      const s = parseDate(task.start_date) ?? parseDate(task.due_date)!
      const e = parseDate(task.due_date) ?? parseDate(task.start_date)!
      const startDay = daysDiff(origin, s)
      const durationDays = Math.max(1, daysDiff(s, e))
      const barX = LABEL_WIDTH + startDay * DAY_PX
      const barW = Math.max(6, durationDays * DAY_PX)
      const barY = HEADER_HEIGHT + index * ROW_HEIGHT + (ROW_HEIGHT - BAR_HEIGHT) / 2
      return { task, index, startDay, durationDays, barX, barW, barY, barMidY: barY + BAR_HEIGHT / 2 }
    })
  }, [datedTasks, origin])

  // Index task rows by task ID for arrow drawing
  const rowById = useMemo(() => {
    const map = new Map<string, TaskRow>()
    for (const row of taskRows) map.set(row.task.id, row)
    return map
  }, [taskRows])

  // Build dependency arrows
  const arrows = useMemo<Arrow[]>(() => {
    const result: Arrow[] = []
    for (const row of taskRows) {
      for (const depId of row.task.depends_on) {
        const predRow = rowById.get(depId)
        if (!predRow) continue
        const fromX = predRow.barX + predRow.barW
        const fromY = predRow.barMidY
        const toX = row.barX
        const toY = row.barMidY
        result.push({ fromX, fromY, toX, toY, color: PRIORITY_STROKE[row.task.priority] })
      }
    }
    return result
  }, [taskRows, rowById])

  // Month header markers
  const monthMarkers = useMemo(() => {
    const markers: { x: number; label: string }[] = []
    const cur = new Date(origin)
    cur.setDate(1)
    while (true) {
      const d = daysDiff(origin, cur)
      if (d > totalDays) break
      markers.push({ x: LABEL_WIDTH + d * DAY_PX, label: fmtMonthYear(cur) })
      cur.setMonth(cur.getMonth() + 1)
    }
    return markers
  }, [origin, totalDays])

  // Today marker
  const todayX = useMemo(() => {
    const d = daysDiff(origin, new Date())
    return d >= 0 && d <= totalDays ? LABEL_WIDTH + d * DAY_PX : null
  }, [origin, totalDays])

  const chartWidth = LABEL_WIDTH + totalDays * DAY_PX
  const chartHeight = HEADER_HEIGHT + datedTasks.length * ROW_HEIGHT

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-4">
      {/* Scrollable chart area */}
      <div
        ref={scrollRef}
        className="rounded-xl border border-border bg-white shadow-sm overflow-x-auto overflow-y-hidden"
        style={{ position: 'relative' }}
      >
        {datedTasks.length === 0 ? (
          <div className="flex items-center justify-center py-16 text-sm text-text-secondary">
            No tasks with dates yet — add start or due dates to see the Gantt chart.
          </div>
        ) : (
          <svg
            width={chartWidth}
            height={chartHeight}
            style={{ display: 'block', minWidth: chartWidth }}
            onMouseLeave={() => setTooltip(null)}
          >
            {/* ── Background grid ── */}
            {monthMarkers.map((m, i) => (
              <line
                key={i}
                x1={m.x} y1={HEADER_HEIGHT}
                x2={m.x} y2={chartHeight}
                stroke="#E2E8F0"
                strokeWidth={1}
              />
            ))}

            {/* ── Row zebra bands ── */}
            {datedTasks.map((_, i) => (
              <rect
                key={i}
                x={0} y={HEADER_HEIGHT + i * ROW_HEIGHT}
                width={chartWidth} height={ROW_HEIGHT}
                fill={i % 2 === 0 ? '#F8FAFC' : '#FFFFFF'}
              />
            ))}

            {/* ── Header background ── */}
            <rect x={0} y={0} width={chartWidth} height={HEADER_HEIGHT} fill="#F1F5F9" />
            <line x1={0} y1={HEADER_HEIGHT} x2={chartWidth} y2={HEADER_HEIGHT} stroke="#E2E8F0" strokeWidth={1} />

            {/* Label column separator */}
            <line x1={LABEL_WIDTH} y1={0} x2={LABEL_WIDTH} y2={chartHeight} stroke="#CBD5E1" strokeWidth={1} />

            {/* ── Month labels ── */}
            {monthMarkers.map((m, i) => (
              <text key={i} x={m.x + 6} y={HEADER_HEIGHT / 2 + 5} fontSize={11} fontWeight={600} fill="#64748B">
                {m.label}
              </text>
            ))}

            {/* ── Today line ── */}
            {todayX !== null && (
              <>
                <line
                  x1={todayX} y1={0}
                  x2={todayX} y2={chartHeight}
                  stroke="#EF4444"
                  strokeWidth={TODAY_LINE_WIDTH}
                  strokeDasharray="4 3"
                  opacity={0.7}
                />
                <text x={todayX + 4} y={14} fontSize={10} fontWeight={700} fill="#EF4444">Today</text>
              </>
            )}

            {/* ── Task label column ── */}
            {taskRows.map(({ task, index, barMidY }) => (
              <g key={task.id}>
                {/* Row separator */}
                <line
                  x1={0} y1={HEADER_HEIGHT + (index + 1) * ROW_HEIGHT}
                  x2={chartWidth} y2={HEADER_HEIGHT + (index + 1) * ROW_HEIGHT}
                  stroke="#E2E8F0" strokeWidth={1}
                />
                {/* Task title (clipped to label area) */}
                <text
                  x={10} y={barMidY + 5}
                  fontSize={12}
                  fontWeight={500}
                  fill="#1E293B"
                  cursor="pointer"
                  onClick={() => onTaskClick?.(task)}
                >
                  <title>{task.title}</title>
                  {task.title.length > 22 ? task.title.slice(0, 21) + '…' : task.title}
                </text>
              </g>
            ))}

            {/* ── Dependency arrows ── */}
            <defs>
              <marker id="arrow-head" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
                <path d="M0,0 L0,6 L6,3 z" fill="#94A3B8" />
              </marker>
            </defs>
            {arrows.map((a, i) => {
              // Route: right of pred → horizontal → vertical → horizontal → left of succ
              const midX = Math.max(a.fromX + ARROW_OFFSET, a.toX - ARROW_OFFSET)
              const path =
                a.fromY === a.toY
                  ? `M${a.fromX},${a.fromY} L${a.toX},${a.toY}`
                  : `M${a.fromX},${a.fromY} H${midX} V${a.toY} H${a.toX}`
              return (
                <path
                  key={i}
                  d={path}
                  fill="none"
                  stroke="#94A3B8"
                  strokeWidth={1.5}
                  strokeDasharray="5 3"
                  markerEnd="url(#arrow-head)"
                  opacity={0.75}
                />
              )
            })}

            {/* ── Task bars ── */}
            {taskRows.map(({ task, barX, barW, barY, barMidY }) => {
              const fill = STATUS_FILL[task.status]
              const stroke = PRIORITY_STROKE[task.priority]
              const textFill = STATUS_TEXT[task.status]
              const progressW = Math.max(0, barW * (task.progress / 100))

              return (
                <g
                  key={task.id}
                  cursor="pointer"
                  onClick={() => onTaskClick?.(task)}
                  onMouseEnter={(e) => {
                    const rect = (e.currentTarget as SVGGElement).ownerSVGElement!.getBoundingClientRect()
                    setTooltip({ x: barX - rect.left + 20, y: barMidY, task })
                  }}
                  onMouseLeave={() => setTooltip(null)}
                >
                  {/* Bar background (full width) */}
                  <rect
                    x={barX} y={barY}
                    width={barW} height={BAR_HEIGHT}
                    rx={BAR_RADIUS} ry={BAR_RADIUS}
                    fill={fill}
                    stroke={stroke}
                    strokeWidth={1.5}
                    opacity={0.85}
                  />
                  {/* Progress fill */}
                  {progressW > 0 && (
                    <rect
                      x={barX} y={barY}
                      width={progressW} height={BAR_HEIGHT}
                      rx={BAR_RADIUS} ry={BAR_RADIUS}
                      fill={stroke}
                      opacity={0.35}
                    />
                  )}
                  {/* Label inside bar (only if wide enough) */}
                  {barW > 60 && (
                    <text
                      x={barX + 8} y={barMidY + 4}
                      fontSize={10} fontWeight={600}
                      fill={textFill}
                      pointerEvents="none"
                    >
                      {task.progress > 0 ? `${task.progress}%` : ''}
                    </text>
                  )}
                  {/* Date labels outside bar */}
                  {task.start_date && (
                    <text
                      x={barX - 4} y={barMidY + 4}
                      fontSize={9} fill="#94A3B8"
                      textAnchor="end"
                      pointerEvents="none"
                    >
                      {fmtShortDate(new Date(task.start_date))}
                    </text>
                  )}
                  {task.due_date && (
                    <text
                      x={barX + barW + 4} y={barMidY + 4}
                      fontSize={9} fill="#94A3B8"
                      textAnchor="start"
                      pointerEvents="none"
                    >
                      {fmtShortDate(new Date(task.due_date))}
                    </text>
                  )}
                  {/* Dependency indicator dot */}
                  {task.depends_on.length > 0 && (
                    <circle cx={barX} cy={barMidY} r={4} fill="#6366F1" opacity={0.9} />
                  )}
                </g>
              )
            })}
          </svg>
        )}
      </div>

      {/* ── Legend ── */}
      <div className="flex flex-wrap items-center gap-4 px-1 text-xs text-text-secondary">
        <span className="font-semibold text-text">Legend:</span>
        {(Object.entries(STATUS_FILL) as [Task['status'], string][]).map(([s, c]) => (
          <span key={s} className="flex items-center gap-1.5">
            <span className="inline-block h-3 w-5 rounded" style={{ background: c }} />
            {s === 'todo' ? 'To Do' : s === 'in_progress' ? 'In Progress' : 'Completed'}
          </span>
        ))}
        <span className="flex items-center gap-1.5">
          <svg width={20} height={12}>
            <line x1={0} y1={6} x2={18} y2={6} stroke="#94A3B8" strokeWidth={1.5} strokeDasharray="4 2" />
            <polygon points="14,2 20,6 14,10" fill="#94A3B8" />
          </svg>
          Dependency
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-3 w-3 rounded-full" style={{ background: '#6366F1' }} />
          Has dependency
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-0.5 w-5 bg-red-400" style={{ borderTop: '2px dashed #EF4444' }} />
          Today
        </span>
      </div>

      {/* ── Undated tasks ── */}
      {undatedTasks.length > 0 && (
        <div className="rounded-xl border border-border bg-white shadow-sm">
          <div className="border-b border-border px-4 py-2.5">
            <p className="text-xs font-semibold text-text-secondary uppercase tracking-wide">
              Tasks without dates ({undatedTasks.length})
            </p>
          </div>
          <div className="divide-y divide-border">
            {undatedTasks.map((task) => (
              <div
                key={task.id}
                className="flex items-center gap-3 px-4 py-2.5 cursor-pointer hover:bg-surface-alt transition-colors"
                onClick={() => onTaskClick?.(task)}
              >
                <span
                  className="h-2.5 w-2.5 rounded-full flex-shrink-0"
                  style={{ background: STATUS_FILL[task.status] }}
                />
                <span className="text-sm font-medium text-text flex-1 truncate">{task.title}</span>
                <span className="text-xs px-1.5 py-0.5 rounded font-medium"
                  style={{ background: STATUS_FILL[task.status] + '33', color: STATUS_TEXT[task.status] }}>
                  {task.status === 'todo' ? 'To Do' : task.status === 'in_progress' ? 'In Progress' : 'Completed'}
                </span>
                {task.depends_on.length > 0 && (
                  <span className="text-[10px] text-indigo-500 font-medium">
                    Depends on {task.depends_on.length}
                  </span>
                )}
                <span className="text-xs text-text-secondary">{task.progress}%</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
