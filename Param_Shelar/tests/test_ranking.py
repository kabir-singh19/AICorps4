import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ranking import (FLAG_SHARE, FLAG_TOLERANCE, capture_rate, flag_by_length,  # noqa: E402
                     flagged_share, fsi_rate, rank_sites)


# fsi_rate

def test_rate_hand_check():
    # 6 crashes over 3 years, 10% of them K or A, on a 0.1-mile site: 6/3 * 0.1 / 0.1 = 2.0
    assert fsi_rate([6.0], [0.1], [0.1], 3)[0] == pytest.approx(2.0)


def test_rate_accepts_one_p_fsi_for_all_sites():
    rates = fsi_rate([1.0, 2.0], 0.5, [0.1, 0.1], 1)
    assert rates == pytest.approx([5.0, 10.0])


@pytest.mark.parametrize("args", [
    ([1.0], [0.1], [0.0], 3),       # zero length, e.g. an intersection with no agreed length
    ([1.0], [0.1], [np.nan], 3),
    ([1.0], [1.5], [0.1], 3),       # probability above 1
    ([-1.0], [0.1], [0.1], 3),
    ([1.0], [0.1], [0.1], 0),
])
def test_rate_rejects_bad_inputs(args):
    with pytest.raises(ValueError):
        fsi_rate(*args)


# rank_sites

def test_highest_score_ranks_first():
    assert list(rank_sites([10, 11, 12], [0.2, 0.9, 0.5])) == [3, 1, 2]


def test_ties_go_to_the_lower_site_id():
    assert list(rank_sites([30, 10, 20], [1.0, 1.0, 1.0])) == [3, 1, 2]


def test_ranking_does_not_depend_on_input_order():
    rng = np.random.default_rng(0)
    ids = np.arange(500)
    score = rng.integers(0, 20, 500).astype(float)  # many ties
    ranks = dict(zip(ids, rank_sites(ids, score)))
    shuffle = rng.permutation(500)
    shuffled = dict(zip(ids[shuffle], rank_sites(ids[shuffle], score[shuffle])))
    assert ranks == shuffled


def test_string_site_ids_work():
    assert list(rank_sites(["b", "a"], [1.0, 1.0])) == [2, 1]


@pytest.mark.parametrize("ids, score", [
    ([1, 1], [0.5, 0.2]),
    ([1, 2], [0.5, np.nan]),
    ([1, 2, 3], [0.5, 0.2]),
])
def test_rank_rejects_bad_inputs(ids, score):
    with pytest.raises(ValueError):
        rank_sites(ids, score)


# flag_by_length

def test_flags_land_closest_to_the_target():
    length = np.ones(10)
    rank = np.arange(1, 11)
    # target 2.7 mi: 3 sites (2.7 away by 0.3) beats 2 sites (0.7)
    assert flag_by_length(rank, length, share=0.27, tolerance=None).sum() == 3
    # target 2.2 mi: 2 sites (0.2) beats 3 sites (0.8)
    assert flag_by_length(rank, length, share=0.22, tolerance=None).sum() == 2


def test_corridor_sized_network_meets_eleven_percent():
    # About the size of S1 network v0_2019: 185 segments of 0.055 to 0.099 mi
    rng = np.random.default_rng(1)
    length = rng.uniform(0.055, 0.099, 185)
    rank = rank_sites(np.arange(185), rng.random(185))
    flagged = flag_by_length(rank, length)
    assert abs(flagged_share(flagged, length) - FLAG_SHARE) <= FLAG_TOLERANCE


def test_flagged_sites_are_exactly_the_top_ranks():
    rng = np.random.default_rng(2)
    length = rng.uniform(0.05, 0.15, 300)
    rank = rank_sites(np.arange(300), rng.random(300))
    flagged = flag_by_length(rank, length)
    n = flagged.sum()
    assert set(rank[flagged]) == set(range(1, n + 1))


@pytest.mark.parametrize("share", [0.05, 0.11, 0.20])
def test_sensitivity_shares(share):
    rng = np.random.default_rng(3)
    length = rng.uniform(0.05, 0.15, 300)
    rank = rank_sites(np.arange(300), rng.random(300))
    flagged = flag_by_length(rank, length, share=share)
    assert abs(flagged_share(flagged, length) - share) <= FLAG_TOLERANCE


def test_one_long_site_cannot_meet_tolerance():
    length = np.array([5.0, 1, 1, 1, 1, 1])  # top site alone is 50% of the network
    rank = np.arange(1, 7)
    with pytest.raises(ValueError, match="outside"):
        flag_by_length(rank, length)
    assert flag_by_length(rank, length, tolerance=None).sum() == 0


@pytest.mark.parametrize("rank, length, share", [
    ([1, 1, 2], [0.1, 0.1, 0.1], 0.11),   # repeated rank
    ([1, 2, 4], [0.1, 0.1, 0.1], 0.11),   # gap in ranks
    ([1, 2], [0.1, 0.0], 0.11),           # zero length
    ([1, 2], [0.1, 0.1], 0.0),            # share of 0
])
def test_flag_rejects_bad_inputs(rank, length, share):
    with pytest.raises(ValueError):
        flag_by_length(rank, length, share=share, tolerance=None)


# capture_rate

def test_capture_counts_unmatched_crashes_in_the_denominator():
    crashes = [1, 1, 2, 3, None]  # the last crash was not matched to any site
    assert capture_rate(crashes, flagged_site_ids=[1]) == pytest.approx(2 / 5)


def test_capture_bounds():
    crashes = [1, 2, 3]
    assert capture_rate(crashes, []) == 0
    assert capture_rate(crashes, [1, 2, 3]) == 1


def test_capture_rejects_empty_test_window():
    with pytest.raises(ValueError):
        capture_rate([], [1])
