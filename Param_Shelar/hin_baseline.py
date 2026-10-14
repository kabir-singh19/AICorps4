"""Published HIN membership; it is never a model feature or invented ranking."""
from __future__ import annotations


def hin_membership(sites):
    values = [s.get("in_hin") for s in sites]
    if all(v is None for v in values):
        return None
    if any(not isinstance(v, bool) for v in values):
        raise ValueError("complete boolean HIN mapping required")
    return {str(s["site_id"]) for s in sites if s["in_hin"]}


def overlap_membership(overlap_length, segment_length):
    import math
    if not math.isfinite(overlap_length) or not math.isfinite(segment_length) or segment_length <= 0 or not 0 <= overlap_length <= segment_length:
        raise ValueError("invalid segment/HIN overlap lengths")
    return overlap_length >= .5*segment_length
