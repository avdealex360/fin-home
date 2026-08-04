const MONTHS = [
  '', 'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
  'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь',
]
const MONTHS_SHORT = [
  '', 'янв', 'фев', 'мар', 'апр', 'мая', 'июн',
  'июл', 'авг', 'сен', 'окт', 'ноя', 'дек',
]

export function money(value: number | null | undefined): string {
  if (value === null || value === undefined) return '0'
  const rounded = Math.round(value)
  return rounded.toLocaleString('ru-RU').replace(/,/g, ' ').replace(/\s/g, ' ')
}

/** USDC — токен с 6 знаками после точки, но в интерфейсе хватает двух. */
export function usdc(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return value
    .toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    .replace(/\s/g, ' ')
}

/** «2026-08-04T17:35:02» → «17:35». Пустая строка, если времени нет. */
export function timeOnly(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
}

export function monthName(m: number): string {
  return MONTHS[m] ?? String(m)
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getDate()} ${MONTHS_SHORT[d.getMonth() + 1]}`
}

export function shiftMonth(year: number, month: number, delta: number): [number, number] {
  let m = month + delta
  let y = year
  while (m < 1) { m += 12; y -= 1 }
  while (m > 12) { m -= 12; y += 1 }
  return [y, m]
}
