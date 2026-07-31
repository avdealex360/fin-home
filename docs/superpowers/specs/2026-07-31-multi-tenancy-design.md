# Multi-tenancy: accounts, workspaces, invites, admin

Date: 2026-07-31. Status: approved (subproject 2 of 4).

## Goal

Friends can use the service without seeing each other's budgets. Registration is
invite-only. The owner gets a minimal admin panel to manage accounts and invites.

## Decisions

- **Account** (new) is the auth principal: `username` (unique), `password_hash`
  (bcrypt), `is_admin`, `workspace_id`, `is_active`. A workspace may have several
  accounts (e.g. partner gets their own login later).
- **AppUser stays** what it is — a per-workspace family-member label for attributing
  transactions; not a login. `telegram_id` stays globally unique: one Telegram account
  maps to one member row, and the bot derives the workspace from it.
- **Workspace**: `name`, `onboarded` ('' | 'demo' | 'clean' — moved out of Setting),
  `created_at`. All root entities get `workspace_id` (NOT NULL): `app_users`,
  `categories`, `sinking_funds`, `transactions`, `monthly_plans`, `debts`. Children
  (contributions, limits, planned items, debt payments) inherit via FK — not denormalized.
- **Setting** becomes `id` PK + `workspace_id` (nullable) + `key` + unique
  `(workspace_id, key)`. `workspace_id = NULL` is the global scope: `secret.*` keys
  (Telegram bot token, webhook secret, AI keys) stay global — one bot and one AI
  account, owned by the admin. Everything else (currency, deposit_*) is per-workspace.
- **Session cookie** carries identity: `{account_id}.{ts}.{hmac}`. The auth middleware
  validates it, loads the account, and puts `(account_id, workspace_id, is_admin)`
  into `request.state`; a `deps.py` dependency exposes it to endpoints. Invalid or
  deactivated account → 401.
- **MonthlyPlan** unique constraint becomes `(workspace_id, year, month)`.

## Invites & registration

- **Invite**: `token` (urlsafe secret, unique), `label`, `workspace_id` (nullable —
  NULL means "registration creates a fresh workspace", set means "join this
  workspace"), `expires_at` (nullable), `used_at`, `used_by_account_id`, `created_at`.
- Public endpoints: `GET /api/auth/invite/{token}` (validity + join-vs-create mode),
  `POST /api/auth/register` `{token, username, password, workspace_name?}` — creates
  the account (+ workspace when the invite isn't bound to one), marks the invite used,
  sets the session cookie. Single-use.
- `POST /api/auth/login` now checks the `accounts` table (bcrypt), not env vars.
- `GET /api/auth/me` → `{authenticated, username, is_admin, workspace: {id, name}}`.

## Admin (`/api/admin/*`, guarded by `is_admin`; UI at `#/admin`)

- Overview: workspaces with account names, member count, transaction count.
- Invites: list / create (label, optional workspace binding, TTL days) / revoke.
- Accounts: deactivate/reactivate, reset password.
- The `#/admin` link shows up in «Ещё» only for admins.

## Migration & bootstrap

Alembic revision on top of `d4f5g6h7i8j9`:
1. Create `workspaces`, `accounts`, `invites`.
2. Insert default workspace id=1 «Семья», copying `onboarded` from old Setting.
3. Add `workspace_id` to the 6 root tables, backfill with 1, make NOT NULL
   (SQLite batch mode). Plan unique constraint rebuilt as (workspace_id, year, month).
4. Rebuild `settings` with the new shape: existing non-secret rows → workspace 1,
   `secret.*` rows → global (NULL). Drop old `onboarded` row.

Startup `ensure_admin_account`: if the accounts table is empty, create an admin
account from `APP_USER`/`APP_PASSWORD_HASH` env in workspace 1 — so the existing
login keeps working after deploy with zero manual steps.

## Scoping sweep

Every endpoint/service filters by the request workspace: transactions, meta
(users/categories/onboarding/dashboard), funds, debts, plan, deposit, analytics
(incl. pair), settings (incl. JSON/CSV export), telegram digest. Telegram bot:
`_sender` (AppUser by telegram_id) defines the workspace for parsing context,
created transactions, `/undo` and the `setcat` callback (ownership checks added).

## Out of scope

Public self-registration, password recovery, email, multi-workspace membership per
account, per-workspace Telegram bots, landing redesign (subproject 3).

## Verification

pytest (new tests: invite registration, cross-workspace isolation 404s, admin guard),
migration dry-run on a copy of the prod-shaped local DB, manual login flow.
