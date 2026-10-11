from __future__ import annotations

import math
import random
import statistics
from collections.abc import Sequence
from dataclasses import dataclass

QUARTILES = 4


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


def _check_pairs(xs: Sequence[float], ys: Sequence[float]) -> None:
    if len(xs) != len(ys):
        raise ValueError(f"Unpaired samples: {len(xs)} against {len(ys)}")
    if len(xs) < 2:
        raise ValueError("Correlation needs at least two pairs")


def pearson(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Pearson correlation, raising where it is undefined rather than returning zero.

    A zero would read as a finding of no relationship, when the sample simply cannot show
    one either way.
    """
    _check_pairs(xs, ys)
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    numerator = sum((a - mx) * (b - my) for a, b in zip(xs, ys, strict=True))
    denominator = math.sqrt(sum((a - mx) ** 2 for a in xs) * sum((b - my) ** 2 for b in ys))
    if denominator == 0:
        raise ValueError("Correlation is undefined when every value in a sample is equal")
    return numerator / denominator


def spearman(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Spearman rank correlation, the Pearson correlation of average ranks.

    Computed directly to avoid a scipy dependency.
    """
    _check_pairs(xs, ys)
    return pearson(average_ranks(xs), average_ranks(ys))


def quartiles(values: Sequence[float]) -> list[int]:
    """Quartile 1 to 4 of each value by rank, the lowest values in quartile 1.

    A value of rank r among n falls in quartile ceil(4r/n), so quartiles hold as near equal
    shares as n allows and tied values share a quartile.
    """
    n = len(values)
    return [math.ceil(QUARTILES * rank / n) for rank in average_ranks(values)]


def transition_matrix(first: Sequence[int], second: Sequence[int]) -> list[list[int]]:
    """Count of filers moving from each quartile in one cycle to each in the next.

    Row i holds the filers in quartile i + 1 of the first cycle, column j those in quartile
    j + 1 of the second.
    """
    if len(first) != len(second):
        raise ValueError(f"Unpaired samples: {len(first)} against {len(second)}")
    matrix = [[0] * QUARTILES for _ in range(QUARTILES)]
    for a, b in zip(first, second, strict=True):
        matrix[a - 1][b - 1] += 1
    return matrix


@dataclass(frozen=True)
class LinearFit:
    slope: float
    intercept: float
    r_squared: float


def ols(xs: Sequence[float], ys: Sequence[float]) -> LinearFit:
    """Least-squares fit of ys on xs."""
    _check_pairs(xs, ys)
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sxx = sum((a - mx) ** 2 for a in xs)
    if sxx == 0:
        raise ValueError("A fit is undefined when every value of the regressor is equal")
    slope = sum((a - mx) * (b - my) for a, b in zip(xs, ys, strict=True)) / sxx
    intercept = my - slope * mx
    return LinearFit(slope=slope, intercept=intercept, r_squared=pearson(xs, ys) ** 2)


def permutation_p_value(
    xs: Sequence[float], ys: Sequence[float], *, permutations: int, seed: int
) -> float:
    """One-sided p-value for a positive Spearman correlation, by permuting the pairing.

    Permuting ys permutes its ranks, so each permutation is scored as the Pearson
    correlation of fixed x ranks against shuffled y ranks without ranking again. The
    observed pairing counts as one of the permutations, so the p-value is never zero.
    """
    observed = spearman(xs, ys)
    rx, ry = average_ranks(xs), average_ranks(ys)
    generator = random.Random(seed)

    at_least = 0
    shuffled = list(ry)
    for _ in range(permutations):
        generator.shuffle(shuffled)
        # A float sum of the same terms in another order can differ in the last place, so a
        # permutation equal to the observed pairing is not missed by rounding.
        if pearson(rx, shuffled) >= observed - 1e-12:
            at_least += 1
    return (at_least + 1) / (permutations + 1)


@dataclass(frozen=True)
class Interval:
    low: float
    high: float
    resamples: int
    undefined: int


def bootstrap_interval(
    xs: Sequence[float],
    ys: Sequence[float],
    *,
    resamples: int,
    seed: int,
    level: float = 0.95,
) -> Interval:
    """Percentile bootstrap interval for the Spearman correlation, resampling pairs.

    A resample whose values are all equal on one side has no correlation. Such resamples
    are counted and left out rather than scored as zero, and the count is returned so a
    reader can see how many there were.
    """
    _check_pairs(xs, ys)
    generator = random.Random(seed)
    n = len(xs)

    estimates: list[float] = []
    undefined = 0
    for _ in range(resamples):
        picks = [generator.randrange(n) for _ in range(n)]
        try:
            estimates.append(spearman([xs[i] for i in picks], [ys[i] for i in picks]))
        except ValueError:
            undefined += 1

    if not estimates:
        raise ValueError("Every resample had an undefined correlation")
    estimates.sort()
    tail = (1 - level) / 2
    return Interval(
        low=_quantile(estimates, tail),
        high=_quantile(estimates, 1 - tail),
        resamples=resamples,
        undefined=undefined,
    )


def _quantile(ordered: Sequence[float], share: float) -> float:
    """Linear interpolation between order statistics, the convention numpy uses by default."""
    position = share * (len(ordered) - 1)
    lower = math.floor(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)
