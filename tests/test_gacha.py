from __future__ import annotations

from dataclasses import dataclass

import pytest

from saizeriya.gacha import calculate_exact_budget_gacha


@dataclass
class Item:
    name: str
    price: int


def test_counts_exact_combinations_and_samples_one_of_them() -> None:
    result = calculate_exact_budget_gacha(
        [Item("A", 700), Item("B", 300), Item("C", 200)],
        1000,
    )

    assert result.count == 3
    assert result.sample is not None
    assert sum(selection.subtotal for selection in result.sample) == 1000


def test_returns_no_sample_when_no_exact_combination_exists() -> None:
    result = calculate_exact_budget_gacha([Item("A", 600)], 1000)

    assert result.count == 0
    assert result.sample is None


def test_zero_budget_has_exactly_one_empty_combination() -> None:
    result = calculate_exact_budget_gacha([Item("A", 600)], 0)

    assert result.count == 1
    assert result.sample == []


def test_samples_cover_every_combination() -> None:
    items = [Item("A", 700), Item("B", 300), Item("C", 200)]
    seen = set()
    for _ in range(200):
        sample = calculate_exact_budget_gacha(items, 1000).sample
        assert sample is not None
        assert sum(selection.subtotal for selection in sample) == 1000
        seen.add(tuple(sorted((s.item.name, s.quantity) for s in sample)))

    assert len(seen) == 3


def test_rejects_negative_budget() -> None:
    with pytest.raises(ValueError, match="non-negative integer"):
        calculate_exact_budget_gacha([Item("A", 100)], -1)


def test_rejects_non_positive_price() -> None:
    with pytest.raises(ValueError, match="positive integer: Free"):
        calculate_exact_budget_gacha([Item("Free", 0)], 100)
