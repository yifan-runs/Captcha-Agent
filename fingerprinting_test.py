from __future__ import annotations
from typing import List, Dict, Any, Tuple
import math

MAX_DURATION = 20.0


def compute_features_from_events(events: List[Dict[str, Any]]) -> Dict[str, float]:
    feats: Dict[str, float] = {}

    evs = sorted(events, key=lambda e: e.get("time", 0.0))
    if not evs:
        return feats

    moves = [e for e in evs if e["type"] == "move" and e.get("mx") is not None]
    clicks = [e for e in evs if e["type"] in ("bubble_click", "empty_click") and e.get("mx") is not None]
    instr_evs = [e for e in evs if e["type"] == "instruction_shown"]
    start_evs = [e for e in evs if e["type"] == "session_start"]
    end_evs = [e for e in evs if e["type"] == "session_end"]

    t_start = start_evs[0]["time"] if start_evs else evs[0]["time"]
    t_end = end_evs[-1]["time"] if end_evs else evs[-1]["time"]
    total_time = max(0.0, t_end - t_start)

    # ---------- A. Timing ----------
    feats["time_used_ratio"] = min(1.0, total_time / MAX_DURATION)

    if clicks:
        first_click_time = clicks[0]["time"]
    else:
        first_click_time = t_end

    instr_time = instr_evs[0]["time"] if instr_evs else t_start
    feats["rt_first_click"] = max(0.0, first_click_time - instr_time)

    # Treat clicks marked is_correct=True as “target clicks”
    target_clicks = [e for e in clicks if e.get("is_correct") is True]
    if target_clicks:
        rts = [max(0.0, e["time"] - instr_time) for e in target_clicks]
        feats["rt_mean"] = sum(rts) / len(rts)
    else:
        feats["rt_mean"] = total_time  # fallback if no correct clicks

    if len(clicks) >= 2:
        times = [e["time"] for e in clicks]
        intervals = [times[i + 1] - times[i] for i in range(len(times) - 1)]
        mean_ici = sum(intervals) / len(intervals)
        var_ici = sum((d - mean_ici) ** 2 for d in intervals) / len(intervals)
        std_ici = math.sqrt(var_ici)
        feats["ici_mean"] = mean_ici
        feats["ici_cv"] = std_ici / (mean_ici + 1e-6)
    else:
        feats["ici_mean"] = total_time
        feats["ici_cv"] = 0.0

    # ---------- B. Movement / path ----------
    avg_speed, max_speed, curvature_mean, teleport_frac = _path_features(moves, clicks)
    feats["avg_speed"] = avg_speed
    feats["max_speed"] = max_speed
    feats["curvature_mean"] = curvature_mean
    feats["teleport_fraction"] = teleport_frac

    # ---------- C. Click accuracy ----------
    offset_mean, offset_std = _click_offsets(clicks)
    feats["offset_mean"] = offset_mean
    feats["offset_std"] = offset_std

    # ---------- D. Errors / decisions ----------
    # “incorrect_bubble_clicks” = incorrect bubble clicks (violating ordering)
    incorrect_clicks = sum(
        1 for e in clicks if e["type"] == "bubble_click" and e.get("is_correct") is False
    )
    empty_clicks = sum(1 for e in clicks if e["type"] == "empty_click")
    feats["incorrect_bubble_clicks"] = float(incorrect_clicks)
    feats["empty_clicks"] = float(empty_clicks)

    # ---------- D.1 Brute-force related counts ----------
    total_clicks = len(clicks)
    feats["total_clicks"] = float(total_clicks)

    if total_clicks > 0:
        feats["empty_click_ratio"] = empty_clicks / total_clicks
    else:
        feats["empty_click_ratio"] = 0.0

    if total_time > 0:
        feats["clicks_per_second"] = total_clicks / total_time
    else:
        feats["clicks_per_second"] = 0.0

    # ---------- E. Exploration / attention ----------
    # Assume instruction area is at top (e.g., y in [0, 60])
    visited_instr = any(0 <= e.get("my", 9999) <= 60 for e in moves)
    feats["visited_instruction_area"] = 1.0 if visited_instr else 0.0

    pre_path = _pre_first_click_path(moves, first_click_time)
    feats["pre_first_click_path_length"] = pre_path

    # ---------- G. Performance level ----------
    # attempts_count: for now, this run is one attempt (you can override later)
    feats["attempts_count"] = 1.0

    feats["superhuman_flag"] = _superhuman_flag(feats)

    return feats


