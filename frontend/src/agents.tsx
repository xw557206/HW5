/**
 * Visual identity for the five agents.
 *
 * Each agent gets its own colour and mark so the timeline is readable at a
 * glance — you can follow a run by colour without reading every line.
 */

import type { AgentName } from './types'

export interface AgentIdentity {
  name: AgentName
  label: string
  initials: string
  colour: string
  tint: string
  blurb: string
}

export const AGENTS: Record<AgentName, AgentIdentity> = {
  boss: {
    name: 'boss',
    label: 'Boss',
    initials: 'BO',
    colour: '#00356b',
    tint: '#e8eef7',
    blurb: 'Triages tickets, delegates, reviews the outcome',
  },
  inventory: {
    name: 'inventory',
    label: 'Inventory',
    initials: 'IN',
    colour: '#1d7a6c',
    tint: '#e4f2ef',
    blurb: 'Stock, restocking, vendors and purchase orders',
  },
  accounting: {
    name: 'accounting',
    label: 'Accounting',
    initials: 'AC',
    colour: '#8a6a22',
    tint: '#f6efdf',
    blurb: 'Invoices, cash, payments, pricing and discounts',
  },
  facilities: {
    name: 'facilities',
    label: 'Facilities',
    initials: 'FA',
    colour: '#6b4e9e',
    tint: '#efeaf7',
    blurb: 'The lease, rent and the premises',
  },
  customer_service: {
    name: 'customer_service',
    label: 'Customer Service',
    initials: 'CS',
    colour: '#b3503a',
    tint: '#f9eae6',
    blurb: 'Anything a customer reads',
  },
}

export function identity(name: string): AgentIdentity {
  return (
    AGENTS[name as AgentName] ?? {
      name: 'boss',
      label: name,
      initials: name.slice(0, 2).toUpperCase(),
      colour: '#5c6b7a',
      tint: '#eef1f5',
      blurb: '',
    }
  )
}

/** Round avatar with the agent's initials, sized to taste. */
export function AgentAvatar({
  agent,
  size = 34,
  active = false,
  title,
}: {
  agent: string
  size?: number
  active?: boolean
  title?: string
}) {
  const id = identity(agent)
  return (
    <span
      className={`avatar${active ? ' avatar-active' : ''}`}
      style={{
        // @ts-expect-error -- CSS custom property
        '--ac': id.colour,
        width: size,
        height: size,
        fontSize: size * 0.36,
      }}
      title={title ?? `${id.label} — ${id.blurb}`}
      aria-label={id.label}
    >
      {id.initials}
    </span>
  )
}
