from __future__ import annotations

import math
import statistics
from collections.abc import Sequence


def average_ranks(values: Sequence[float]) -> list[float]:
    """Rank from 1, giving tied values the mean of the positions they occupy."""
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)

    position = 0
    while position < len(order):
        tied_end = position
        while tied_end + 1 < len(order) and values[order[tied_end + 1]] == values[order[position]]:
            tied_end += 1
        rank = (position + tied_end) / 2 + 1
        for index in order[position : tied_end + 1]:
            ranks[index] = rank
        position = tied_end + 1

    return ranks


def spearman(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Spearman rank correlation, computed directly to avoid a scipy dependency.

    Raises where the correlation is undefined rather than returning zero, which would read
    as a finding of no relationship.
    """
    if len(xs) != len(ys):
        raise ValueError(f"Unpaired samples: {len(xs)} against {len(ys)}")
    if len(xs) < 2:
        raise ValueError("Rank correlation needs at least two pairs")

    rx, ry = average_ranks(xs), average_ranks(ys)
    mx, my = statistics.fmean(rx), statistics.fmean(ry)
    numerator = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    denominator = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    if denominator == 0:
        raise ValueError("Rank correlation is undefined when every value in a sample is equal")
    return numerator / denominator
