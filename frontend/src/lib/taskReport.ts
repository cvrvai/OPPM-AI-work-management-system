/**
 * Task report export utilities â€” CSV and PDF.
 * Both formats group tasks by OPPM objective and include a project summary header.
 */
import jsPDF from 'jspdf'
import autoTable from 'jspdf-autotable'
import type { Task, Project } from '@/types'

// â”€â”€ helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function csvCell(value: string | number | null | undefined): string {
  const str = String(value ?? '')
  if (str.includes(',') || str.includes('"') || str.includes('\n')) {
    return `"${str.replace(/"/g, '""')}"`
  }
  return str
}

function slugify(title: string): string {
  return title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 60)
}

function today(): string {
  return new Date().toISOString().slice(0, 10)
}

function formatD(d: string | null | undefined): string {
  if (!d) return ''
  return d.slice(0, 10)
}

function statusLabel(s: string): string {
  return s === 'in_progress' ? 'In Progress' : s === 'todo' ? 'To Do' : 'Completed'
}

function priorityLabel(p: string): string {
  return p.charAt(0).toUpperCase() + p.slice(1)
}

function getAssignees(task: Task, memberMap: Map<string, string>): string {
  if (task.assignees && task.assignees.length > 0) {
    return task.assignees.map((a) => a.display_name || memberMap.get(a.id) || a.id.slice(0, 8)).join(', ')
  }
  if (task.assignee_id) {
    return memberMap.get(task.assignee_id) || task.assignee_id.slice(0, 8)
  }
  return ''
}

interface TaskRow {
  objective: string
  title: string
  type: string
  status: string
  priority: string
  progress: string
  assignees: string
  startDate: string
  dueDate: string
}

function buildRows(
  tasks: Task[],
  objectiveMap: Map<string, string>,
  memberMap: Map<string, string>,
): TaskRow[] {
  const mainTasks = tasks.filter((t) => !t.parent_task_id)
  const subMap = new Map<string, Task[]>()
  tasks.filter((t) => t.parent_task_id).forEach((t) => {
    const parent = t.parent_task_id!
    if (!subMap.has(parent)) subMap.set(parent, [])
    subMap.get(parent)!.push(t)
  })

  const rows: TaskRow[] = []
  for (const main of mainTasks) {
    const objName = main.oppm_objective_id ? (objectiveMap.get(main.oppm_objective_id) ?? '') : ''
    rows.push({
      objective: objName,
      title: main.title,
      type: 'Main Task',
      status: statusLabel(main.status),
      priority: priorityLabel(main.priority),
      progress: `${main.progress ?? 0}%`,
      assignees: getAssignees(main, memberMap),
      startDate: formatD(main.start_date),
      dueDate: formatD(main.due_date),
    })
    const subs = subMap.get(main.id) ?? []
    for (const sub of subs) {
      rows.push({
        objective: objName,
        title: `  â”” ${sub.title}`,
        type: 'Sub-task',
        status: statusLabel(sub.status),
        priority: priorityLabel(sub.priority),
        progress: `${sub.progress ?? 0}%`,
        assignees: getAssignees(sub, memberMap),
        startDate: formatD(sub.start_date),
        dueDate: formatD(sub.due_date),
      })
    }
  }
  return rows
}

// â”€â”€ CSV export â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

