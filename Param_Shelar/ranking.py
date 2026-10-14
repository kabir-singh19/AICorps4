"""Rates, ranks, flags and capture rate for methods A, B and C (FSR 3.2.1.8 to 3.2.1.10).

    fsi_rate     expected F&SI crashes per mile per year = (n_eb / n_years) * p_fsi / length_mi
    rank_sites   1 = highest rate; ties go to the lower site_id, so a re-run gives the same order
    flag_by_length
                 the highest-ranked sites whose combined length is closest to a share of the
                 network (11% for the main result, other shares for the sensitivity runs)
    capture_rate test-window crashes on flagged sites / all test-window crashes in the area

Lengths are whatever the caller passes, in miles, one per site. How long an intersection counts
as (ICD Table 9 says its 250 ft influence zone) is still an open decision with S1 (see
docs/interfaces.md), so this module does not pick a value.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
from numpy.typing import ArrayLike

FLAG_SHARE = 0.11       # share of network length flagged (FSR 3.2.1.9), the HIN's share
FLAG_TOLERANCE = 0.005  # allowed miss, in shares of network length: 10.5% to 11.5%


def fsi_rate(n_eb: ArrayLike, p_fsi: ArrayLike, length_mi: ArrayLike, n_years: float) -> np.ndarray:
    """Expected F&SI crashes per mile per year for each site.

    n_eb is the EB estimate of all crashes over the history window (empirical_bayes), p_fsi the
    probability that a crash at the site is K or A (severity.py), n_years the window length.
    """
    n = _array(n_eb, "n_eb")
    p = _array(p_fsi, "p_fsi")
    length = _array(length_mi, "length_mi")
    if np.any(n < 0):
        raise ValueError("n_eb must not be negative")
    if np.any((p < 0) | (p > 1)):
        raise ValueError("p_fsi must be between 0 and 1")
    if np.any(length <= 0):
        raise ValueError("length_mi must be greater than 0 for every site")
    if not np.isfinite(n_years) or n_years <= 0:
        raise ValueError("n_years must be greater than 0")
    n, p, length = np.broadcast_arrays(n, p, length)
    return n / n_years * p / length


def rank_sites(site_id: ArrayLike, score: ArrayLike) -> np.ndarray:
    """Rank sites by score, 1 = highest. Equal scores go to the lower site_id first."""
    ids = np.asarray(site_id)
    s = _array(score, "score")
    if ids.shape != s.shape or ids.ndim != 1:
        raise ValueError(f"site_id has shape {ids.shape} but score has shape {s.shape}")
    if len(np.unique(ids)) != ids.size:
        raise ValueError("site_id values must be unique")
    order = np.lexsort((ids, -s))  # last key sorts first: score descending, then site_id
    ranks = np.empty(ids.size, dtype=int)
    ranks[order] = np.arange(1, ids.size + 1)
    return ranks


def flag_by_length(rank: ArrayLike, length_mi: ArrayLike, share: float = FLAG_SHARE,
                   tolerance: float | None = FLAG_TOLERANCE) -> np.ndarray:
    """Flag the top-ranked sites whose combined length is closest to `share` of the network.

    Sites are taken strictly in rank order, never skipped, so the flagged set is always the top
    n sites. Raises if the result misses `share` by more than `tolerance`, which can only happen
    when one site is long compared with the network; pass tolerance=None to accept any result.
    """
    r = np.asarray(rank)
    length = _array(length_mi, "length_mi")
    if r.shape != length.shape or r.ndim != 1:
        raise ValueError(f"rank has shape {r.shape} but length_mi has shape {length.shape}")
    if not np.array_equal(np.sort(r), np.arange(1, r.size + 1)):
        raise ValueError("rank must run 1, 2, ..., n with no gaps or repeats")
    if np.any(length <= 0):
        raise ValueError("length_mi must be greater than 0 for every site")
    if not 0 < share <= 1:
        raise ValueError("share must be greater than 0 and at most 1")

    order = np.argsort(r)
    cumulative = np.cumsum(length[order])
    target = share * cumulative[-1]
    n = int(np.searchsorted(cumulative, target, side="right"))  # sites that fit under target
    below = cumulative[n - 1] if n > 0 else 0.0
    if n < r.size and cumulative[n] - target < target - below:
        n += 1  # one more site lands closer to the target than stopping short

    flagged = np.zeros(r.size, dtype=bool)
    flagged[order[:n]] = True
    achieved = flagged_share(flagged, length)
    if tolerance is not None and abs(achieved - share) > tolerance:
        raise ValueError(f"flagged {achieved:.2%} of network length, outside {share:.1%} "
                         f"± {tolerance:.1%}")
    return flagged


def flagged_share(flagged: ArrayLike, length_mi: ArrayLike) -> float:
    """Share of total network length covered by the flagged sites."""
    mask = np.asarray(flagged, dtype=bool)
    length = _array(length_mi, "length_mi")
    return float(length[mask].sum() / length.sum())


def capture_rate(crash_site_ids: Iterable, flagged_site_ids: Iterable) -> float:
    """Share of test-window crashes that happened on flagged sites.

    Pass one entry per test-window crash in the analysis area: the site it was matched to, or
    None if it was not matched. Unmatched crashes stay in the denominator, as the capture rate
    is out of all crashes in the area (FSR 3.2.1.10), not only the matched ones.
    """
    crashes = list(crash_site_ids)
    if not crashes:
        raise ValueError("no test-window crashes to score")
    flagged = set(flagged_site_ids)
    return sum(site in flagged for site in crashes) / len(crashes)


def _array(values: ArrayLike, name: str) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must be finite")
    return arr
