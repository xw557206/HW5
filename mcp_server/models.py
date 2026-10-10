"""Structured return types for the MCP tools.

Typed returns mean the MCP client receives structured output rather than a
wall of prose, so an agent can branch on `can_fulfill_now` instead of parsing
a sentence.

Every field is either copied from the database or computed from database
values by plain arithmetic. Nothing here is estimated or assumed — where a
number is derived, the field name says so (`shortfall`, `days_until_due`).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SizeStock(BaseModel):
    """One size of a product, with what is on the shelf."""

    size: str
    qty: int
    location: str
    in_stock: bool = Field(description="True when qty > 0.")


class VendorOption(BaseModel):
    """A vendor considered as a source for a restock."""

    vendor_id: int
    name: str
    specialty: str
    lead_days: int = Field(description="Days from order to delivery.")
    outstanding_invoice_count: int
    outstanding_invoice_total: float
    can_order: bool = Field(
        description="False when the vendor has any unpaid invoice. "
        "Ordering from a blocked vendor is not allowed."
    )
    blocked_reason: str | None = None


class OrderFulfillment(BaseModel):
    """Whether a customer order can be filled today, and what blocks it."""

    sku: str
    product_name: str | None
    requested_size: str
    requested_qty: int

    qty_on_hand: int = Field(description="Units of the requested size.")
    can_fulfill_now: bool
    shortfall: int = Field(description="Units short; 0 when fully covered.")

    other_sizes: list[SizeStock] = Field(
        default_factory=list,
        description="Every size carried for this sku, so an alternative can be offered.",
    )
    unit_cost: float | None = None
    list_price: float | None = None

    restock_options: list[VendorOption] = Field(
        default_factory=list,
        description="Vendors whose specialty could supply this product.",
    )
    any_vendor_available: bool = Field(
        description="True when at least one matching vendor has no unpaid invoice."
    )

    shop_date: str = Field(description="From desk.date_today, not the system clock.")
    summary: str


class RentStatus(BaseModel):
    """What is owed on a lease, when, and whether the shop can cover it."""

    lease_id: int
    space_name: str
    landlord: str
    monthly_rent: float

    next_due: str
    days_until_due: int = Field(description="Negative means already overdue.")
    is_overdue: bool
    is_due_soon: bool = Field(description="Due within the next 7 days.")

    cash_account: str
    cash_balance: float
    affordable: bool = Field(description="True when the balance covers the rent.")
    balance_after_payment: float

    already_paid: bool = Field(description="True when payments holds a row for this lease.")
    payment_count: int

    requires_human_approval: bool = Field(
        default=True,
        description="Always true. No payment may be made without dashboard approval.",
    )

    shop_date: str
    summary: str


class BulkQuote(BaseModel):
    """Pricing and availability for a bulk order with a discount request."""

    sku: str
    product_name: str | None
    size: str
    requested_qty: int

    qty_on_hand: int
    shortfall: int
    can_fill_from_stock: bool

    unit_cost: float
    list_price: float
    list_total: float = Field(description="requested_qty x list_price.")
    cost_total: float = Field(description="requested_qty x unit_cost — the break-even point.")
    margin_at_list: float = Field(description="list_total - cost_total.")

    min_unit_price: float = Field(
        description="unit_cost — selling below this loses money on every unit."
    )
    max_discount_pct_at_cost: float = Field(
        description="Largest discount off list that still breaks even."
    )

    proposed_unit_price: float | None = None
    proposed_total: float | None = None
    proposed_margin: float | None = None
    proposed_discount_pct: float | None = None
    proposed_is_profitable: bool | None = None

    requires_human_approval: bool = Field(
        default=True, description="A price override is never applied by an agent alone."
    )

    shop_date: str
    summary: str
