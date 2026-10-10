/**
 * Typed client for the Campus Customs backend.
 *
 * Everything the dashboard shows comes from here — there are no mock
 * responses and no local fabrication of agent activity.
 *
 * Requests go to `/api/...` and Vite proxies them to FastAPI, so there is no
 * CORS issue in development and no hostname baked into the build.
 */

import type {
  ApprovalResult,
  ApprovalsResponse,
  Cash,
  EventsResponse,
  Health,
  ResetResult,
  RunResult,
  TicketsResponse,
} from './types'

const BASE = '/api'

/** Raised when the backend answers but refuses, so the UI can show the reason. */
export class ApiError extends Error {
  status: number
  detail?: string

  constructor(message: string, status: number, detail?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...init,
    })
  } catch {
    // The fetch itself failed — the backend is not running or not reachable.
    throw new ApiError(
      'Cannot reach the backend. Is it running on port 8000?',
      0,
    )
  }

  if (!res.ok) {
    // FastAPI uses `detail`; our own handlers use `error` + `detail`.
    let message = `Request failed (${res.status})`
    let detail: string | undefined
    try {
      const body = await res.json()
      message = body.error || body.detail || message
      detail = typeof body.detail === 'string' ? body.detail : undefined
      if (body.error && detail && detail !== message) {
        // keep both
      } else if (body.detail && !body.error) {
        message = body.detail
        detail = undefined
      }
    } catch {
      /* non-JSON error body; keep the generic message */
    }
    throw new ApiError(message, res.status, detail)
  }

  return res.json() as Promise<T>
}

export const api = {
  health: () => request<Health>('/health'),

  tickets: () => request<TicketsResponse>('/tickets'),

  cash: () => request<Cash>('/cash'),

  approvals: () => request<ApprovalsResponse>('/approvals'),

  events: (limit = 60) => request<EventsResponse>(`/events?limit=${limit}`),

  /** Runs the agent team on one ticket. Slow — it makes real model calls. */
  runTicket: (ticketId: number) =>
    request<RunResult>(`/tickets/${ticketId}/run`, { method: 'POST' }),

  decideApproval: (
    id: number,
    decision: 'approved' | 'rejected',
    decidedBy: string,
    note = '',
  ) =>
    request<ApprovalResult>(`/approvals/${id}`, {
      method: 'POST',
      body: JSON.stringify({ decision, decided_by: decidedBy, note }),
    }),

  reset: () => request<ResetResult>('/reset', { method: 'POST' }),
}

/** $1,234 — whole dollars, which is how every price in this shop is quoted. */
export function money(n: number | null | undefined): string {
  if (n === null || n === undefined) return '—'
  return n.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: n % 1 === 0 ? 0 : 2,
    maximumFractionDigits: 2,
  })
}

/** "2026-08-31T09:15:00-04:00" -> "09:15" */
export function clockTime(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime())
    ? ''
    : d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })
}
