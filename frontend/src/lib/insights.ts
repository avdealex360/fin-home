/** Client-side derivations for the analytics screen.
 *
 * Everything here is computed from data the API already returns
 * (`/api/transactions` for the month + `/api/dashboard`), so no backend
 * changes are required to ship the richer statistics screen. */

import type { MonthOutlook, Transaction } from './api'

export interface MonthPace {
  day: number
  daysInMonth: number
  daysLeft: number
  spent: number
  /** Straight-line projection of the month's total at the current pace. */
  projected: number
  perDaySoFar: number
  /** What you may spend per remaining day to land exactly on `planLimit`. */
  perDayToFit: number
  overBy: number
}

/** Pace for the VIEWED month, not the calendar month: a past month is fully
 *  elapsed (day = last day), the current month uses today, a future month has
 *  zero elapsed days — so browsing history never shows a bogus projection. */
export function monthPace(spent: number, planLimit: number, year?: number, month?: number): MonthPace {
  const now = new Date()
  const y = year ?? now.getFullYear()
  const m = month ?? now.getMonth() + 1
  const daysInMonth = new Date(y, m, 0).getDate()
  const isCurrent = y === now.getFullYear() && m === now.getMonth() + 1
  const isPast = y < now.getFullYear() || (y === now.getFullYear() && m < now.getMonth() + 1)
  const day = isCurrent ? Math.min(now.getDate(), daysInMonth) : isPast ? daysInMonth : 0
  const daysLeft = Math.max(daysInMonth - day, 0)
  const perDaySoFar = day > 0 ? spent / day : 0
  const projected = perDaySoFar * daysInMonth
  return {
    day,
    daysInMonth,
    daysLeft,
    spent,
    projected,
    perDaySoFar,
    perDayToFit: daysLeft > 0 ? Math.max(planLimit - spent, 0) / daysLeft : 0,
    overBy: Math.max(projected - planLimit, 0),
  }
}

/** Expense total per day-of-month (index 0 = day 1). */
export function dailySpend(txs: Transaction[], daysInMonth: number): number[] {
  const out = new Array(daysInMonth).fill(0)
  for (const t of txs) {
    if (t.type !== 'expense') continue
    const d = new Date(t.date).getDate()
    if (d >= 1 && d <= daysInMonth) out[d - 1] += t.amount
  }
  return out
}

export function cumulative(series: number[], upToDay: number): number[] {
  let acc = 0
  return series.slice(0, upToDay).map((v) => (acc += v))
}

/** Weekday index (0 = Monday) of the 1st of the month. */
export function firstWeekday(year: number, month: number): number {
  return (new Date(year, month - 1, 1).getDay() + 6) % 7
}

export interface RecurringSplit {
  recurring: number
  variable: number
  recurringNames: string[]
}

/** "Regular" categories (per the outlook: present every past month with a
 *  stable amount) are the payments that will arrive again regardless of
 *  behaviour. Everything else is what you can actually steer. */
export function recurringSplit(
  monthTxs: Transaction[],
  kindByCategory: Record<number, string>,
): RecurringSplit {
  let recurring = 0
  let variable = 0
  const names = new Set<string>()
  for (const t of monthTxs) {
    if (t.type !== 'expense') continue
    const kind = t.category_id ? kindByCategory[t.category_id] : undefined
    if (kind === 'regular') {
      recurring += t.amount
      if (t.category_name) names.add(t.category_name)
    } else {
      variable += t.amount
    }
  }
  return { recurring, variable, recurringNames: [...names] }
}

export interface Insight {
  tone: 'red' | 'yellow' | 'blue' | 'green'
  icon: string
  title: string
  text: string
}

export interface InsightInput {
  categories: { name: string; spent: number; limit: number; avg3: number }[]
  txs: Transaction[]
  outlook: MonthOutlook | null
  /** Sum of this month's category limits (or the income-based fallback). */
  planLimit: number
}

