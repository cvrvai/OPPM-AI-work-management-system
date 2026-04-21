/**
 * oppmSheetBuilder.ts — Scalable OPPM layout generator for FortuneSheet.
 *
 * Builds a FortuneSheet-compatible sheet model that mirrors the classic
 * One Page Project Manager template. Section dimensions scale based on
 * configurable data counts (sub-objectives, tasks, dates, members).
 *
 * Usage:
 *   buildOppmScratchSheet()                        // default 6/16/12/5
 *   buildOppmScratchSheet({ subObjCount: 2 })      // only 2 sub-obj cols
 *   buildOppmScratchSheet({ taskCount: 5 })         // only 5 task rows
 */

/* eslint-disable @typescript-eslint/no-explicit-any */

export const OPPM_GENERATED_LAYOUT_VERSION = 'scalable-v5'
export const OPPM_GENERATED_FILE_NAME = 'OPPM Layout'

// ════════════════════════════════════════════════════════════
// Configuration
// ════════════════════════════════════════════════════════════

export interface OppmLayoutConfig {
  /** Sub-objective columns (1–6, default 6) */
  subObjCount: number
  /** Task rows in task grid (1–20, default 16) */
  taskCount: number
  /** Timeline date columns (0–24, default 12). 0 = no date section. */
  dateCount: number
  /** Member/owner columns (1–6, default 5) */
  memberCount: number
}

const DEFAULT_CONFIG: OppmLayoutConfig = {
  subObjCount: 6,
  taskCount: 16,
  dateCount: 12,
  memberCount: 5,
}

// ════════════════════════════════════════════════════════════
// Border constants
// ════════════════════════════════════════════════════════════

const BLK = '#000000'
const THIN = { style: 1, color: BLK }
const MED = { style: 8, color: BLK }
const GREY_BG = '#D9D9D9'
const GREEN_BG = '#00B050'
const YELLOW_BG = '#FFD700'
const RED_BG = '#FF0000'

type BS = { style: number; color: string }

// ════════════════════════════════════════════════════════════
// Geometry — all coordinates computed from config
// ════════════════════════════════════════════════════════════

const TASK_COLS = 5   // columns merged for task text (H–L in reference template)
const LEGEND_COLS = 4 // fixed right-side legend columns
const INFO_ROWS = 3   // project info rows — 3 rows visible in reference (rows 2-4)
const GAP_ROWS = 4    // gap rows between separator and people row
const BOTTOM_ROWS = 6 // rows in bottom summary section

interface Geo {
  // Column spans (0-indexed, inclusive)
  soS: number; soE: number   // sub-objective
  tkS: number; tkE: number   // task text
  dtS: number; dtE: number   // date/timeline
  mmS: number; mmE: number   // member/owner
  lgS: number; lgE: number   // legend
  lastCol: number

  // Row spans (0-indexed, inclusive)
  hdrRow: number             // header (Project Leader / Name)
  infS: number; infE: number // project info block
  chRow: number              // column headers
  trS: number; trE: number   // task rows
  sepRow: number             // separator bar
  gapS: number; gapE: number // gap rows (identity panel in legend cols)
  pplRow: number             // "# People" row
  btLbl: number              // bottom label row
  btS: number; btE: number   // bottom section
  lastRow: number

  hasDates: boolean
}

function computeGeo(cfg: OppmLayoutConfig): Geo {
  const hasDates = cfg.dateCount > 0

  // ── Columns ──
  const soS = 1
  const soE = soS + cfg.subObjCount - 1
  const tkS = soE + 1
  const tkE = tkS + TASK_COLS - 1
  const dtS = tkE + 1
  const dtE = hasDates ? dtS + cfg.dateCount - 1 : tkE
  const mmS = (hasDates ? dtE : tkE) + 1
  const mmE = mmS + cfg.memberCount - 1
  const lgS = mmE + 1
  const lgE = lgS + LEGEND_COLS - 1

  // ── Rows ──
  const hdrRow = 1
  const infS = 2
  const infE = infS + INFO_ROWS - 1         // 5
  const chRow = infE + 1                     // 6
  const trS = chRow + 1                      // 7
  const trE = trS + cfg.taskCount - 1
  const sepRow = trE + 1
  const gapS = sepRow + 1
  const gapE = gapS + GAP_ROWS - 1
  const pplRow = gapE + 1
  const btLbl = pplRow + 1
  const btS = btLbl + 1
  const btE = btS + BOTTOM_ROWS - 1
  const lastRow = btE + 1

  return {
    soS, soE, tkS, tkE, dtS, dtE, mmS, mmE, lgS, lgE,
    lastCol: lgE,
    hdrRow, infS, infE, chRow, trS, trE,
    sepRow, gapS, gapE, pplRow, btLbl, btS, btE, lastRow,
    hasDates,
  }
}

