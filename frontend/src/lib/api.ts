// Typed client for the fin-home JSON API. Same-origin in prod (Caddy),
// proxied to :8000 in dev (see vite.config.ts).

export interface Category {
  id: number
  name: string
  group: 'needs' | 'wants' | 'savings' | 'income'
  is_hidden: boolean
  sort_order: number
  allocation_level: number | null
  icon: string
  color: string
}

export interface User {
  id: number
  name: string
  is_active: boolean
}

export interface Transaction {
  id: number
  type: 'income' | 'expense' | 'transfer'
  amount: number
  date: string
  category_id: number | null
  category_name: string | null
  user_id: number | null
  user_name: string | null
  comment: string | null
  is_fully_allocated: boolean
  fund_id: number | null
  unallocated?: number
}

export interface GroupSummary {
  name: string
  label: string
  percent: number
  limit: number
  spent: number
  remaining: number
  usage_percent: number
  color: 'green' | 'yellow' | 'red'
}

export interface DebtSummary {
  id: number
  name: string
  remaining: number
  total_amount: number
  progress_percent: number
  monthly_payment: number
  interest_rate: number
  type: string
  priority_label: string
  monthly_interest: number
  grace_period_end: string | null
  next_payment_date: string | null
}

export interface FundSummary {
  id: number
  name: string
  target_amount: number
  current_amount: number
  monthly_contribution: number
  target_date: string | null
  progress_percent: number
  is_rolling: boolean
  linked_category_id: number | null
  category_group?: string
}

export interface GoalSummary {
  id: number
  name: string
  current_amount: number
  target_amount: number
  progress_percent: number
  months_to_goal: number | null
  deadline: string | null
  monthly_contribution?: number
  linked_account_name?: string | null
  linked_category_id?: number | null
}

export interface MonthSummary {
  year: number
  month: number
  income_fact: number
  income_plan: number
  total_spent: number
  remaining: number
  savings_rate: number
  savings_target_rate: number
  unallocated: number
  is_fully_allocated: boolean
  income_eur: number
  salary_last_month: number | null
  salary_diff: number | null
  groups: GroupSummary[]
  debts: DebtSummary[]
  goals: GoalSummary[]
  funds: FundSummary[]
  has_plan: boolean
}

export interface Advice {
  priority: number
  message: string
  category: string
  tier: 'urgent' | 'attention' | 'info'
}

export interface AdviceTiers {
  urgent: Advice[]
  attention: Advice[]
  info: Advice[]
}

export interface AllocationItem {
  id: number
  name: string
  kind: 'category' | 'fund'
  suggested_amount: number
  group: string | null
  allocation_level: number
}

export interface AllocationLevel {
  level: number
  label: string
  items: AllocationItem[]
  total_suggested: number
}

