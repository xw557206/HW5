/** Presentational pieces of the dashboard. */

import { useEffect, useState } from 'react'
import { AgentAvatar, identity } from './agents'
import { clockTime, money } from './api'
import type { AgentEvent, Approval, Ticket } from './types'

/* ---------------------------------------------------------------- crest */

export function Crest({ size = 60 }: { size?: number }) {
  return (
    <svg
      className="crest"
      width={size}
      height={size * 1.18}
      viewBox="0 0 120 142"
      role="img"
      aria-label="Campus Customs crest"
    >
      <path d="M60 4 112 18v52c0 30-22 51-52 68C30 121 8 100 8 70V18z" fill="rgba(255,255,255,.07)" stroke="#b08d3f" strokeWidth="2" />
      <path d="M60 12 104 24v46c0 26-19 44-44 59C36 114 16 96 16 70V24z" fill="none" stroke="rgba(255,255,255,.22)" strokeWidth="1" />
      <g transform="translate(28 26)" fill="#fff">
        <path d="M14 9.5c4.2-2.2 8.4 1 11 7.2-3.6 2.2-6.6 5.4-8.4 9.4-3.8-5.6-5.2-13.4-2.6-16.6z" />
        <path d="M50 9.5c-4.2-2.2-8.4 1-11 7.2 3.6 2.2 6.6 5.4 8.4 9.4 3.8-5.6 5.2-13.4 2.6-16.6z" />
        <path d="M32 11c13.2 0 21.5 6.8 21.5 17.2 0 12.6-9.2 22.3-21.5 22.3S10.5 40.8 10.5 28.2C10.5 17.8 18.8 11 32 11z" />
        <path d="M32 29c7.2 0 11.5 3.9 11.5 9.2S38.6 47.5 32 47.5s-11.5-4-11.5-9.3S24.8 29 32 29z" fill="#00356b" opacity=".3" />
        <ellipse cx="23.6" cy="30.2" rx="2.9" ry="3.1" fill="#00172f" />
        <ellipse cx="40.4" cy="30.2" rx="2.9" ry="3.1" fill="#00172f" />
        <path d="M32 33.2c2.9 0 4.8 1.6 4.8 3.4S34.9 39.6 32 39.6s-4.8-1.2-4.8-3S29.1 33.2 32 33.2z" fill="#00172f" />
        <path d="M32 39.6v3.1M32 42.7c-3 0-5.2-1.5-6.2-3.4M32 42.7c3 0 5.2-1.5 6.2-3.4" stroke="#00172f" strokeWidth="2.1" strokeLinecap="round" fill="none" />
      </g>
      <text x="60" y="112" textAnchor="middle" fontFamily="Georgia,serif" fontSize="12" letterSpacing="3" fill="#b08d3f">NEW HAVEN</text>
    </svg>
  )
}

/* --------------------------------------------------------------- pills */

/** The one place ticket state turns into a label, so it cannot drift. */
export function statusPill(ticket: Ticket, running: boolean, pendingCount: number) {
  if (running) return <span className="pill pill-running">Agents working</span>
  const s = ticket.status.toLowerCase()
  if (s === 'resolved') return <span className="pill pill-resolved">Resolved</span>
  if (s === 'blocked') return <span className="pill pill-blocked">Blocked</span>
  if (s === 'waiting_approval' || pendingCount > 0)
    return <span className="pill pill-waiting">Awaiting approval</span>
  if (s === 'in_progress') return <span className="pill pill-waiting">In progress</span>
  return <span className="pill pill-open">Open</span>
}

/* -------------------------------------------------------- ticket card */

export function TicketCard({
  ticket, selected, running, pendingCount, agents, onSelect,
}: {
  ticket: Ticket
  selected: boolean
  running: boolean
  pendingCount: number
  agents: string[]
  onSelect: () => void
}) {
  return (
    <button
      className={`ticket${selected ? ' selected' : ''}${running ? ' running' : ''}`}
      onClick={onSelect}
      aria-pressed={selected}
    >
      <div className="ticket-top">
        <div style={{ minWidth: 0 }}>
          <div className="ticket-id">TICKET {ticket.id}</div>
          <h3>{ticket.subject}</h3>
          <p className="who">{ticket.requester}</p>
        </div>
        {statusPill(ticket, running, pendingCount)}
      </div>

      {ticket.description && <p className="desc">{ticket.description}</p>}

      <div className="ticket-foot">
        <span className="pill pill-type">{ticket.type.replace(/_/g, ' ')}</span>
        {agents.length > 0 ? (
          <span className="avatar-row" title={`Agents involved: ${agents.join(', ')}`}>
            {agents.map((a) => (
              <AgentAvatar key={a} agent={a} size={22} active={running} />
            ))}
          </span>
        ) : (
          <span className="meta">
            {ticket.sku ?? (ticket.lease_id ? `lease ${ticket.lease_id}` : '')}
            {ticket.size ? ` · size ${ticket.size}` : ''}
            {ticket.qty ? ` · qty ${ticket.qty}` : ''}
          </span>
        )}
      </div>
    </button>
  )
}

/* ------------------------------------------------------------ timeline */

