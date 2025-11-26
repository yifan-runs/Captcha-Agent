from __future__ import annotations
from typing import List, Dict, Any, Tuple
import math

MAX_DURATION = 20.0


def compute_features_from_events(events: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Compute a rich set of behavioural features from raw mouse/click events.

    events: list of dicts, each having at least:
      - "time": float
      - "type": "move" | "bubble_click" | "empty_click" | ...
      - "mx", "my": mouse coordinates for moves/clicks
      - optional: "is_correct" (for bubble_click), "bubble_center" ((cx, cy))
      - optional: "session_start", "session_end", "instruction_shown" events

    Returns:
      feats: dict of feature_name -> float
    """
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
    avg_speed, max_speed, curvature_mean, teleport_frac, speed_std = _path_features(moves, clicks)
    feats["avg_speed"] = avg_speed
    feats["max_speed"] = max_speed
    feats["curvature_mean"] = curvature_mean
    feats["teleport_fraction"] = teleport_frac
    feats["speed_std"] = speed_std

    # simple counts (can be useful later)
    feats["move_count"] = float(len(moves))
    feats["click_count"] = float(len(clicks))

    # ---------- C. Click accuracy ----------
    offset_mean, offset_std = _click_offsets(clicks)
    feats["offset_mean"] = offset_mean
    feats["offset_std"] = offset_std

    # ---------- D. Errors / decisions ----------
    incorrect_clicks = sum(
        1 for e in clicks
        if e["type"] == "bubble_click" and e.get("is_correct") is False
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


def _path_features(
    moves: List[Dict[str, Any]],
    clicks: List[Dict[str, Any]],
) -> Tuple[float, float, float, float, float]:
    """
    Compute speed-based and curvature-based features.
    Returns:
      avg_speed, max_speed, curvature_mean, teleport_fraction, speed_std
    """
    if len(moves) < 2:
        return 0.0, 0.0, 1.0, 0.0, 0.0

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

    if speeds:
        avg_speed = sum(speeds) / len(speeds)
        max_speed = max(speeds)
        mean_v = avg_speed
        var_v = sum((v - mean_v) ** 2 for v in speeds) / len(speeds)
        speed_std = math.sqrt(var_v)
        teleport_frac = teleports / len(speeds)
    else:
        avg_speed = max_speed = speed_std = teleport_frac = 0.0

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

    return avg_speed, max_speed, curvature_mean, teleport_frac, speed_std


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
    You can tune this later with empirical data.
    """
    too_fast = feats.get("rt_first_click", 999.0) < 0.15 and feats.get("rt_mean", 999.0) < 0.25
    too_precise = feats.get("offset_mean", 999.0) < 2.0 and feats.get("offset_std", 999.0) < 1.0
    no_errors = feats.get("incorrect_bubble_clicks", 1.0) == 0.0 and feats.get("empty_clicks", 1.0) == 0.0
    too_regular = feats.get("ici_cv", 1.0) < 0.1 and feats.get("ici_mean", 999.0) < 0.4

    superhuman = too_fast and too_precise and no_errors and too_regular
    return 1.0 if superhuman else 0.0


def classify_fingerprint(features: Dict[str, float], captcha_passed: bool) -> Dict[str, Any]:
    """
    Stronger rule-based classifier with a risk score.

    Returns:
      {
        "is_human": bool,
        "suspicious": bool,
        "risk_score": float (0..1),
        "reasons": [str, ...]
      }
    """
    suspicious = False
    reasons: List[str] = []
    risk = 0.0

    # --- pull features safely ---
    tele = features.get("teleport_fraction", 0.0)
    avg_speed = features.get("avg_speed", 0.0)
    max_speed = features.get("max_speed", 0.0)
    speed_std = features.get("speed_std", 0.0)

    rt_first = features.get("rt_first_click", 999.0)
    rt_mean = features.get("rt_mean", 999.0)
    ici_mean = features.get("ici_mean", 999.0)
    ici_cv = features.get("ici_cv", 0.0)

    off_mean = features.get("offset_mean", 0.0)
    off_std = features.get("offset_std", 0.0)

    inc_clicks = features.get("incorrect_bubble_clicks", 0.0)
    empty_clicks = features.get("empty_clicks", 0.0)
    total_clicks = features.get("total_clicks", 0.0)
    empty_ratio = features.get("empty_click_ratio", 0.0)
    cps = features.get("clicks_per_second", 0.0)

    visited_instr = features.get("visited_instruction_area", 0.0)
    pre_path = features.get("pre_first_click_path_length", 0.0)

    time_used = features.get("time_used_ratio", 0.0)
    superhuman_flag = features.get("superhuman_flag", 0.0)

    # --- 1) Hard fails (red flags) ---

    # 1.1. Teleporting a lot at high speed
    if tele > 0.15:
        suspicious = True
        reasons.append("teleport_fraction_high")
        risk += 0.35
    elif tele > 0.08 and avg_speed > 900:
        suspicious = True
        reasons.append("teleports_with_high_speed")
        risk += 0.25

    # 1.2. Reaction time unrealistically fast
    if rt_first < 0.15 and rt_mean < 0.25:
        suspicious = True
        reasons.append("reaction_too_fast")
        risk += 0.3

    # 1.3. Superhuman combo flag
    if superhuman_flag == 1.0:
        suspicious = True
        reasons.append("superhuman_pattern")
        risk += 0.4

    # --- 2) Precision & regularity (aimbot-style) ---

    # Very precise clicking
    if off_mean < 3.0 and off_std < 1.5:
        risk += 0.15
        reasons.append("very_precise_clicks")

    # Very regular timing and limited variability in speeds
    if ici_cv < 0.12 and ici_mean < 0.45:
        risk += 0.15
        reasons.append("timing_too_regular")

    if speed_std < 300.0 and avg_speed > 600.0:
        risk += 0.1
        reasons.append("speed_pattern_too_stable")

    # Combine precision + regular timing into stronger suspicion
    if off_mean < 3.0 and off_std < 1.5 and ici_cv < 0.12 and ici_mean < 0.45:
        suspicious = True
        reasons.append("precision_plus_regular_timing")
        risk += 0.2

    # --- 3) Brute-force style (many errors / spam) ---

    # Empty-click heavy in a short game
    if total_clicks >= 15 and empty_ratio > 0.5:
        suspicious = True
        reasons.append("empty_click_bruteforce")
        risk += 0.3

    # Very high click rate
    if cps > 3.0:
        suspicious = True
        reasons.append("click_rate_too_high")
        risk += 0.25
    elif cps > 2.0:
        risk += 0.15
        reasons.append("click_rate_high")

    # Many incorrect bubble clicks + still passed is weird
    if captcha_passed and inc_clicks >= 2:
        suspicious = True
        reasons.append("many_incorrect_bubble_clicks_but_passed")
        risk += 0.25
    elif inc_clicks >= 4:
        risk += 0.15
        reasons.append("many_incorrect_bubble_clicks")

    # --- 4) Cognitive / attention cues ---

    # Never visiting instruction area + very fast RT
    if visited_instr < 0.5 and rt_first < 0.4:
        risk += 0.15
        reasons.append("no_instruction_visit_fast_rt")

    # No exploration path at all before first click and fast RT
    if pre_path < 30.0 and rt_first < 0.4:
        risk += 0.1
        reasons.append("no_pre_click_exploration")

    # --- 5) Time usage patterns ---

    if time_used < 0.15 and captcha_passed:
        risk += 0.15
        reasons.append("very_fast_overall")

    # --- normalise risk & final decision ---

    risk = max(0.0, min(1.0, risk))

    # Final human vs bot decision:
    # - non-human if hard suspicious OR risk very high
    if suspicious or risk >= 0.6:
        is_human = False
        suspicious = True
    else:
        is_human = True

    return {
        "is_human": is_human,
        "suspicious": suspicious,
        "risk_score": risk,
        "reasons": reasons,
    }