// ════════════════════════════════════════════════════════════
// Cell helpers
// ════════════════════════════════════════════════════════════

interface CellOpts {
  bold?: boolean
  fontSize?: number
  bg?: string
  hAlign?: number   // 0=center, 1=left, 2=right
  vAlign?: number   // 0=middle, 1=top, 2=bottom
  fc?: string       // font color
  wrap?: boolean
  rotation?: string // tr value: "0"|"1"|"2"|"3"|"4"|"5"
}

function mkCell(r: number, c: number, text: string, opts?: CellOpts): any {
  const v: any = {
    v: text,
    m: text,
    ct: { fa: 'General', t: 's' },
  }
  if (opts?.bold) v.bl = 1
  if (opts?.fontSize) v.fs = opts.fontSize
  if (opts?.bg) v.bg = opts.bg
  if (opts?.hAlign !== undefined) v.ht = opts.hAlign
  if (opts?.vAlign !== undefined) v.vt = opts.vAlign
  if (opts?.fc) v.fc = opts.fc
  if (opts?.wrap) v.tb = '2'
  if (opts?.rotation) v.tr = opts.rotation
  return { r, c, v }
}

/** Add a merged cell + its placeholder references. */
function addMerge(
  merges: Record<string, any>,
  cells: any[],
  r: number, c: number,
  rs: number, cs: number,
  text: string,
  opts?: CellOpts,
) {
  merges[`${r}_${c}`] = { r, c, rs, cs }
  const cv = mkCell(r, c, text, opts)
  cv.v.mc = { r, c, rs, cs }
  cells.push(cv)
  for (let ri = r; ri < r + rs; ri++) {
    for (let ci = c; ci < c + cs; ci++) {
      if (ri === r && ci === c) continue
      cells.push({ r: ri, c: ci, v: { mc: { r, c } } })
    }
  }
}

// ════════════════════════════════════════════════════════════
// Border helpers
// ════════════════════════════════════════════════════════════

function borderCell(r: number, c: number, sides: {
  l?: BS; r?: BS; t?: BS; b?: BS
}): any {
  return {
    rangeType: 'cell',
    value: {
      row_index: r,
      col_index: c,
      ...(sides.l && { l: sides.l }),
      ...(sides.r && { r: sides.r }),
      ...(sides.t && { t: sides.t }),
      ...(sides.b && { b: sides.b }),
    },
  }
}

/** Draw outer border around a rectangle. */
function drawFrame(
  borders: any[], r1: number, c1: number, r2: number, c2: number, s: BS = MED,
) {
  for (let c = c1; c <= c2; c++) {
    borders.push(borderCell(r1, c, { t: s }))
    borders.push(borderCell(r2, c, { b: s }))
  }
  for (let r = r1; r <= r2; r++) {
    borders.push(borderCell(r, c1, { l: s }))
    borders.push(borderCell(r, c2, { r: s }))
  }
}

/** Draw horizontal line (bottom of row) across columns. */
function drawHLine(
  borders: any[], row: number, c1: number, c2: number,
  side: 'b' | 't' = 'b', s: BS = THIN,
) {
  for (let c = c1; c <= c2; c++) {
    borders.push(borderCell(row, c, { [side]: s }))
  }
}

/** Draw vertical line (right of col) across rows. */
function drawVLine(
  borders: any[], col: number, r1: number, r2: number,
  side: 'l' | 'r' = 'r', s: BS = THIN,
) {
  for (let r = r1; r <= r2; r++) {
    borders.push(borderCell(r, col, { [side]: s }))
  }
}

/** Draw full thin grid inside a rectangle. */
function drawGrid(
  borders: any[], r1: number, c1: number, r2: number, c2: number, s: BS = THIN,
) {
  for (let r = r1; r <= r2; r++) {
    for (let c = c1; c <= c2; c++) {
      borders.push(borderCell(r, c, { l: s, r: s, t: s, b: s }))
    }
  }
}