def _path_features(moves: List[Dict[str, Any]], clicks: List[Dict[str, Any]]) -> Tuple[float, float, float, float]:
    if len(moves) < 2:
        return 0.0, 0.0, 1.0, 0.0

    speeds: List[float] = []
    teleports = 0
    TELEPORT_THRESHOLD = 3000.0  # px/s, adjust if needed

    for i in range(len(moves) - 1):
        e1, e2 = moves[i], moves[i + 1]
        dt = e2["time"] - e1["time"]
        if dt <= 0:
            continue
        dx = e2["mx"] - e1["mx"]
        dy = e2["my"] - e1["my"]
        dist = math.hypot(dx, dy)
        v = dist / dt
        speeds.append(v)
        if v > TELEPORT_THRESHOLD:
            teleports += 1

    avg_speed = sum(speeds) / len(speeds) if speeds else 0.0
    max_speed = max(speeds) if speeds else 0.0
    teleport_frac = teleports / len(speeds) if speeds else 0.0

    # Curvature between clicks
    if len(clicks) < 2:
        curvature_mean = 1.0
    else:
        vals: List[float] = []
        for i in range(len(clicks) - 1):
            t_start = clicks[i]["time"]
            t_end = clicks[i + 1]["time"]
            segment = [m for m in moves if t_start <= m["time"] <= t_end]
            if len(segment) < 2:
                continue
            path_len = 0.0
            for j in range(len(segment) - 1):
                dx = segment[j + 1]["mx"] - segment[j]["mx"]
                dy = segment[j + 1]["my"] - segment[j]["my"]
                path_len += math.hypot(dx, dy)
            straight = math.hypot(
                segment[-1]["mx"] - segment[0]["mx"],
                segment[-1]["my"] - segment[0]["my"],
            )
            if straight > 0:
                vals.append(path_len / straight)
        curvature_mean = sum(vals) / len(vals) if vals else 1.0

    return avg_speed, max_speed, curvature_mean, teleport_frac


def _click_offsets(clicks: List[Dict[str, Any]]) -> Tuple[float, float]:
    offsets: List[float] = []
    for e in clicks:
        if e["type"] != "bubble_click":
            continue
        center = e.get("bubble_center")
        if not center:
            continue
        cx, cy = center
        dx = e["mx"] - cx
        dy = e["my"] - cy
        offsets.append(math.hypot(dx, dy))

    if not offsets:
        return 0.0, 0.0
    mean_off = sum(offsets) / len(offsets)
    var_off = sum((d - mean_off) ** 2 for d in offsets) / len(offsets)
    std_off = math.sqrt(var_off)
    return mean_off, std_off


def _pre_first_click_path(moves: List[Dict[str, Any]], first_click_time: float) -> float:
    pre = [m for m in moves if m["time"] < first_click_time]
    if len(pre) < 2:
        return 0.0
    path = 0.0
    for i in range(len(pre) - 1):
        dx = pre[i + 1]["mx"] - pre[i]["mx"]
        dy = pre[i + 1]["my"] - pre[i]["my"]
        path += math.hypot(dx, dy)
    return path


def _superhuman_flag(feats: Dict[str, float]) -> float:
    """
    Simple heuristic: very fast, very precise, no errors, very regular timing.
    You will tune this later once you see real data.
    """
    too_fast = feats["rt_first_click"] < 0.15 and feats["rt_mean"] < 0.25
    too_precise = feats["offset_mean"] < 2.0 and feats["offset_std"] < 1.0
    no_errors = feats["incorrect_bubble_clicks"] == 0.0 and feats["empty_clicks"] == 0.0
    too_regular = feats["ici_cv"] < 0.1 and feats["ici_mean"] < 0.4

    superhuman = too_fast and too_precise and no_errors and too_regular
    return 1.0 if superhuman else 0.0


def classify_fingerprint(features: Dict[str, float], captcha_passed: bool) -> Dict[str, Any]:
    """
    Very simple rule-based classifier.
    """
    suspicious = False
    reasons = []

    tele = features["teleport_fraction"]
    avg_speed = features["avg_speed"]
    empty = features["empty_clicks"]
    empty_ratio = features.get("empty_click_ratio", 0.0)
    cps = features.get("clicks_per_second", 0.0)

    # Teleport behaviour (already tuned)
    if tele > 0.12 or (tele > 0.07 and avg_speed > 900 and empty == 0.0):
        suspicious = True
        reasons.append("too_many_teleports")

    # Brute-force clicking: very fast, mostly empty clicks
    if cps > 4.0 and empty_ratio > 0.6:
        suspicious = True
        reasons.append("bruteforce_clicking_pattern")

    # Extremely fast reading + solving (very strict, rarely triggered)
    if features["rt_first_click"] < 0.15 and features["rt_mean"] < 0.25:
        suspicious = True
        reasons.append("reaction_too_fast")

    # Unrealistically precise clicking
    if features["offset_mean"] < 2.0 and features["offset_std"] < 1.0:
        suspicious = True
        reasons.append("clicks_too_precise")

    # Overly regular timing between clicks
    if features["ici_cv"] < 0.1 and features["ici_mean"] < 0.4:
        suspicious = True
        reasons.append("click_timing_too_regular")

    if features["superhuman_flag"] == 1.0:
        suspicious = True
        reasons.append("superhuman_pattern")

    is_human = not suspicious

    return {
        "is_human": is_human,
        "suspicious": suspicious,
        "reasons": reasons,
    }
