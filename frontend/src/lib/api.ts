// Typed client for the fin-home JSON API. Same-origin in prod (Caddy),
// proxied to :8000 in dev (see vite.config.ts).

import { authenticated } from './stores'

export interface Category {
  id: number
  name: string
  group: 'needs' | 'wants' | 'savings' | 'income'
  is_hidden: boolean
  sort_order: number
  icon: string
  color: string
}

export interface User {
  id: number
  name: string
  is_active: boolean
  telegram_id: string | null
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
  fund_id: number | null
}

export interface AuthMe {
  authenticated: boolean
  username?: string
  is_admin?: boolean
  workspace?: { id: number; name: string }
}

export interface AdminAccount {
  id: number
  username: string
  is_admin: boolean
  is_active: boolean
  created_at: string | null
}

export interface AdminWorkspace {
  id: number
  name: string
  onboarded: string
  created_at: string | null
  tx_count: number
  accounts: AdminAccount[]
}

export interface AdminOverview {
  workspaces: AdminWorkspace[]
}

export interface AdminInvite {
  id: number
  token: string
  label: string | null
  workspace_id: number | null
  workspace_name: string | null
  expires_at: string | null
  used_at: string | null
  created_at: string | null
}

export interface TransactionListResponse {
  items: Transaction[]
  total: number
  day_totals: Record<string, number>
  month_totals: Record<string, number>
}

export interface TransactionListParams {
  year?: number
  month?: number
  date_from?: string
  date_to?: string
  type?: string
  category_ids?: number[]
  group?: string
  user_id?: number
  sort_by?: 'date' | 'amount'
  sort_dir?: 'asc' | 'desc'
  limit?: number
  offset?: number
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
  group: 'wants' | 'savings'
}

export interface MonthSummary {
  year: number
  month: number
  income_fact: number
  income_plan: number
  total_spent: number
  remaining: number
  carryover: number
  balance: number
  savings_rate: number
  savings_target_rate: number
  salary_last_month: number | null
  salary_diff: number | null
  groups: GroupSummary[]
  debts: DebtSummary[]
  funds: FundSummary[]
  has_plan: boolean
}


export interface Deposit {
  rate: number
  start_date: string | null
  term_months: number
  initial_lump: number
  monthly_contribution: number
  rate_schedule: string
}

export interface Integrations {
  tg_bot_token: boolean
  yandex_api_key: boolean
  yandex_folder_id: boolean
  gigachat_auth_key: boolean
  tg_bot_token_mask: string
  ai_primary_provider: 'yandex' | 'gigachat'
  tg_bot_enabled: boolean
  webhook_set: boolean
}