export function exportTasksCSV(
  tasks: Task[],
  objectiveMap: Map<string, string>,
  memberMap: Map<string, string>,
  project: Project,
): void {
  const rows = buildRows(tasks, objectiveMap, memberMap)

  const headers = ['#', 'Objective', 'Title', 'Type', 'Status', 'Priority', 'Progress', 'Assignee(s)', 'Start Date', 'Due Date']

  // Project summary block
  const summaryLines = [
    `Project Report: ${project.title}`,
    `Status: ${statusLabel(project.status)}`,
    `Progress: ${project.progress}%`,
    `Start: ${formatD(project.start_date)}`,
    `Deadline: ${formatD(project.deadline)}`,
    `Total Tasks: ${tasks.filter((t) => !t.parent_task_id).length}`,
    `Completed: ${tasks.filter((t) => t.status === 'completed').length}`,
    `Generated: ${today()}`,
    '',
  ]

  const dataLines = rows.map((r, i) =>
    [
      csvCell(i + 1),
      csvCell(r.objective),
      csvCell(r.title.trim()),
      csvCell(r.type),
      csvCell(r.status),
      csvCell(r.priority),
      csvCell(r.progress),
      csvCell(r.assignees),
      csvCell(r.startDate),
      csvCell(r.dueDate),
    ].join(',')
  )

  const csv = [
    ...summaryLines.map((l) => csvCell(l)),
    headers.map(csvCell).join(','),
    ...dataLines,
  ].join('\r\n')

  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${slugify(project.title)}-tasks-${today()}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

// â”€â”€ PDF export â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

const C = {
  // Brand
  navy:       [15,  23,  42]  as [number, number, number],   // slate-900
  blue:       [37,  99,  235] as [number, number, number],   // blue-600
  blueLight:  [219,234,254]   as [number, number, number],   // blue-100
  blueMid:    [147,197,253]   as [number, number, number],   // blue-300
  // Neutrals
  white:      [255,255,255]   as [number, number, number],
  gray50:     [248,250,252]   as [number, number, number],
  gray100:    [241,245,249]   as [number, number, number],
  gray200:    [226,232,240]   as [number, number, number],
  gray300:    [203,213,225]   as [number, number, number],
  gray400:    [148,163,184]   as [number, number, number],
  gray500:    [100,116,139]   as [number, number, number],
  gray700:    [51, 65, 85]    as [number, number, number],
  gray900:    [15, 23, 42]    as [number, number, number],
  // Status
  green:      [22, 163, 74]   as [number, number, number],
  greenBg:    [220,252,231]   as [number, number, number],
  amber:      [180,83,9]      as [number, number, number],
  amberBg:    [254,243,199]   as [number, number, number],
  amberMid:   [217,119,6]     as [number, number, number],   // amber-600
  // Priority
  red:        [185,28,28]     as [number, number, number],
  redBg:      [254,226,226]   as [number, number, number],
  orange:     [194,65,12]     as [number, number, number],
  orangeBg:   [255,237,213]   as [number, number, number],
}

function statusChip(s: string): { text: string; fg: [number,number,number]; bg: [number,number,number] } {
  if (s === 'completed')   return { text: 'Completed',   fg: C.green,   bg: C.greenBg  }
  if (s === 'in_progress') return { text: 'In Progress', fg: C.amber,   bg: C.amberBg  }
  return                          { text: 'To Do',       fg: C.gray700, bg: C.gray100  }
}

function priorityChip(p: string): { text: string; fg: [number,number,number]; bg: [number,number,number] } {
  if (p === 'critical') return { text: 'Critical', fg: C.red,    bg: C.redBg    }
  if (p === 'high')     return { text: 'High',     fg: C.orange, bg: C.orangeBg }
  if (p === 'medium')   return { text: 'Medium',   fg: C.blue,   bg: C.blueLight }
  return                       { text: 'Low',      fg: C.gray500, bg: C.gray100  }
}

function miniBar(
  doc: jsPDF,
  x: number,
  y: number,
  w: number,
  h: number,
  pct: number,
  trackColor: [number,number,number],
  fillColor: [number,number,number],
): void {
  doc.setFillColor(...trackColor)
  doc.roundedRect(x, y, w, h, h / 2, h / 2, 'F')
  if (pct > 0) {
    doc.setFillColor(...fillColor)
    doc.roundedRect(x, y, Math.max(h, w * pct / 100), h, h / 2, h / 2, 'F')
  }
}

export function exportTasksPDF(
  tasks: Task[],
  objectiveMap: Map<string, string>,
  memberMap: Map<string, string>,
  project: Project,
): void {
  const doc   = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' })
  const pageW = doc.internal.pageSize.getWidth()
  const pageH = doc.internal.pageSize.getHeight()
  const M     = 16  // margin

  // â”€â”€ MINIMAL HEADER â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  // Thin blue top bar
  doc.setFillColor(...C.blue)
  doc.rect(0, 0, pageW, 2.5, 'F')

  // Project title
  const titleLine = project.title.length > 70 ? project.title.slice(0, 67) + 'â€¦' : project.title
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(16)
  doc.setTextColor(...C.navy)
  doc.text(titleLine, M, 12)

  // Top-right: methodology badge + date
  const subBadge = project.project_code
    ? `#${project.project_code}`
    : project.methodology ? project.methodology.toUpperCase() : ''
  doc.setFont('helvetica', 'normal')
  doc.setFontSize(7)
  doc.setTextColor(...C.gray400)
  if (subBadge) doc.text(subBadge, pageW - M, 8, { align: 'right' })
  doc.text(`Generated ${today()}`, pageW - M, subBadge ? 13 : 10, { align: 'right' })

  // Separator
  doc.setDrawColor(...C.gray200)
  doc.setLineWidth(0.3)
  doc.line(M, 16, pageW - M, 16)

  // â”€â”€ COMPACT INFO LINE â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  const totalMain  = tasks.filter((t) => !t.parent_task_id).length
  const totalDone  = tasks.filter((t) => t.status === 'completed').length
  const totalWip   = tasks.filter((t) => t.status === 'in_progress').length
  const overallPct = project.progress ?? 0

  const infoParts: string[] = [
    `Status: ${statusLabel(project.status)}`,
    `Priority: ${priorityLabel(project.priority)}`,
    ...(project.deadline ? [`Deadline: ${formatD(project.deadline)}`] : []),
    `Tasks: ${totalMain}`,
    `Completed: ${totalDone}`,
    `In Progress: ${totalWip}`,
  ]
  doc.setFont('helvetica', 'normal')
  doc.setFontSize(7.5)
  doc.setTextColor(...C.gray500)
  doc.text(infoParts.join('   Â·   '), M, 22)

  // â”€â”€ PROGRESS BAR â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  const pbX = M + 28
  const pbW = pageW - M * 2 - 28 - 14
  const pbH = 3
  const pbY = 26.5

  doc.setFont('helvetica', 'normal')
  doc.setFontSize(7)
  doc.setTextColor(...C.gray400)
  doc.text('Progress', M, pbY + pbH / 2, { baseline: 'middle' })

  const pbFill: [number,number,number] =
    overallPct === 100 ? C.green : overallPct >= 60 ? C.blue : overallPct > 0 ? C.amberMid : C.gray300
  miniBar(doc, pbX, pbY, pbW, pbH, overallPct, C.gray100, pbFill)

  doc.setFont('helvetica', 'bold')
  doc.setFontSize(7.5)
  doc.setTextColor(...pbFill)
  doc.text(`${overallPct}%`, pageW - M, pbY + pbH / 2, { align: 'right', baseline: 'middle' })

  // Separator below progress
  doc.setDrawColor(...C.gray200)
  doc.setLineWidth(0.3)
  doc.line(M, 33, pageW - M, 33)

  // â”€â”€ TABLE COLUMNS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  // Sum = 265mm (A4 landscape 297 âˆ’ 2Ã—16 margin)
  const COL_W        = [6, 91, 26, 22, 26, 50, 22, 22]
  const PROGRESS_COL = 4
  const HEADERS      = ['#', 'Title', 'Status', 'Priority', 'Progress', 'Assignee(s)', 'Start', 'Due']

  let curY   = 36
  let rowNum = 0

  // â”€â”€ GROUP TASKS BY OBJECTIVE â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  const objectiveOrder: string[] = []
  const tasksByObjective: Record<string, Task[]> = { '': [] }
  tasks.filter((t) => !t.parent_task_id).forEach((t) => {
    const objId = t.oppm_objective_id ?? ''
    if (!tasksByObjective[objId]) {
      tasksByObjective[objId] = []
      if (objId) objectiveOrder.push(objId)
    }
    tasksByObjective[objId].push(t)
  })
  if (tasksByObjective[''].length > 0) objectiveOrder.push('')

  const subMap = new Map<string, Task[]>()
  tasks.filter((t) => t.parent_task_id).forEach((t) => {
    const parent = t.parent_task_id!
    if (!subMap.has(parent)) subMap.set(parent, [])
    subMap.get(parent)!.push(t)
  })

  // Continuation page slim header
  const drawContinuationHeader = () => {
    doc.setFillColor(...C.blue)
    doc.rect(0, 0, pageW, 2.5, 'F')
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(8.5)
    doc.setTextColor(...C.navy)
    doc.text(titleLine, M, 9)
    doc.setDrawColor(...C.gray200)
    doc.setLineWidth(0.3)
    doc.line(M, 12, pageW - M, 12)
  }

  for (const objId of objectiveOrder) {
    const objTasks = tasksByObjective[objId] ?? []
    if (objTasks.length === 0) continue

    const objName = objId ? (objectiveMap.get(objId) ?? 'Unassigned') : 'Unassigned'
    const objDone = objTasks.filter((t) => t.status === 'completed').length
    const objPct  = objTasks.length > 0 ? Math.round((objDone / objTasks.length) * 100) : 0

    if (curY > pageH - 42) {
      doc.addPage()
      drawContinuationHeader()
      curY = 16
    }

    // â”€â”€ OBJECTIVE HEADER: left blue tick, name, right pct + fraction + mini bar â”€â”€
    const objPctColor: [number,number,number] =
      objPct === 100 ? C.green : objPct >= 60 ? C.blue : objPct > 0 ? C.amberMid : C.gray400

    doc.setFillColor(...C.blue)
    doc.rect(M, curY, 3, 7, 'F')

    doc.setFont('helvetica', 'bold')
    doc.setFontSize(9)
    doc.setTextColor(...C.navy)
    doc.text(objName, M + 7, curY + 5.5)

    // right: pct bold + fraction light + mini bar
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(8.5)
    doc.setTextColor(...objPctColor)
    doc.text(`${objPct}%`, pageW - M - 42, curY + 5.5, { align: 'right' })

    doc.setFont('helvetica', 'normal')
    doc.setFontSize(7.5)
    doc.setTextColor(...C.gray400)
    doc.text(`${objDone}/${objTasks.length}`, pageW - M - 36, curY + 5.5)

    miniBar(doc, pageW - M - 28, curY + (7 - 2.5) / 2, 28, 2.5, objPct, C.gray100, objPctColor)

    curY += 9

    // â”€â”€ BUILD TABLE ROWS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    const tableBody: (string | object)[][] = []
    const pctLookup:      number[] = []
    const statusLookup:   string[] = []
    const priorityLookup: string[] = []

    for (const main of objTasks) {
      rowNum++
      const sc   = statusChip(main.status)
      const pc   = priorityChip(main.priority)
      const pct2 = main.progress ?? 0
      pctLookup.push(pct2)
      statusLookup.push(main.status)
      priorityLookup.push(main.priority)

      tableBody.push([
        { content: String(rowNum), styles: { halign: 'center', textColor: C.gray400, fontSize: 7 } },
        { content: main.title, styles: { fontStyle: 'bold', fontSize: 8, textColor: C.navy } },
        // Status: colored text only, no cell fill
        { content: sc.text, styles: { textColor: sc.fg, fontSize: 7.5, halign: 'center', fontStyle: 'bold' } },
        // Priority: colored text only, no cell fill
        { content: pc.text, styles: { textColor: pc.fg, fontSize: 7.5, halign: 'center', fontStyle: 'bold' } },
        { content: String(pct2), styles: { fontSize: 0.5, halign: 'center', textColor: C.white } },
        { content: getAssignees(main, memberMap), styles: { fontSize: 7.5, textColor: C.gray700 } },
        { content: formatD(main.start_date), styles: { fontSize: 7.5, textColor: C.gray400, halign: 'center' } },
        { content: formatD(main.due_date),   styles: { fontSize: 7.5, textColor: C.gray400, halign: 'center' } },
      ])

      for (const sub of subMap.get(main.id) ?? []) {
        const ssc  = statusChip(sub.status)
        const spc  = priorityChip(sub.priority)
        const spct = sub.progress ?? 0
        pctLookup.push(spct)
        statusLookup.push(sub.status)
        priorityLookup.push(sub.priority)

        tableBody.push([
          { content: '', styles: { halign: 'center' } },
          { content: `  â†³  ${sub.title}`, styles: { fontSize: 7, textColor: C.gray500 } },
          { content: ssc.text, styles: { textColor: ssc.fg, fontSize: 7, halign: 'center', fontStyle: 'bold' } },
          { content: spc.text, styles: { textColor: spc.fg, fontSize: 7, halign: 'center', fontStyle: 'bold' } },
          { content: String(spct), styles: { fontSize: 0.5, halign: 'center', textColor: C.white } },
          { content: getAssignees(sub, memberMap), styles: { fontSize: 7, textColor: C.gray500 } },
          { content: formatD(sub.start_date), styles: { fontSize: 7, textColor: C.gray400, halign: 'center' } },
          { content: formatD(sub.due_date),   styles: { fontSize: 7, textColor: C.gray400, halign: 'center' } },
        ])
      }
    }

    autoTable(doc, {
      startY: curY,
      head: [HEADERS],
      body: tableBody,
      margin: { left: M, right: M, top: 14 },
      columnStyles: COL_W.reduce<Record<number, { cellWidth: number }>>((acc, w, i) => {
        acc[i] = { cellWidth: w }
        return acc
      }, {}),
      headStyles: {
        fillColor: C.gray50,
        textColor: C.gray700,
        fontStyle: 'bold',
        fontSize: 7.5,
        cellPadding: { top: 3, bottom: 3, left: 3, right: 3 },
        halign: 'center',
        lineColor: C.gray200,
        lineWidth: 0.2,
      },
      bodyStyles: {
        fontSize: 8,
        cellPadding: { top: 4, bottom: 4, left: 3, right: 3 },
        textColor: C.gray700,
        lineColor: C.gray200,
        lineWidth: 0.2,
        minCellHeight: 11,
        fillColor: C.white,
      },
      alternateRowStyles: { fillColor: C.white },
      tableLineColor: C.gray200,
      tableLineWidth: 0.2,
      didDrawPage: (data) => {
        if (data.pageNumber > 1) drawContinuationHeader()
      },
      didDrawCell: (data) => {
        if (data.section !== 'body') return

        const rowIdx = data.row.index
        const colIdx = data.column.index
        const cx = data.cell.x
        const cy = data.cell.y
        const cw = data.cell.width
        const ch = data.cell.height

        // Column 0: priority accent bar
        if (colIdx === 0) {
          const prio = priorityLookup[rowIdx] ?? ''
          if (prio === 'critical' || prio === 'high') {
            const accentC: [number,number,number] = prio === 'critical' ? C.red : C.orange
            doc.setFillColor(...accentC)
            doc.rect(cx, cy, 2.5, ch, 'F')
          }
          return
        }

        // Column 1: strikethrough + indent guide
        if (colIdx === 1) {
          const isSub  = (data.cell.text[0] ?? '').includes('â†³')
          const isDone = statusLookup[rowIdx] === 'completed'
          if (isSub) {
            doc.setDrawColor(...C.gray300)
            doc.setLineWidth(0.5)
            doc.line(cx + 4, cy + 1.5, cx + 4, cy + ch - 1.5)
          }
          if (isDone) {
            doc.setDrawColor(...C.gray400)
            doc.setLineWidth(0.4)
            doc.line(cx + 3.5, cy + ch / 2 - 0.5, cx + cw - 3.5, cy + ch / 2 - 0.5)
          }
          return
        }

        // Column PROGRESS_COL: mini bar
        if (colIdx !== PROGRESS_COL) return

        const pctVal = pctLookup[rowIdx] ?? 0
        doc.setFillColor(...C.white)
        doc.rect(cx + 0.6, cy + 0.6, cw - 1.2, ch - 1.2, 'F')

        const bx = cx + 3
        const bw = cw - 6
        const bh = 2.8
        const by = cy + (ch - bh) / 2 - 1.5
        const fc: [number,number,number] =
          pctVal === 100 ? C.green : pctVal >= 60 ? C.blue : pctVal > 0 ? C.amberMid : C.gray300
        miniBar(doc, bx, by, bw, bh, pctVal, C.gray100, fc)

        const lc: [number,number,number] =
          pctVal === 100 ? C.green : pctVal >= 60 ? C.blue : pctVal > 0 ? C.amberMid : C.gray400
        doc.setFontSize(6.5)
        doc.setFont('helvetica', 'bold')
        doc.setTextColor(...lc)
        doc.text(`${pctVal}%`, cx + cw / 2, by + bh + 3.5, { align: 'center' })
      },
    })

    // @ts-expect-error jspdf-autotable appends lastAutoTable
    curY = (doc.lastAutoTable?.finalY ?? curY + 10) + 6
  }

  // â”€â”€ FOOTER PASS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  const totalPages = (doc.internal as unknown as { getNumberOfPages(): number }).getNumberOfPages()
  for (let p = 1; p <= totalPages; p++) {
    doc.setPage(p)
    const fy = pageH - 4.5
    doc.setDrawColor(...C.gray200)
    doc.setLineWidth(0.3)
    doc.line(M, pageH - 8.5, pageW - M, pageH - 8.5)
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(7)
    doc.setTextColor(...C.gray400)
    doc.text(project.title, M, fy)
    doc.text(`Page ${p} of ${totalPages}`, pageW / 2, fy, { align: 'center' })
    doc.text(today(), pageW - M, fy, { align: 'right' })
  }

  doc.save(`${slugify(project.title)}-report-${today()}.pdf`)
}
