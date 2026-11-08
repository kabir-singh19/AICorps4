"""Plain-language names for model factors (SHAP top 5 per flagged site)."""
from __future__ import annotations

import math

FUNC_CLASS = {1: "interstate", 2: "freeway or expressway", 3: "principal arterial", 4: "minor arterial",
              5: "major collector", 6: "minor collector", 7: "local street"}
MEDIAN = {"0": "no median", "2": "curbed median", "3": "raised or depressed median", "7": "two-way left-turn lane"}
ACCESS = {"1": "full access control", "2": "partial access control", "3": "no access control"}
CURB = {"0": "no curb", "1": "curb", "2": "curb and gutter"}

TEMPLATES = {
    "traffic": "traffic exposure ({aadt:,.0f} vehicles/day)",
    "nb_tot_3y": "{v:.0f} crashes on sites within 250 m in the last 3 years",
    "nb_kabc_3y": "{v:.0f} injury crashes on sites within 250 m in the last 3 years",
    "speed_limit": "{v:.0f} mph speed limit",
    "num_lanes": "{v:.0f} lanes",
    "lane_width_ft": "{v:.0f} ft lanes",
    "median_width_ft": "{v:.0f} ft median",
    "shoulder_inside_ft": "{v:.0f} ft inside shoulder",
    "shoulder_outside_ft": "{v:.0f} ft outside shoulder",
    "surface_width_ft": "{v:.0f} ft pavement width",
    "truck_pct": "{v:.1f}% trucks",
    "curvature_deg_per_mi": "{v:.0f} degrees of curve per mile",
    "dist_to_intersection_m": "{v:.0f} m to the nearest intersection",
    "length_mi": "segment length {v:.2f} mi",
    "osm_bars_200m": "{v:.0f} bars within 200 m",
    "osm_bus_stops_200m": "{v:.0f} bus stops within 200 m",
    "osm_crossings_30m": "{v:.0f} marked crossings within 30 m",
    "osm_restaurants_100m": "{v:.0f} restaurants within 100 m",
    "osm_schools_400m": "{v:.0f} schools within 400 m",
    "osm_signalized_intersections_30m": "{v:.0f} traffic signals within 30 m",
    "osm_sidewalk_share": "{pct:.0f}% of the segment has a mapped sidewalk",
    "legs": "{v:.0f}-leg intersection",
}


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def describe(feature, value, aadt):
    """Readable text for one factor. Missing values say so instead of printing nan."""
    v = _num(value)
    if feature == "traffic":
        return TEMPLATES["traffic"].format(aadt=aadt)
    if feature == "func_class":
        return f"functional class: {FUNC_CLASS.get(int(v), 'unknown')}" if v is not None else "functional class not recorded"
    if feature == "median_type":
        return MEDIAN.get(str(value), "median type not recorded") if value is not None else "median type not recorded"
    if feature == "access_control":
        return ACCESS.get(str(value), "access control not recorded") if value is not None else "access control not recorded"
    if feature in ("curb_left", "curb_right"):
        side = "left" if feature.endswith("left") else "right"
        return f"{side} side: {CURB.get(str(value), 'curb not recorded')}" if value is not None else f"{side} curb not recorded"
    if feature == "aadt_imputed":
        return "traffic count estimated (no TxDOT count)" if v else "TxDOT traffic count available"
    if feature == "state_route":
        return "on a state route (TxDOT)" if v else "not on a state route"
    if feature == "signalized":
        return "signalized" if v else "not signalized"
    if feature == "interchange":
        return "part of an interchange" if v else "not an interchange"
    if v is None:
        return f"{feature.replace('_', ' ')} not recorded"
    template = TEMPLATES.get(feature)
    if template is None:
        return f"{feature.replace('_', ' ')} = {v:g}"
    return template.format(v=v, pct=100 * v)
