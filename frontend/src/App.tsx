/**
 * Campus Customs operations dashboard.
 *
 * Everything shown here comes from the FastAPI backend. There are no mock
 * agents and no fabricated activity: the timeline is the real audit trail,
 * the approvals are real rows, and the buttons call real endpoints.
 *
 * "Real time" is done by polling `/events` while a run is in flight. The run
 * endpoint is a single blocking POST, so without polling the dashboard would
 * sit still for a minute and then jump to the end — which hides exactly the
 * part worth watching.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ApiError, api, money } from './api'
import { AGENTS, AgentAvatar, identity } from './agents'
import {
  ApprovalCard, ConfirmModal, Crest, Elapsed, TicketCard, Timeline, Toasts,
  type Toast,
} from './components'
import type { AgentEvent, Approval, Cash, Health, RunResult, Ticket } from './types'

const WHO = 'shop owner' // recorded against every approval decision

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [approvals, setApprovals] = useState<Approval[]>([])
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [cash, setCash] = useState<Cash | null>(null)
  const [health, setHealth] = useState<Health | null>(null)

  const [selected, setSelected] = useState<number | null>(null)
  const [running, setRunning] = useState<number | null>(null)
  const [runStartedAt, setRunStartedAt] = useState(0)
  const [lastRun, setLastRun] = useState<RunResult | null>(null)

  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [deciding, setDeciding] = useState<number | null>(null)
  const [confirmReset, setConfirmReset] = useState(false)
  const [resetting, setResetting] = useState(false)
  const [cashFlash, setCashFlash] = useState(false)

  const [toasts, setToasts] = useState<Toast[]>([])
  const toastId = useRef(0)

  const toast = useCallback((kind: Toast['kind'], title: string, body?: string) => {
    setToasts((t) => [...t, { id: ++toastId.current, kind, title, body }])
  }, [])
  const dismiss = useCallback((id: number) => {
    setToasts((t) => t.filter((x) => x.id !== id))
  }, [])

  /* ------------------------------------------------------------ loading */

  const refresh = useCallback(async (quiet = false) => {
    try {
      const [t, a, c, e] = await Promise.all([
        api.tickets(), api.approvals(), api.cash(), api.events(60),
      ])
      setTickets(t.tickets)
      setApprovals(a.approvals)
      setCash(c)
      setEvents(e.events)
      setLoadError(null)
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : String(err)
      setLoadError(msg)
      if (!quiet) toast('err', 'Could not load the desk', msg)
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth({ ok: false, mcp_connected: false }))
    refresh()
  }, [refresh])

  /* ------------------------------------- live polling while a run is on */

  useEffect(() => {
    if (running === null) return
    const poll = setInterval(async () => {
      try {
        const e = await api.events(60)
        setEvents(e.events)
      } catch {
        /* a dropped poll is not worth interrupting the run for */
      }
    }, 2000)
    return () => clearInterval(poll)
  }, [running])

  /* -------------------------------------------------------------- derived */

  const pendingByTicket = useMemo(() => {
    const m = new Map<number, number>()
    for (const a of approvals) {
      if (a.status !== 'pending' || a.ticket_id === null) continue
      m.set(a.ticket_id, (m.get(a.ticket_id) ?? 0) + 1)
    }
    return m
  }, [approvals])

  const agentsByTicket = useMemo(() => {
    const m = new Map<number, string[]>()
    // Oldest first, so the order reflects who was called when.
    for (const e of [...events].reverse()) {
      if (e.ticket_id === null || e.run_id === 'offline-check') continue
      const list = m.get(e.ticket_id) ?? []
      if (!list.includes(e.agent)) list.push(e.agent)
      m.set(e.ticket_id, list)
    }
    return m
  }, [events])

  const visibleEvents = useMemo(() => {
    // The audit trail is append-only and still holds the Problem 5 wiring
    // checks, which ran a TestModel against ticket ids to prove the plumbing.
    // They are real records and stay in the file, but they are not shop work,
    // so the operations view leaves them out.
    const real = events.filter((e) => e.run_id !== 'offline-check')
    return selected === null ? real : real.filter((e) => e.ticket_id === selected)
  }, [events, selected])

  const pendingApprovals = approvals.filter((a) => a.status === 'pending')
  const decidedApprovals = approvals.filter((a) => a.status !== 'pending')
  const selectedTicket = tickets.find((t) => t.id === selected) ?? null

  /* ------------------------------------------------------------- actions */

  async function runTicket(id: number) {
    setRunning(id)
    setRunStartedAt(Date.now())
    setLastRun(null)
    toast('info', `Running ticket ${id}`, 'The Boss is reading the ticket and choosing an agent.')
    try {
      const result = await api.runTicket(id)
      setLastRun(result)
      if (result.status === 'needs_approval') {
        toast('warn', `Ticket ${id} needs approval`,
          `${result.pending_approvals.length} request(s) are waiting for your decision.`)
      } else if (result.status === 'resolved') {
        toast('ok', `Ticket ${id} resolved`, result.resolution.slice(0, 140))
      } else if (result.status === 'failed') {
        toast('err', `Ticket ${id} did not complete`, result.message)
      } else {
        toast('info', `Ticket ${id}: ${result.status.replace(/_/g, ' ')}`, result.resolution.slice(0, 140))
      }
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : String(err)
      toast('err', `Could not run ticket ${id}`, msg)
    } finally {
      setRunning(null)
      await refresh(true)
    }
  }

  async function decide(id: number, decision: 'approved' | 'rejected') {
    setDeciding(id)
    try {
      const r = await api.decideApproval(id, decision, WHO)
      if (r.status === 'executed') {
        toast('ok', 'Approved and executed', r.message)
        setCashFlash(true)
        setTimeout(() => setCashFlash(false), 1400)
      } else if (r.status === 'rejected') {
        toast('info', 'Rejected', r.message)
      } else {
        // Approved by a person, then refused by a business rule.
        toast('warn', 'Blocked by a business rule', r.message)
      }
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : String(err)
      toast('err', 'Decision failed', msg)
    } finally {
      setDeciding(null)
      await refresh(true)
    }
  }

  async function doReset() {
    setResetting(true)
    try {
      const r = await api.reset()
      toast('ok', 'Desk reset', r.message)
      setLastRun(null)
      setSelected(null)
      await refresh(true)
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : String(err)
      toast('err', 'Reset failed', msg)
    } finally {
      setResetting(false)
      setConfirmReset(false)
    }
  }

  /* ---------------------------------------------------------------- view */

  const backendDown = loadError !== null && tickets.length === 0

  return (
    <>
      <header className="masthead">
        <div className="mast-inner">
          <Crest size={58} />
          <div className="mast-text">
            <p className="kicker">Campus Customs · Operations Desk</p>
            <h1>Agent Dashboard</h1>
            <p className="mast-sub">
              Five agents working the shop's open tickets
              {health?.shop_date ? ` · shop date ${health.shop_date}` : ''}
              {health?.mcp_tools ? ` · ${health.mcp_tools} MCP tools` : ''}
            </p>
          </div>
          <div className="mast-right">
            <dl className={`cash-plate${cashFlash ? ' flash' : ''}`}>
              <dt>Checking</dt>
              <dd>{cash ? money(cash.balance) : '—'}</dd>
              {cash && cash.committed_by_open_requests > 0 && (
                <small>{money(cash.available_to_commit)} free · {money(cash.committed_by_open_requests)} committed</small>
              )}
            </dl>
            <button
              className="btn btn-ghost btn-sm"
              style={{ color: '#fff', borderColor: 'rgba(255,255,255,.4)' }}
              onClick={() => setConfirmReset(true)}
              disabled={running !== null}
            >
              Reset desk
            </button>
          </div>
        </div>
        <svg className="watermark" width="330" height="330" viewBox="0 0 64 64" aria-hidden="true" fill="currentColor">
          <path d="M14 9.5c4.2-2.2 8.4 1 11 7.2-3.6 2.2-6.6 5.4-8.4 9.4-3.8-5.6-5.2-13.4-2.6-16.6z" />
          <path d="M50 9.5c-4.2-2.2-8.4 1-11 7.2 3.6 2.2 6.6 5.4 8.4 9.4 3.8-5.6 5.2-13.4 2.6-16.6z" />
          <path d="M32 11c13.2 0 21.5 6.8 21.5 17.2 0 12.6-9.2 22.3-21.5 22.3S10.5 40.8 10.5 28.2C10.5 17.8 18.8 11 32 11z" />
        </svg>
      </header>

      <main>
        {backendDown && (
          <div className="notice notice-error" style={{ marginBottom: 22 }}>
            <strong>The backend is not reachable.</strong> {loadError}
            <br />
            Start it with <code>uvicorn backend.main:app --reload --port 8000</code> from the
            project root, then{' '}
            <button className="btn btn-ghost btn-sm" style={{ marginTop: 9 }} onClick={() => refresh()}>
              Try again
            </button>
          </div>
        )}

        {health && !health.agents_configured && !backendDown && (
          <div className="notice notice-warn" style={{ marginBottom: 22 }}>
            The agent team is not configured, so running a ticket will return a clear error.
            Everything else on this page works.
          </div>
        )}

        <div className="grid">
          {/* ------------------------------------------------ left column */}
          <div className="col">
            <section className="card">
              <div className="card-hd">
                <div>
                  <h2>Open tickets</h2>
                  <p className="sub">Select one, then run the team</p>
                </div>
                <button className="btn btn-ghost btn-sm" onClick={() => refresh()} disabled={running !== null}>
                  Refresh
                </button>
              </div>
              <div className="card-body">
                {loading ? (
                  <>
                    <div className="skel w70" /><div className="skel" /><div className="skel w45" />
                  </>
                ) : tickets.length === 0 ? (
                  <div className="empty">
                    <p>No tickets returned by the backend.</p>
                  </div>
                ) : (
                  <div className="tickets">
                    {tickets.map((t) => (
                      <TicketCard
                        key={t.id}
                        ticket={t}
                        selected={selected === t.id}
                        running={running === t.id}
                        pendingCount={pendingByTicket.get(t.id) ?? 0}
                        agents={agentsByTicket.get(t.id) ?? []}
                        onSelect={() => setSelected(selected === t.id ? null : t.id)}
                      />
                    ))}
                  </div>
                )}

                {selectedTicket && (
                  <div className="runbar" style={{ marginTop: 16 }}>
                    <span className="label">
                      {running === selectedTicket.id ? (
                        <span className="working">
                          <span className="dots"><i /><i /><i /></span>
                          Agents working on <b>ticket {selectedTicket.id}</b> · <Elapsed since={runStartedAt} />
                        </span>
                      ) : (
                        <>Ready to run <b>ticket {selectedTicket.id}</b> — {selectedTicket.subject}</>
                      )}
                    </span>
                    <button
                      className="btn btn-primary btn-sm"
                      disabled={running !== null}
                      onClick={() => runTicket(selectedTicket.id)}
                    >
                      {running === selectedTicket.id ? 'Running…' : 'Run agent team'}
                    </button>
                  </div>
                )}
              </div>
            </section>

            {/* outcome of the last run */}
            {lastRun && (
              <section className="card">
                <div className="card-hd">
                  <div>
                    <h2>Ticket {lastRun.ticket_id} outcome</h2>
                    <p className="sub">
                      {lastRun.model_calls} model calls · {lastRun.tool_calls} tool calls
                    </p>
                  </div>
                  <span className={`pill pill-${
                    lastRun.status === 'resolved' ? 'resolved'
                    : lastRun.status === 'needs_approval' ? 'waiting'
                    : lastRun.status === 'blocked' || lastRun.status === 'failed' ? 'blocked'
                    : 'open'}`}>
                    {lastRun.status.replace(/_/g, ' ')}
                  </span>
                </div>
                <div className="card-body">
                  {lastRun.assigned_to && (
                    <p style={{ fontSize: 13, color: 'var(--dim)', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 8 }}>
                      <AgentAvatar agent={lastRun.assigned_to} size={24} />
                      {lastRun.routing_reason}
                    </p>
                  )}
                  <p style={{ fontSize: 14.5, lineHeight: 1.65, color: '#49566a' }}>{lastRun.resolution}</p>

                  {lastRun.blocked_by && (
                    <div className="notice notice-warn" style={{ marginTop: 13 }}>
                      <strong>Blocked:</strong> {lastRun.blocked_by}
                    </div>
                  )}

                  {lastRun.agents_involved.length > 0 && (
                    <div style={{ marginTop: 15 }}>
                      <p className="eyebrow" style={{ marginBottom: 9 }}>Who contributed</p>
                      {lastRun.agents_involved.map((a) => {
                        const ev = events.find((e) => e.agent === a && e.run_id === lastRun.run_id)
                        return (
                          <div key={a} style={{ display: 'flex', gap: 10, marginBottom: 9 }}>
                            <AgentAvatar agent={a} size={26} />
                            <div style={{ minWidth: 0 }}>
                              <div style={{ fontWeight: 600, fontSize: 13.5, color: 'var(--yale-ink)' }}>
                                {identity(a).label}
                              </div>
                              <div style={{ fontSize: 12.5, color: 'var(--dim)', lineHeight: 1.5 }}>
                                {ev?.result_summary ?? identity(a).blurb}
                              </div>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  )}

                  {lastRun.tools_called.length > 0 && (
                    <div className="tl-tools" style={{ marginTop: 12 }}>
                      {lastRun.tools_called.map((t) => <span className="tool" key={t}>{t}</span>)}
                    </div>
                  )}
                </div>
              </section>
            )}

            {/* the five agents, as a legend */}
            <section className="card">
              <div className="card-hd"><div><h2>The team</h2><p className="sub">Who does what</p></div></div>
              <div className="card-body">
                {Object.values(AGENTS).map((a) => (
                  <div key={a.name} style={{ display: 'flex', gap: 11, alignItems: 'center', padding: '7px 0' }}>
                    <AgentAvatar agent={a.name} size={30} />
                    <div>
                      <div style={{ fontFamily: 'var(--serif)', fontSize: 14.5, fontWeight: 600 }}>{a.label}</div>
                      <div style={{ fontSize: 12.5, color: 'var(--dim)' }}>{a.blurb}</div>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          </div>

          {/* ----------------------------------------------- right column */}
          <div className="col">
            <section className="card">
              <div className="card-hd">
                <div>
                  <h2>Approvals</h2>
                  <p className="sub">
                    {pendingApprovals.length > 0
                      ? `${pendingApprovals.length} waiting on you`
                      : 'Nothing waiting'}
                  </p>
                </div>
                {pendingApprovals.length > 0 && (
                  <span className="pill pill-open">{pendingApprovals.length} pending</span>
                )}
              </div>
              <div className="card-body">
                {loading ? (
                  <><div className="skel w85" /><div className="skel w45" /></>
                ) : approvals.length === 0 ? (
                  <div className="empty">
                    <div className="ico">
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M20 6 9 17l-5-5" />
                      </svg>
                    </div>
                    <p>No approval requests yet. Agents raise them when a ticket needs money to move or a price to change — they can never approve their own.</p>
                  </div>
                ) : (
                  <>
                    {pendingApprovals.map((a) => (
                      <ApprovalCard key={a.id} approval={a} busy={deciding === a.id} onDecide={(d) => decide(a.id, d)} />
                    ))}
                    {decidedApprovals.length > 0 && (
                      <>
                        <p className="eyebrow" style={{ margin: '20px 0 10px' }}>Decided</p>
                        {decidedApprovals.map((a) => (
                          <ApprovalCard key={a.id} approval={a} busy={false} onDecide={() => {}} />
                        ))}
                      </>
                    )}
                  </>
                )}
              </div>
            </section>

            <section className="card">
              <div className="card-hd">
                <div>
                  <h2>Agent activity</h2>
                  <p className="sub">
                    {selected ? `Ticket ${selected}` : 'All tickets'}
                    {running !== null ? ' · live' : ''}
                  </p>
                </div>
                {running !== null && (
                  <span className="working">
                    <span className="dots"><i /><i /><i /></span> live
                  </span>
                )}
              </div>
              <div className="card-body">
                {loading ? (
                  <><div className="skel w70" /><div className="skel" /></>
                ) : (
                  <Timeline events={visibleEvents} live={running !== null} />
                )}
              </div>
            </section>
          </div>
        </div>
      </main>

      {confirmReset && (
        <ConfirmModal
          title="Reset the desk?"
          body="This restores the working database from the untouched original: approvals, drafts, purchase orders and payments are cleared, and the cash balance goes back to $3,400. The audit trail is kept, and the original database is never modified."
          confirmLabel="Reset"
          busy={resetting}
          onConfirm={doReset}
          onCancel={() => setConfirmReset(false)}
        />
      )}

      <Toasts toasts={toasts} dismiss={dismiss} />
    </>
  )
}