// ════════════════════════════════════════════════════════════
// Section builders
// ════════════════════════════════════════════════════════════

/** Section 1: Header — Project Leader / Project Name
 *
 * Sub-obj columns (soS..soE) are BLANK in this row — no box covers them.
 * "Project Leader:" covers only task-text columns (tkS..tkE).
 * "Project Name:"   covers date + member + legend columns (dtS..lastCol).
 */
function buildHeader(g: Geo, cells: any[], borders: any[], merges: Record<string, any>) {
  // "Project Leader:" — task cols only (H–L in reference)
  addMerge(merges, cells, g.hdrRow, g.tkS, 1, g.tkE - g.tkS + 1,
    'Project Leader:', { bold: true, fontSize: 12, bg: GREY_BG, hAlign: 0 })

  // "Project Name:" — dates + members + legend
  addMerge(merges, cells, g.hdrRow, g.dtS, 1, g.lastCol - g.dtS + 1,
    'Project Name:', { bold: true, fontSize: 12, bg: GREY_BG, hAlign: 0 })

  drawFrame(borders, g.hdrRow, g.tkS, g.hdrRow, g.lastCol, MED)
  drawVLine(borders, g.tkE, g.hdrRow, g.hdrRow, 'r', THIN)
}

/** Section 2: Project Info — Objective, Deliverable, Start Date, Deadline
 *
 * Starts at tkS (same x as "Project Leader:"). Sub-obj columns (soS..soE)
 * are left as plain empty grid in these rows, matching the reference image.
 */
function buildInfoBlock(g: Geo, cells: any[], borders: any[], merges: Record<string, any>) {
  const infoText = [
    'Project Objective: Text',
    'Deliverable Output : Text',
    'Start Date:',
    'Deadline:',
  ].join('\n')

  addMerge(merges, cells, g.infS, g.tkS, INFO_ROWS, g.lastCol - g.tkS + 1,
    infoText, { bold: true, fontSize: 10, hAlign: 1, vAlign: 1, wrap: true })

  drawFrame(borders, g.infS, g.tkS, g.infE, g.lastCol, MED)
}

/** Section 3: Column Headers — Sub objective, Major Tasks, etc. */
function buildColumnHeaders(
  g: Geo, cfg: OppmLayoutConfig,
  cells: any[], borders: any[], merges: Record<string, any>,
) {
  const r = g.chRow

  // "Sub objective" over sub-obj columns
  addMerge(merges, cells, r, g.soS, 1, cfg.subObjCount,
    'Sub objective', { bold: true, fontSize: 9, bg: GREY_BG, hAlign: 0 })

  // "Major Tasks    (Deadline)" over task columns
  addMerge(merges, cells, r, g.tkS, 1, TASK_COLS,
    'Major Tasks    (Deadline)', { bold: true, fontSize: 9, bg: GREY_BG, hAlign: 0 })

  // "Project Completed By: Text" over date columns
  if (g.hasDates) {
    addMerge(merges, cells, r, g.dtS, 1, cfg.dateCount,
      'Project Completed By: Text', { bold: true, fontSize: 9, bg: GREY_BG, hAlign: 0 })
  }

  // "Owner / Priority" over member columns
  addMerge(merges, cells, r, g.mmS, 1, cfg.memberCount,
    'Owner / Priority', { bold: true, fontSize: 9, bg: GREY_BG, hAlign: 0 })

  // Legend header (empty gray)
  addMerge(merges, cells, r, g.lgS, 1, LEGEND_COLS,
    '', { bg: GREY_BG })

  // Borders — outer frame + medium section dividers
  drawFrame(borders, r, g.soS, r, g.lastCol, MED)
  drawVLine(borders, g.soE, r, r, 'r', MED)
  drawVLine(borders, g.tkE, r, r, 'r', MED)
  if (g.hasDates) {
    drawVLine(borders, g.dtE, r, r, 'r', MED)
  }
  drawVLine(borders, g.mmE, r, r, 'r', MED)
}

