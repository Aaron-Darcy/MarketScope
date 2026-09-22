from __future__ import annotations

import pytest

from marketscope.ranking import average_ranks, spearman


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
