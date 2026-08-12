"""Exact-budget menu gacha.

Ported from `betterzeriya`'s `gacha.ts`: count every multiset of menu items whose
prices sum to exactly the target budget, then draw one of them uniformly at
random. The count is computed with an unbounded-knapsack table so the sampler
can reuse the same weights.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence


class PriceItem(Protocol):
    """Anything with a display name and a positive integer price."""

    @property
    def name(self) -> str:
        """Display name, used only in error messages."""

    @property
    def price(self) -> int:
        """Unit price in yen."""


@dataclass
class ExactBudgetSelection[T: PriceItem]:
    """One line of a drawn combination."""

    item: T
    quantity: int
    subtotal: int


@dataclass
class ExactBudgetResult[T: PriceItem]:
    """Number of exact-budget combinations plus one uniformly drawn sample."""

    count: int
    sample: list[ExactBudgetSelection[T]] | None


def _build_solution_table(prices: Sequence[int], target: int) -> list[list[int]]:
    """Return `table[i][r]`: ways to reach `r` yen using `prices[i:]`."""
    table = [[0] * (target + 1) for _ in range(len(prices) + 1)]
    table[len(prices)][0] = 1
    for index in reversed(range(len(prices))):
        price = prices[index]
        row = table[index]
        below = table[index + 1]
        row[0] = 1
        for rest in range(1, target + 1):
            row[rest] = below[rest] + (row[rest - price] if rest >= price else 0)
    return table


def calculate_exact_budget_gacha[T: PriceItem](items: Sequence[T], target: int) -> ExactBudgetResult[T]:
    """Count combinations summing to exactly `target` and sample one uniformly."""
    _assert_input(items, target)

    prices = [item.price for item in items]
    table = _build_solution_table(prices, target)
    count = table[0][target]
    if count == 0:
        return ExactBudgetResult(count=0, sample=None)

    quantities = _sample_quantities(prices, table, target)
    return ExactBudgetResult(count=count, sample=_quantities_to_selections(items, quantities))


def _sample_quantities(prices: Sequence[int], table: list[list[int]], target: int) -> list[int]:
    quantities = [0] * len(prices)
    rest = target
    for index, price in enumerate(prices):
        below = table[index + 1]
        weights = [(quantity, below[rest - price * quantity]) for quantity in range(rest // price + 1)]
        weights = [(quantity, weight) for quantity, weight in weights if weight > 0]
        total_weight = sum(weight for _, weight in weights)
        if total_weight == 0:
            continue
        cursor = secrets.randbelow(total_weight)
        for quantity, weight in weights:
            if cursor < weight:
                quantities[index] = quantity
                rest -= price * quantity
                break
            cursor -= weight
    return quantities


def _quantities_to_selections[T: PriceItem](
    items: Sequence[T],
    quantities: Sequence[int],
) -> list[ExactBudgetSelection[T]]:
    return [
        ExactBudgetSelection(item=items[index], quantity=quantity, subtotal=items[index].price * quantity)
        for index, quantity in enumerate(quantities)
        if quantity > 0
    ]


def _assert_input(items: Sequence[PriceItem], target: int) -> None:
    if not isinstance(target, int) or isinstance(target, bool) or target < 0:
        msg = "target must be a non-negative integer"
        raise ValueError(msg)
    for item in items:
        if not isinstance(item.price, int) or isinstance(item.price, bool) or item.price <= 0:
            msg = f"price must be a positive integer: {item.name}"
            raise ValueError(msg)