/** Automatic observations, ordered by how much money is at stake. */
export function buildInsights({ categories, txs, outlook, planLimit }: InsightInput): Insight[] {
  const daysLeft = outlook?.days_left ?? 0
  const out: Insight[] = []
  const fmt = (n: number) => Math.round(n).toLocaleString('ru-RU').replace(/\u00a0/g, ' ')

  for (const c of categories) {
    if (c.limit > 0 && c.spent > c.limit) {
      out.push({
        tone: 'red',
        icon: 'ti-alert-triangle',
        title: `${c.name}: перерасход ${fmt(c.spent - c.limit)} ₽`,
        text: `Потрачено ${fmt(c.spent)} ₽ при лимите ${fmt(c.limit)} ₽.` +
          (c.avg3 > 0 ? ` Это ${Math.round(((c.spent - c.avg3) / c.avg3) * 100)}% к среднему за 3 месяца.` : ''),
      })
    } else if (c.limit > 0 && c.avg3 > 0 && c.spent < c.avg3 * 0.85 && daysLeft > 0 && daysLeft <= 10) {
      out.push({
        tone: 'green',
        icon: 'ti-confetti',
        title: `${c.name}: экономия ${fmt(c.avg3 - c.spent)} ₽`,
        text: 'Тратите заметно меньше обычного. Разницу можно переложить в накопления.',
      })
    }
  }

  // Unusually large one-off charges. The outlook already excludes regular
  // categories (rent, taxes, instalments) so a big but expected bill is not a spike.
  if (outlook && outlook.history_months > 0) {
    for (const s of outlook.oneoffs.slice(0, 2)) {
      out.push({
        tone: 'blue',
        icon: 'ti-flame',
        title: `Разовая трата: ${s.category_name ?? 'без категории'} ${fmt(s.amount)} ₽`,
        text: (outlook.median_cheque > 0 ? `В ${(s.amount / outlook.median_cheque).toFixed(1)} раза выше вашего обычного чека.` : '') +
          (s.comment ? ` ${s.comment}` : ''),
      })
    }
  } else {
    const amounts = txs.filter((t) => t.type === 'expense').map((t) => t.amount).sort((a, b) => a - b)
    if (amounts.length > 6) {
      const median = amounts[Math.floor(amounts.length / 2)]
      const spikes = txs
        .filter((t) => t.type === 'expense' && t.amount > median * 2.5)
        .sort((a, b) => b.amount - a.amount)
        .slice(0, 2)
      for (const s of spikes) {
        out.push({
          tone: 'blue',
          icon: 'ti-flame',
          title: `Крупная трата: ${s.category_name ?? 'без категории'} ${fmt(s.amount)} ₽`,
          text: `В ${(s.amount / median).toFixed(1)} раза выше вашего обычного чека.` + (s.comment ? ` ${s.comment}` : ''),
        })
      }
    }
  }

  const uncategorised = txs.filter((t) => t.type === 'expense' && !t.category_id)
  if (uncategorised.length) {
    out.push({
      tone: 'yellow',
      icon: 'ti-help-circle',
      title: `${uncategorised.length} операц. без категории`,
      text: `На ${fmt(uncategorised.reduce((s, t) => s + t.amount, 0))} ₽. Пока они не разобраны, лимиты считаются неточно.`,
    })
  }

  // Forecast vs plan — from the family's own typical months, not a per-day pace.
  if (outlook && outlook.history_months > 0 && outlook.days_left > 0 && planLimit > 0) {
    const over = outlook.forecast_total - planLimit
    if (over > planLimit * 0.03) {
      out.unshift({
        tone: 'red',
        icon: 'ti-trending-up',
        title: `По обычным месяцам выйдет ≈ ${fmt(outlook.forecast_total)} ₽ — на ${fmt(over)} ₽ больше плана`,
        text: `Уже потрачено ${fmt(outlook.spent)} ₽, и обычно за оставшиеся дни уходит ещё ≈ ${fmt(outlook.expected_remaining)} ₽.`,
      })
    }
  }
  // Same day last month — rent and instalments are in both, so this is a fair comparison.
  if (outlook && outlook.prev_same_day && outlook.prev_same_day > 0 && outlook.day > 3) {
    const delta = ((outlook.spent - outlook.prev_same_day) / outlook.prev_same_day) * 100
    if (Math.abs(delta) >= 15) {
      out.push({
        tone: delta > 0 ? 'yellow' : 'green',
        icon: delta > 0 ? 'ti-arrow-up-right' : 'ti-arrow-down-right',
        title: `К ${outlook.day}-му: ${delta > 0 ? '+' : '−'}${Math.abs(Math.round(delta))}% к прошлому месяцу`,
        text: `Сейчас ${fmt(outlook.spent)} ₽ против ${fmt(outlook.prev_same_day)} ₽ на ту же дату.`,
      })
    }
  }

  return out.slice(0, 5)
}