/** Section 4: Task Grid — sub-obj checkmarks, task text, date grid, member grid */
function buildTaskGrid(
  g: Geo, cfg: OppmLayoutConfig,
  cells: any[], borders: any[], merges: Record<string, any>,
) {
  // ── Placeholder task names ──
  let idx = 0
  let mainNum = 1
  while (idx < cfg.taskCount) {
    const r = g.trS + idx
    // Main task row
    addMerge(merges, cells, r, g.tkS, 1, TASK_COLS,
      `${mainNum}. Main task ${mainNum}`,
      { bold: true, fontSize: 9, hAlign: 1 })
    idx++

    // Sub-tasks (up to 3 per main task) — blue text matching reference
    for (let sub = 1; sub <= 3 && idx < cfg.taskCount; sub++) {
      const sr = g.trS + idx
      addMerge(merges, cells, sr, g.tkS, 1, TASK_COLS,
        `    ${mainNum}.${sub}   Sub task ${sub}`,
        { fontSize: 9, hAlign: 1, fc: '#0070C0' })
      idx++
    }
    mainNum++
  }

  // ── Borders ──

  // Sub-objective grid (full grid for checkmark cells)
  drawGrid(borders, g.trS, g.soS, g.trE, g.soE, THIN)

  // Task text column borders (left/right + row separators)
  for (let r = g.trS; r <= g.trE; r++) {
    drawHLine(borders, r, g.tkS, g.tkE, 'b', THIN)
  }
  drawVLine(borders, g.tkS, g.trS, g.trE, 'l', THIN)
  drawVLine(borders, g.tkE, g.trS, g.trE, 'r', THIN)

  // Date grid
  if (g.hasDates) {
    drawGrid(borders, g.trS, g.dtS, g.trE, g.dtE, THIN)
  }

  // Member grid
  drawGrid(borders, g.trS, g.mmS, g.trE, g.mmE, THIN)

  // Legend column area (just outer borders, no internal grid)
  drawFrame(borders, g.trS, g.lgS, g.trE, g.lgE, THIN)

  // Medium vertical section dividers — spanning full task grid height
  drawVLine(borders, g.soE, g.trS, g.trE, 'r', MED)
  drawVLine(borders, g.tkE, g.trS, g.trE, 'r', MED)
  if (g.hasDates) {
    drawVLine(borders, g.dtE, g.trS, g.trE, 'r', MED)
  }
  drawVLine(borders, g.mmE, g.trS, g.trE, 'r', MED)

  // Section outer frame
  drawFrame(borders, g.trS, g.soS, g.trE, g.lastCol, MED)
}

/** Section 5: Separator bar */
function buildSeparator(g: Geo, cells: any[], borders: any[]) {
  for (let c = g.soS; c <= g.lastCol; c++) {
    cells.push(mkCell(g.sepRow, c, '', { bg: GREY_BG }))
  }
  drawFrame(borders, g.sepRow, g.soS, g.sepRow, g.lastCol, MED)
}

/** Section 6: Priority Legend panel (in legend cols, near top of task grid) */
function buildPriorityLegend(
  g: Geo, cells: any[], borders: any[], merges: Record<string, any>,
) {
  const startR = g.trS
  const entries = [
    { key: 'A', label: 'Primary/Owner' },
    { key: 'B', label: 'Primary Helper' },
    { key: 'C', label: 'Secondary Helper' },
  ]

  // "Priority" header
  addMerge(merges, cells, startR, g.lgS, 1, LEGEND_COLS,
    'Priority', { bold: true, fontSize: 9, hAlign: 0 })

  for (let i = 0; i < entries.length; i++) {
    const r = startR + 1 + i
    cells.push(mkCell(r, g.lgS, entries[i].key,
      { bold: true, fontSize: 9, hAlign: 0 }))
    addMerge(merges, cells, r, g.lgS + 1, 1, LEGEND_COLS - 1,
      entries[i].label, { fontSize: 9, hAlign: 1 })
  }

  drawGrid(borders, startR, g.lgS, startR + entries.length, g.lgE, THIN)
}