export function Timeline({ events, live }: { events: AgentEvent[]; live: boolean }) {
  if (events.length === 0) {
    return (
      <div className="empty">
        <div className="ico">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round">
            <circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" />
          </svg>
        </div>
        <p>No agent activity yet. Pick a ticket and run the team to see the Boss delegate work.</p>
      </div>
    )
  }

  return (
    <div className="timeline">
      {events.map((e) => {
        const id = identity(e.agent)
        const refused = e.rule_refusals ?? []
        return (
          <div className="tl-item" key={e.entry_id}>
            <span className="tl-dot">
              <AgentAvatar agent={e.agent} size={32} active={live && e.status === 'running'} />
            </span>
            {/* @ts-expect-error -- CSS custom property */}
            <div className="tl-card" style={{ '--ac': id.colour }}>
              <div className="tl-head">
                <span className="tl-name">{id.label}</span>
                <span className="tl-time">
                  {clockTime(e.started_at)}
                  {e.ticket_id ? ` · ticket ${e.ticket_id}` : ''}
                  {e.delegation_depth > 0 ? ' · delegated' : ''}
                </span>
              </div>

              {e.task && <p className="tl-task">{e.task}</p>}
              {e.result_summary && <p className="tl-summary">{e.result_summary}</p>}

              {e.delegated_to.length > 0 && (
                <span className="tl-delegate">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                    <path d="M5 12h14M13 6l6 6-6 6" />
                  </svg>
                  asked {e.delegated_to.map((d) => identity(d).label).join(', ')}
                </span>
              )}

              {e.tools_used.length > 0 && (
                <div className="tl-tools">
                  {e.tools_used.map((t) => (
                    <span className="tool" key={t}>{t}</span>
                  ))}
                </div>
              )}

              {refused.map((r, i) => (
                <div className="tl-refusal" key={i}>
                  <strong>Rule stopped this.</strong> {r.reason ?? 'A business rule refused the action.'}
                </div>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}

/* ----------------------------------------------------------- approvals */

const KIND_LABEL: Record<string, string> = {
  invoice_payment: 'Invoice payment',
  rent_payment: 'Rent payment',
  purchase_order: 'Purchase order',
  price_override: 'Price override',
}

export function ApprovalCard({
  approval, busy, onDecide,
}: {
  approval: Approval
  busy: boolean
  onDecide: (d: 'approved' | 'rejected') => void
}) {
  const pending = approval.status === 'pending'
  return (
    <div className={`approval is-${approval.status}`}>
      <div className="ap-top">
        <div style={{ minWidth: 0 }}>
          <div className="ap-kind">
            {KIND_LABEL[approval.kind] ?? approval.kind.replace(/_/g, ' ')}
            {approval.ticket_id ? ` · ticket ${approval.ticket_id}` : ''}
          </div>
          <div className="ap-amount">
            {approval.kind === 'price_override' ? `${money(approval.amount)} /unit` : money(approval.amount)}
          </div>
        </div>
        <span className={`pill pill-${approval.status === 'pending' ? 'open' : approval.status === 'approved' ? 'resolved' : 'blocked'}`}>
          {approval.status}
        </span>
      </div>

      <p className="ap-reason">{approval.reason}</p>
      <p className="ap-meta">
        Requested by {identity(approval.requested_by).label}
        {approval.ref_id ? ` · ref ${approval.ref_id}` : ''} · #{approval.id}
      </p>

      {pending ? (
        <div className="ap-actions">
          <button className="btn btn-ok btn-sm" disabled={busy} onClick={() => onDecide('approved')}>
            {busy ? 'Working…' : 'Approve'}
          </button>
          <button className="btn btn-no btn-sm" disabled={busy} onClick={() => onDecide('rejected')}>
            Reject
          </button>
        </div>
      ) : (
        <p className="ap-decided">
          {approval.status === 'approved' ? 'Approved' : 'Rejected'}
          {approval.decided_by ? ` by ${approval.decided_by}` : ''}
          {approval.decision_note ? ` — “${approval.decision_note}”` : ''}
        </p>
      )}
    </div>
  )
}

/* -------------------------------------------------------------- toasts */

export interface Toast {
  id: number
  kind: 'ok' | 'err' | 'warn' | 'info'
  title: string
  body?: string
}

export function Toasts({ toasts, dismiss }: { toasts: Toast[]; dismiss: (id: number) => void }) {
  useEffect(() => {
    if (toasts.length === 0) return
    const timers = toasts.map((t) => setTimeout(() => dismiss(t.id), 7000))
    return () => timers.forEach(clearTimeout)
  }, [toasts, dismiss])

  return (
    <div className="toasts" aria-live="polite">
      {toasts.map((t) => (
        <div className={`toast ${t.kind}`} key={t.id} onClick={() => dismiss(t.id)} role="status">
          <b>{t.title}</b>
          {t.body && <span>{t.body}</span>}
        </div>
      ))}
    </div>
  )
}

/* --------------------------------------------------------------- modal */

export function ConfirmModal({
  title, body, confirmLabel, onConfirm, onCancel, busy,
}: {
  title: string
  body: string
  confirmLabel: string
  onConfirm: () => void
  onCancel: () => void
  busy: boolean
}) {
  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && onCancel()
    window.addEventListener('keydown', esc)
    return () => window.removeEventListener('keydown', esc)
  }, [onCancel])

  return (
    <div className="backdrop" onClick={onCancel}>
      <div className="modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
        <div className="modal-hd"><h3>{title}</h3></div>
        <div className="modal-body"><p>{body}</p></div>
        <div className="modal-foot">
          <button className="btn btn-ghost btn-sm" onClick={onCancel} disabled={busy}>Cancel</button>
          <button className="btn btn-danger-ghost btn-sm" onClick={onConfirm} disabled={busy}>
            {busy ? 'Working…' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}

/* ------------------------------------------------------ elapsed timer */

export function Elapsed({ since }: { since: number }) {
  const [, tick] = useState(0)
  useEffect(() => {
    const t = setInterval(() => tick((n) => n + 1), 1000)
    return () => clearInterval(t)
  }, [])
  const s = Math.floor((Date.now() - since) / 1000)
  return <>{s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`}</>
}
