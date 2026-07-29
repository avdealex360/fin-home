/** Client-side derivations for the analytics screen.
 *
 * Everything here is computed from data the API already returns
 * (`/api/transactions` for the month + `/api/dashboard`), so no backend
 * changes are required to ship the richer statistics screen. */

import type { Transaction } from './api'

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

export function monthPace(spent: number, planLimit: number, ref = new Date()): MonthPace {
  const daysInMonth = new Date(ref.getFullYear(), ref.getMonth() + 1, 0).getDate()
  const day = Math.min(ref.getDate(), daysInMonth)
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

/** A category counts as "recurring" when it produced a charge in each of the
 *  last `minMonths` months — those are the payments that will arrive again
 *  regardless of behaviour. Everything else is what you can actually steer. */
export function recurringSplit(
  monthTxs: Transaction[],
  historyByCategory: Record<number, number>,
  minMonths = 3,
): RecurringSplit {
  let recurring = 0
  let variable = 0
  const names = new Set<string>()
  for (const t of monthTxs) {
    if (t.type !== 'expense') continue
    const months = t.category_id ? (historyByCategory[t.category_id] ?? 0) : 0
    if (months >= minMonths) {
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
  pace: MonthPace
}

/** Automatic observations, ordered by how much money is at stake. */
export function buildInsights({ categories, txs, pace }: InsightInput): Insight[] {
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
    } else if (c.limit > 0 && c.avg3 > 0 && c.spent < c.avg3 * 0.85 && pace.daysLeft <= 10) {
      out.push({
        tone: 'green',
        icon: 'ti-confetti',
        title: `${c.name}: экономия ${fmt(c.avg3 - c.spent)} ₽`,
        text: 'Тратите заметно меньше обычного. Разницу можно переложить в накопления.',
      })
    }
  }

  // Unusually large single charges: 2.5× the median expense of the month.
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
        text: `В ${(s.amount / median).toFixed(1)} раза выше вашего обычного чека.` +
          (s.comment ? ` ${s.comment}` : ''),
      })
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

  if (pace.overBy > 0) {
    out.unshift({
      tone: 'red',
      icon: 'ti-trending-up',
      title: `Темп выше плана: +${fmt(pace.overBy)} ₽ к концу месяца`,
      text: `Сейчас уходит ${fmt(pace.perDaySoFar)} ₽ в день. Чтобы уложиться — не больше ${fmt(pace.perDayToFit)} ₽ в день.`,
    })
  }

  return out.slice(0, 5)
}