export interface AllocationView {
  transaction: { id: number; amount: number; date: string; is_fully_allocated: boolean }
  unallocated: number
  levels: AllocationLevel[]
  existing: { category_id: number | null; fund_id: number | null; amount: number; allocation_level: number }[]
}

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const opts: RequestInit = { method, headers: {} }
  if (body !== undefined) {
    opts.headers = { 'Content-Type': 'application/json' }
    opts.body = JSON.stringify(body)
  }
  const res = await fetch(`/api${path}`, opts)
  if (!res.ok) {
    let detail = res.statusText
    try {
      detail = (await res.json()).detail ?? detail
    } catch {}
    throw new Error(detail)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

const ym = (year?: number, month?: number) =>
  year && month ? `?year=${year}&month=${month}` : ''

export const api = {
  onboardingStatus: () => req<{ onboarded: boolean }>('GET', '/onboarding'),
  onboard: (mode: 'demo' | 'clean') => req('POST', '/onboarding', { mode }),

  users: () => req<User[]>('GET', '/users'),
  createUser: (name: string) => req<User>('POST', '/users', { name }),

  categories: (group?: string) =>
    req<Category[]>('GET', `/categories${group ? `?group=${group}` : ''}`),
  createCategory: (b: Partial<Category>) => req<Category>('POST', '/categories', b),
  updateCategory: (id: number, b: Partial<Category>) => req<Category>('PATCH', `/categories/${id}`, b),
  deleteCategory: (id: number) => req('DELETE', `/categories/${id}`),

  dashboard: (year?: number, month?: number) =>
    req<MonthSummary>('GET', `/dashboard${ym(year, month)}`),
  advice: (year?: number, month?: number) =>
    req<AdviceTiers>('GET', `/advice${ym(year, month)}`),

  transactions: (limit = 20, year?: number, month?: number) => {
    const p = new URLSearchParams({ limit: String(limit) })
    if (year) p.set('year', String(year))
    if (month) p.set('month', String(month))
    return req<Transaction[]>('GET', `/transactions?${p}`)
  },
  createTransaction: (b: Partial<Transaction>) => req<Transaction>('POST', '/transactions', b),
  updateTransaction: (id: number, b: Partial<Transaction>) =>
    req<Transaction>('PATCH', `/transactions/${id}`, b),
  deleteTransaction: (id: number) => req('DELETE', `/transactions/${id}`),

  allocationView: (txId: number) => req<AllocationView>('GET', `/allocation/${txId}`),
  allocate: (txId: number, allocations: unknown[]) =>
    req<{ is_fully_allocated: boolean; unallocated: number }>('POST', `/allocation/${txId}`, {
      allocations,
    }),

  funds: () => req<FundSummary[]>('GET', '/funds'),
  createFund: (b: unknown) => req<FundSummary>('POST', '/funds', b),
  updateFund: (id: number, b: unknown) => req<FundSummary>('PATCH', `/funds/${id}`, b),
  deleteFund: (id: number) => req('DELETE', `/funds/${id}`),
  fundContribute: (id: number, b: unknown) => req('POST', `/funds/${id}/contribute`, b),
  fundSpend: (id: number, b: unknown) => req('POST', `/funds/${id}/spend`, b),

  goals: () => req<GoalSummary[]>('GET', '/goals'),
  createGoal: (b: unknown) => req<GoalSummary>('POST', '/goals', b),
  updateGoal: (id: number, b: unknown) => req<GoalSummary>('PATCH', `/goals/${id}`, b),
  deleteGoal: (id: number) => req('DELETE', `/goals/${id}`),
  goalContribute: (id: number, b: unknown) => req('POST', `/goals/${id}/contribute`, b),

  debts: (includeClosed = false) =>
    req<DebtSummary[]>('GET', `/debts${includeClosed ? '?include_closed=true' : ''}`),
  createDebt: (b: unknown) => req<DebtSummary>('POST', '/debts', b),
  updateDebt: (id: number, b: unknown) => req<DebtSummary>('PATCH', `/debts/${id}`, b),
  deleteDebt: (id: number) => req('DELETE', `/debts/${id}`),
  debtPayment: (id: number, b: unknown) => req('POST', `/debts/${id}/payment`, b),

  plan: (year?: number, month?: number) => req<any>('GET', `/plan${ym(year, month)}`),
  savePlan: (b: unknown, year?: number, month?: number) =>
    req<any>('POST', `/plan${ym(year, month)}`, b),
  saveLimits: (limits: Record<number, number>, year?: number, month?: number) =>
    req<any>('POST', `/plan/limits${ym(year, month)}`, { limits }),
  addPlannedExpense: (b: unknown, year?: number, month?: number) =>
    req<any>('POST', `/plan/planned-expense${ym(year, month)}`, b),
  deletePlannedExpense: (id: number) => req('DELETE', `/plan/planned-expense/${id}`),
  addPlannedDebt: (b: unknown, year?: number, month?: number) =>
    req<any>('POST', `/plan/planned-debt${ym(year, month)}`, b),
  deletePlannedDebt: (id: number) => req('DELETE', `/plan/planned-debt/${id}`),
  closeMonth: (year?: number, month?: number) => req<any>('POST', `/plan/close${ym(year, month)}`),

  deposit: () => req<any>('GET', '/deposit'),
  updateDeposit: (b: unknown) => req<any>('POST', '/deposit', b),
  depositCalc: (monthly: number, targetDate: string) =>
    req<any>('GET', `/deposit/calculator?monthly=${monthly}&target_date=${targetDate}`),

  analytics: (year?: number, month?: number) => req<any>('GET', `/analytics${ym(year, month)}`),

  settings: () => req<Record<string, string>>('GET', '/settings'),
  saveSettings: (b: unknown) => req('POST', '/settings/general', b),
  fetchEurRate: () => req<{ eur_usd_rate: string | null }>('POST', '/settings/fetch-eur-rate'),
}