/** Section 7: Identity Symbol panel (in legend cols, in gap area) */
function buildIdentitySymbol(
  g: Geo, cells: any[], borders: any[], merges: Record<string, any>,
) {
  const r0 = g.gapS

  // "Project Identity Symbol" header
  addMerge(merges, cells, r0, g.lgS, 1, LEGEND_COLS,
    'Project Identity Symbol', { bold: true, fontSize: 9, hAlign: 0 })

  // Symbol row: □  ●  ■
  const symbols = ['\u25A1', '\u25CF', '\u25A0']
  for (let i = 0; i < 3 && g.lgS + i <= g.lgE; i++) {
    cells.push(mkCell(r0 + 1, g.lgS + i, symbols[i],
      { bold: true, fontSize: 10, hAlign: 0 }))
  }

  // Label row: Start, In Progress, Complete
  const labels = ['Start', 'In Progress', 'Complete']
  for (let i = 0; i < 3 && g.lgS + i <= g.lgE; i++) {
    cells.push(mkCell(r0 + 2, g.lgS + i, labels[i],
      { fontSize: 8, hAlign: 0 }))
  }

  // Color row: Green, Yellow, Red
  const colors: Array<{ label: string; bg: string }> = [
    { label: 'Green', bg: GREEN_BG },
    { label: 'Yellow', bg: YELLOW_BG },
    { label: 'Red', bg: RED_BG },
  ]
  for (let i = 0; i < 3 && g.lgS + i <= g.lgE; i++) {
    cells.push(mkCell(r0 + 3, g.lgS + i, colors[i].label,
      { fontSize: 8, hAlign: 0, bg: colors[i].bg, fc: i === 2 ? '#FFFFFF' : '#000000' }))
  }

  drawGrid(borders, r0, g.lgS, r0 + 3, g.lgE, THIN)
}

/** Section 8: "# People working" row */
function buildPeopleRow(
  g: Geo, cells: any[], borders: any[], merges: Record<string, any>,
) {
  addMerge(merges, cells, g.pplRow, g.soS, 1, g.lastCol - g.soS + 1,
    '# People working on the project:',
    { bold: true, fontSize: 10, hAlign: 2, bg: GREY_BG })
  drawFrame(borders, g.pplRow, g.soS, g.pplRow, g.lastCol, THIN)
}

/** Section 9: Bottom summary — sub-obj labels, task/date labels, member labels */
function buildBottomSection(
  g: Geo, cfg: OppmLayoutConfig,
  cells: any[], borders: any[], merges: Record<string, any>,
) {
  // ── Bottom label row: sub-obj numbers ──
  for (let i = 0; i < cfg.subObjCount; i++) {
    cells.push(mkCell(g.btLbl, g.soS + i, `${i + 1}`,
      { bold: true, fontSize: 9, hAlign: 0 }))
  }

  // ── Sub-objective labels (rotated, in bottom rows) ──
  for (let i = 0; i < cfg.subObjCount; i++) {
    cells.push(mkCell(g.btS, g.soS + i, `Sub Obj ${i + 1}`,
      { bold: true, fontSize: 8, hAlign: 0, rotation: '4' }))
  }

  // "Sub Objectives" label at bottom of sub-obj columns
  addMerge(merges, cells, g.btE, g.soS, 1, cfg.subObjCount,
    'Sub Objectives', { bold: true, fontSize: 10, hAlign: 0 })

  // "Major Tasks" label in task columns
  addMerge(merges, cells, g.btS, g.tkS, 3, TASK_COLS,
    'Major Tasks', { bold: true, fontSize: 11, hAlign: 0, vAlign: 0 })

  // "Target Dates" label
  addMerge(merges, cells, g.btS + 3, g.tkS, 2, TASK_COLS,
    'Target Dates', { bold: true, fontSize: 11, hAlign: 0, vAlign: 0 })

  // Date column placeholders (rotated)
  if (g.hasDates) {
    for (let i = 0; i < cfg.dateCount; i++) {
      cells.push(mkCell(g.btS, g.dtS + i, '',
        { fontSize: 8, rotation: '4' }))
    }
  }

  // Member labels (rotated)
  const memberLabels = [
    'Project Leader', 'Member 1', 'Member 2',
    'Member 3', 'Member 4', 'Member 5',
  ]
  for (let i = 0; i < cfg.memberCount; i++) {
    const lbl = i < memberLabels.length ? memberLabels[i] : `Member ${i}`
    cells.push(mkCell(g.btS, g.mmS + i, lbl,
      { bold: true, fontSize: 8, hAlign: 0, rotation: '4' }))
  }

  // ── Borders ──
  drawFrame(borders, g.btLbl, g.soS, g.btE, g.lastCol, MED)

  // Sub-obj grid in bottom
  drawGrid(borders, g.btLbl, g.soS, g.btE, g.soE, THIN)

  // Vertical section dividers — medium to match task grid
  drawVLine(borders, g.tkE, g.btLbl, g.btE, 'r', MED)
  if (g.hasDates) {
    drawVLine(borders, g.dtE, g.btLbl, g.btE, 'r', MED)
  }
  drawVLine(borders, g.mmE, g.btLbl, g.btE, 'r', MED)
}