const REQUEST_TIMEOUT_MS = 15000

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const opts: RequestInit = { method, headers: {}, credentials: 'same-origin' }
  if (body !== undefined) {
    opts.headers = { 'Content-Type': 'application/json' }
    opts.body = JSON.stringify(body)
  }
  const controller = new AbortController()
  opts.signal = controller.signal
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)
  let res: Response
  try {
    res = await fetch(`/api${path}`, opts)
  } catch (e) {
    throw new Error(
      (e as Error).name === 'AbortError' ? 'Сервер не отвечает, проверьте соединение' : 'Нет соединения с сервером',
    )
  } finally {
    clearTimeout(timer)
  }
  if (res.status === 401 && path !== '/auth/login') {
    authenticated.set(false)
    throw new Error('unauthorized')
  }
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
  authMe: () => req<AuthMe>('GET', '/auth/me'),
  login: (username: string, password: string) =>
    req<{ ok: boolean }>('POST', '/auth/login', { username, password }),
  logout: () => req('POST', '/auth/logout'),
  inviteInfo: (token: string) =>
    req<{ valid: boolean; mode: 'join' | 'create'; workspace_name: string | null }>(
      'GET', `/auth/invite/${token}`),
  register: (b: { token: string; username: string; password: string; workspace_name?: string }) =>
    req<{ ok: boolean; workspace: { id: number; name: string } }>('POST', '/auth/register', b),

  adminOverview: () => req<AdminOverview>('GET', '/admin/overview'),
  adminInvites: () => req<AdminInvite[]>('GET', '/admin/invites'),
  adminCreateInvite: (b: { label?: string; workspace_id?: number | null; ttl_days?: number | null }) =>
    req<AdminInvite>('POST', '/admin/invites', b),
  adminRevokeInvite: (id: number) => req('DELETE', `/admin/invites/${id}`),
  adminPatchAccount: (id: number, b: { is_active?: boolean; password?: string }) =>
    req('PATCH', `/admin/accounts/${id}`, b),

  onboardingStatus: () => req<{ onboarded: boolean }>('GET', '/onboarding'),
  onboard: (mode: 'demo' | 'clean') => req('POST', '/onboarding', { mode }),

  users: () => req<User[]>('GET', '/users'),
  createUser: (b: { name: string; telegram_id?: string | null }) => req<User>('POST', '/users', b),
  updateUser: (id: number, b: { name: string; telegram_id?: string | null }) => req<User>('PATCH', `/users/${id}`, b),
  deleteUser: (id: number) => req('DELETE', `/users/${id}`),

  categories: (group?: string, includeHidden = false) => {
    const p = new URLSearchParams()
    if (group) p.set('group', group)
    if (includeHidden) p.set('include_hidden', 'true')
    const qs = p.toString()
    return req<Category[]>('GET', `/categories${qs ? `?${qs}` : ''}`)
  },
  createCategory: (b: Partial<Category>) => req<Category>('POST', '/categories', b),
  updateCategory: (id: number, b: Partial<Category>) => req<Category>('PATCH', `/categories/${id}`, b),
  deleteCategory: (id: number) =>
    req<{ ok: boolean; hidden?: boolean; deleted?: boolean }>('DELETE', `/categories/${id}`),

  dashboard: (year?: number, month?: number) =>
    req<MonthSummary>('GET', `/dashboard${ym(year, month)}`),

  transactions: (limit = 20, year?: number, month?: number) => {
    const p = new URLSearchParams({ limit: String(limit) })
    if (year) p.set('year', String(year))
    if (month) p.set('month', String(month))
    return req<TransactionListResponse>('GET', `/transactions?${p}`).then((r) => r.items)
  },
  transactionsList: (params: TransactionListParams) => {
    const p = new URLSearchParams()
    for (const [k, v] of Object.entries(params)) {
      if (v === undefined || v === null || v === '') continue
      if (Array.isArray(v)) {
        for (const item of v) p.append(k, String(item))
      } else {
        p.set(k, String(v))
      }
    }
    return req<TransactionListResponse>('GET', `/transactions?${p}`)
  },
  createTransaction: (b: Partial<Transaction>) => req<Transaction>('POST', '/transactions', b),
  updateTransaction: (id: number, b: Partial<Transaction>) =>
    req<Transaction>('PATCH', `/transactions/${id}`, b),
  deleteTransaction: (id: number) => req('DELETE', `/transactions/${id}`),

  funds: () => req<FundSummary[]>('GET', '/funds'),
  createFund: (b: unknown) => req<FundSummary>('POST', '/funds', b),
  updateFund: (id: number, b: unknown) => req<FundSummary>('PATCH', `/funds/${id}`, b),
  deleteFund: (id: number) => req('DELETE', `/funds/${id}`),
  fundContribute: (id: number, b: unknown) => req('POST', `/funds/${id}/contribute`, b),
  fundSpend: (id: number, b: unknown) => req('POST', `/funds/${id}/spend`, b),

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

  deposit: () => req<Deposit>('GET', '/deposit'),
  updateDeposit: (b: unknown) => req<Deposit>('POST', '/deposit', b),
  depositCalc: (monthly?: number) =>
    req<any>('GET', `/deposit/calculator${monthly !== undefined ? `?monthly=${monthly}` : ''}`),

  planMeter: (y: number, m: number) =>
    req<Record<string, { allocated: number; target: number }>>('GET', `/plan/${y}/${m}/meter`),

  analytics: (year?: number, month?: number, period: 'month' | 'quarter' | 'year' = 'month') =>
    req<any>('GET', `/analytics${ym(year, month)}${ym(year, month) ? '&' : '?'}period=${period}`),

  settings: () => req<Record<string, string>>('GET', '/settings'),
  saveSettings: (b: unknown) => req('POST', '/settings/general', b),

  integrations: () => req<Integrations>('GET', '/settings/integrations'),
  saveIntegrations: (b: Partial<{
    tg_bot_token: string; yandex_api_key: string; yandex_folder_id: string;
    gigachat_auth_key: string; ai_primary_provider: string; tg_bot_enabled: boolean
  }>) => req('POST', '/settings/integrations', b),
  testIntegrations: () => req<{ telegram: boolean; yandex: boolean; gigachat: boolean }>('POST', '/settings/integrations/test'),
  setWebhook: () => req<{ ok: boolean; url: string; error?: string }>('POST', '/settings/integrations/set-webhook'),
}
