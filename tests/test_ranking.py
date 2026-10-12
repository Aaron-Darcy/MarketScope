from __future__ import annotations

import statistics

import pytest

from marketscope.ranking import (
    average_ranks,
    bootstrap_interval,
    ols,
    pearson,
    permutation_p_value,
    quartiles,
    spearman,
    transition_matrix,
)


def test_ranks_start_at_one() -> None:
    assert average_ranks([0.3, 0.1, 0.2]) == [3.0, 1.0, 2.0]


def test_tied_values_share_the_mean_of_their_positions() -> None:
    assert average_ranks([0.5, 0.1, 0.5, 0.9]) == [2.5, 1.0, 2.5, 4.0]


def test_a_monotone_relationship_correlates_perfectly() -> None:
    """Rank correlation is indifferent to scale, which is why it survives the level shift
    between a slow cycle and a fast one."""
    assert spearman([0.2, 0.3, 0.4, 0.5], [0.3, 0.5, 0.9, 1.4]) == pytest.approx(1.0)


def test_a_reversed_ordering_correlates_negatively() -> None:
    assert spearman([0.1, 0.2, 0.3], [0.9, 0.5, 0.4]) == pytest.approx(-1.0)


def test_ties_are_not_broken_by_input_order() -> None:
    forward = spearman([1.0, 2.0, 2.0, 3.0], [1.0, 2.0, 3.0, 4.0])
    swapped = spearman([1.0, 2.0, 2.0, 3.0], [1.0, 3.0, 2.0, 4.0])

    assert forward == pytest.approx(swapped)


def test_unpaired_samples_are_refused() -> None:
    with pytest.raises(ValueError, match="Unpaired"):
        spearman([0.1, 0.2, 0.3], [0.1, 0.2])


def test_a_single_pair_is_refused() -> None:
    with pytest.raises(ValueError, match="at least two"):
        spearman([0.1], [0.2])


def test_a_constant_sample_is_refused_rather_than_read_as_no_relationship() -> None:
    with pytest.raises(ValueError, match="undefined"):
        spearman([0.4, 0.4, 0.4], [0.1, 0.2, 0.3])


def test_pearson_agrees_with_the_standard_library() -> None:
    xs, ys = [1.0, 2.0, 3.0, 4.5], [2.0, 4.0, 6.5, 7.0]

    assert pearson(xs, ys) == pytest.approx(statistics.correlation(xs, ys))


def test_spearman_is_pearson_on_average_ranks() -> None:
    xs, ys = [0.4, 0.1, 0.4, 0.7, 0.2], [0.9, 0.3, 0.5, 0.8, 0.1]

    assert spearman(xs, ys) == pytest.approx(pearson(average_ranks(xs), average_ranks(ys)))


def test_quartiles_split_by_rank_into_near_equal_shares() -> None:
    assert quartiles([8.0, 1.0, 7.0, 2.0, 6.0, 3.0, 5.0, 4.0]) == [4, 1, 4, 1, 3, 2, 3, 2]


def test_tied_values_share_a_quartile() -> None:
    first, second = quartiles([1.0, 2.0, 2.0, 3.0])[1:3]

    assert first == second


def test_quartiles_with_a_sample_not_divisible_by_four() -> None:
    """Twenty-two filers fall into quartiles of 5, 6, 5 and 6 under ceil(4r/n)."""
    counts = [quartiles([float(i) for i in range(22)]).count(q) for q in (1, 2, 3, 4)]

    assert counts == [5, 6, 5, 6]


def test_transition_matrix_counts_moves_between_quartiles() -> None:
    matrix = transition_matrix([1, 1, 2, 4], [1, 2, 2, 1])

    assert matrix[0] == [1, 1, 0, 0]
    assert matrix[1] == [0, 1, 0, 0]
    assert matrix[3] == [1, 0, 0, 0]
    assert sum(map(sum, matrix)) == 4


def test_ols_recovers_an_exact_line() -> None:
    fit = ols([0.2, 0.3, 0.4], [0.5, 0.65, 0.8])

    assert fit.slope == pytest.approx(1.5)
    assert fit.intercept == pytest.approx(0.2)
    assert fit.r_squared == pytest.approx(1.0)


def test_ols_refuses_a_constant_regressor() -> None:
    with pytest.raises(ValueError, match="undefined"):
        ols([0.3, 0.3, 0.3], [0.1, 0.2, 0.3])


def test_a_perfect_ordering_is_rarely_matched_by_chance() -> None:
    """Six filers in the same order in both cycles: one pairing in 720 does as well."""
    xs = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]

    p = permutation_p_value(xs, xs, permutations=20_000, seed=1)

    assert p < 0.005


def test_a_reversed_ordering_gives_no_evidence_of_persistence() -> None:
    p = permutation_p_value(
        [0.1, 0.2, 0.3, 0.4, 0.5], [0.5, 0.4, 0.3, 0.2, 0.1], permutations=2_000, seed=1
    )

    assert p == pytest.approx(1.0)


def test_a_fixed_seed_reproduces_the_p_value_exactly() -> None:
    xs, ys = [0.3, 0.1, 0.5, 0.2, 0.4, 0.6], [0.4, 0.2, 0.3, 0.1, 0.6, 0.5]

    first = permutation_p_value(xs, ys, permutations=5_000, seed=20261010)
    second = permutation_p_value(xs, ys, permutations=5_000, seed=20261010)

    assert first == second


def test_the_bootstrap_interval_brackets_the_estimate_and_reproduces() -> None:
    xs = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    ys = [0.2, 0.1, 0.4, 0.3, 0.6, 0.5, 0.8, 0.7, 1.0, 0.9]

    interval = bootstrap_interval(xs, ys, resamples=2_000, seed=7)
    again = bootstrap_interval(xs, ys, resamples=2_000, seed=7)

    assert interval.low <= spearman(xs, ys) <= interval.high
    assert interval == again
    assert interval.resamples == 2_000


def test_undefined_resamples_are_counted_rather_than_scored_as_zero() -> None:
    """With two filers, a resample drawing the same filer twice has no correlation."""
    interval = bootstrap_interval([0.1, 0.2], [0.3, 0.4], resamples=200, seed=3)

    assert interval.undefined > 0
    assert interval.low == interval.high == pytest.approx(1.0)