// ════════════════════════════════════════════════════════════
// Dimensions
// ════════════════════════════════════════════════════════════

function buildColumnWidths(g: Geo): Record<number, number> {
  const w: Record<number, number> = {}
  w[0] = 30  // spacer / row-number margin
  // Sub-objective: 6 narrow columns
  for (let c = g.soS; c <= g.soE; c++) w[c] = 25
  // Task text: first col wider (task number), rest medium
  w[g.tkS] = 80
  for (let c = g.tkS + 1; c <= g.tkE; c++) w[c] = 55
  // Date/timeline columns
  if (g.hasDates) {
    for (let c = g.dtS; c <= g.dtE; c++) w[c] = 38
  }
  // Owner/member columns
  for (let c = g.mmS; c <= g.mmE; c++) w[c] = 60
  // Legend columns
  w[g.lgS] = 40
  for (let c = g.lgS + 1; c <= g.lgE; c++) w[c] = 60
  return w
}

function buildRowHeights(g: Geo): Record<number, number> {
  const h: Record<number, number> = {}
  h[0] = 8
  h[g.hdrRow] = 28
  // Info block: 3 rows × 22px = 66px total, fitting 4 wrapped lines
  for (let r = g.infS; r <= g.infE; r++) h[r] = 22
  h[g.chRow] = 25
  for (let r = g.trS; r <= g.trE; r++) h[r] = 20
  h[g.sepRow] = 30
  for (let r = g.gapS; r <= g.gapE; r++) h[r] = 22
  h[g.pplRow] = 25
  h[g.btLbl] = 20
  for (let r = g.btS; r <= g.btE; r++) h[r] = 55
  return h
}

// ════════════════════════════════════════════════════════════
// Public API
// ════════════════════════════════════════════════════════════

/** Check whether a sheet object was generated by this builder. */
export function isOppmGeneratedSheet(sheet: any): boolean {
  return !!(sheet?.oppmGeneratedLayoutVersion)
}

/** Check whether a generated sheet is outdated vs current version. */
export function isOppmGeneratedSheetOutdated(sheet: any): boolean {
  return (
    isOppmGeneratedSheet(sheet) &&
    sheet.oppmGeneratedLayoutVersion !== OPPM_GENERATED_LAYOUT_VERSION
  )
}

/**
 * Build a FortuneSheet-compatible sheet array for the OPPM layout scaffold.
 *
 * All section dimensions scale with `config`:
 * - subObjCount → number of sub-objective columns (1–6)
 * - taskCount   → number of task rows (1–20)
 * - dateCount   → number of date/timeline columns (0–24)
 * - memberCount → number of member columns (1–6)
 */
export function buildOppmScratchSheet(config?: Partial<OppmLayoutConfig>): any[] {
  const cfg: OppmLayoutConfig = { ...DEFAULT_CONFIG, ...config }
  cfg.subObjCount = Math.max(1, Math.min(6, cfg.subObjCount))
  cfg.taskCount = Math.max(1, Math.min(20, cfg.taskCount))
  cfg.dateCount = Math.max(0, Math.min(24, cfg.dateCount))
  cfg.memberCount = Math.max(1, Math.min(6, cfg.memberCount))

  const g = computeGeo(cfg)

  const cells: any[] = []
  const borders: any[] = []
  const merges: Record<string, any> = {}

  // Build each section
  buildHeader(g, cells, borders, merges)
  buildInfoBlock(g, cells, borders, merges)
  buildColumnHeaders(g, cfg, cells, borders, merges)
  buildTaskGrid(g, cfg, cells, borders, merges)
  buildSeparator(g, cells, borders)
  buildPriorityLegend(g, cells, borders, merges)
  buildIdentitySymbol(g, cells, borders, merges)
  buildPeopleRow(g, cells, borders, merges)
  buildBottomSection(g, cfg, cells, borders, merges)

  return [{
    name: OPPM_GENERATED_FILE_NAME,
    celldata: cells,
    config: {
      borderInfo: borders,
      merge: merges,
      columnlen: buildColumnWidths(g),
      rowlen: buildRowHeights(g),
    },
    row: g.lastRow + 10,
    column: g.lastCol + 5,
    oppmGeneratedLayoutVersion: OPPM_GENERATED_LAYOUT_VERSION,
  }]
}
