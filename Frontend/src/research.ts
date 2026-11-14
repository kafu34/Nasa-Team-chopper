import { num, str, type ApiObject } from './api'

export type TrendPoint = { analyte: string; subject: string; unit: string; timepoint: string; order: number | null; value: number }

/** Never connect unlike research measurements in a chart. */
export function trendRecords(records: ApiObject[]): TrendPoint[] {
  const groups = new Map<string, TrendPoint[]>()
  for (const record of records) {
    const value = num(record.value ?? record.VALUE)
    const analyte = str(record.analyte ?? record.ANALYTE, '')
    const subject = str(record.subject_id ?? record.SUBJECT_ID, '')
    const unit = str(record.unit ?? record.units ?? record.UNITS, '')
    if (value === null || !analyte || !subject || !unit) continue
    const point = { value, analyte, subject, unit, timepoint: str(record.timepoint, ''), order: num(record.timepoint_order) }
    const key = JSON.stringify([analyte, subject, unit])
    groups.set(key, [...(groups.get(key) ?? []), point])
  }
  return ([...groups.values()].sort((a, b) => b.length - a.length)[0] ?? []).sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
}
