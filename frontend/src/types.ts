/**
 * Shapes returned by the FastAPI backend.
 *
 * These mirror the Pydantic models in `backend/models.py`. Kept in one file
 * so a backend change has one place to land on this side.
 */

export type AgentName =
  | 'boss'
  | 'inventory'
  | 'accounting'
  | 'facilities'
  | 'customer_service'

export type RunStatus =
  | 'resolved'
  | 'needs_approval'
  | 'blocked'
  | 'in_progress'
  | 'failed'

export type ApprovalState = 'pending' | 'approved' | 'rejected'

export interface Ticket {
  id: number
  type: string
  requester: string
  subject: string
  description: string
  status: string
  is_open: boolean
  sku: string | null
  size: string | null
  qty: number | null
  lease_id: number | null
  invoice_id: number | null
  created_at: string
}

export interface TicketsResponse {
  ok: boolean
  shop_date: string
  count: number
  tickets: Ticket[]
}

export interface Approval {
  id: number
  kind: string
  ticket_id: number | null
  ref_id: number | null
  amount: number
  requested_by: string
  reason: string
  status: ApprovalState
  created_at: string
  decided_at: string | null
  decided_by: string | null
  decision_note: string | null
}

export interface ApprovalsResponse {
  ok: boolean
  count: number
  pending_count: number
  approvals: Approval[]
}

export interface ApprovalResult {
  ok: boolean
  status: 'executed' | 'rejected' | 'blocked'
  approval_id: number
  decision: string
  executed: boolean
  payment_id: number | null
  purchase_order_id: number | null
  amount: number | null
  new_balance: number | null
  message: string
}

export interface RunResult {
  ok: boolean
  status: RunStatus
  run_id: string
  ticket_id: number
  assigned_to: AgentName | null
  routing_reason: string | null
  resolution: string
  ticket_status: string
  blocked_by: string | null
  needs_human_approval: boolean
  pending_approvals: Approval[]
  draft_ids: number[]
  agents_involved: AgentName[]
  tools_called: string[]
  model_calls: number
  tool_calls: number
  message: string
}

/** One agent run, as the timeline shows it. */
export interface AgentEvent {
  entry_id: string
  run_id: string
  agent: string
  ticket_id: number | null
  task: string
  started_at: string
  finished_at: string
  status: string
  stop_reason: string | null
  iterations: number
  tools_used: string[]
  actions: string[]
  rule_refusals: { tool?: string; reason?: string }[]
  delegated_to: string[]
  delegation_depth: number
  result_summary: string | null
}

export interface EventsResponse {
  ok: boolean
  count: number
  total_recorded: number
  events: AgentEvent[]
}

export interface Cash {
  ok: boolean
  account: string
  balance: number
  committed_by_open_requests: number
  available_to_commit: number
  as_of: string
  shop_date: string
}

export interface ResetResult {
  ok: boolean
  reset: boolean
  restored_from: string
  row_counts: Record<string, number>
  checking_balance: number
  audit_entries_archived: number
  message: string
}

export interface Health {
  ok: boolean
  mcp_connected: boolean
  mcp_tools?: number
  shop_date?: string
  agents_configured?: boolean
  detail?: string
}
