// fingerprinting.js

const FP_MAX_DURATION = 20.0;

// events: array of { time, type, mx, my, is_correct, bubble_center, ... }
function computeFeaturesFromEvents(events) {
  const feats = {};

  const evs = [...events].sort(
    (a, b) => (a.time ?? 0.0) - (b.time ?? 0.0)
  );
  if (!evs.length) return feats;

  const moves = evs.filter(
    (e) => e.type === "move" && e.mx != null && e.my != null
  );
  const clicks = evs.filter(
    (e) =>
      (e.type === "bubble_click" || e.type === "empty_click") &&
      e.mx != null &&
      e.my != null
  );
  const instrEvs = evs.filter((e) => e.type === "instruction_shown");
  const startEvs = evs.filter((e) => e.type === "session_start");
  const endEvs = evs.filter((e) => e.type === "session_end");

  const tStart = startEvs.length ? startEvs[0].time : evs[0].time;
  const tEnd = endEvs.length ? endEvs[endEvs.length - 1].time : evs[evs.length - 1].time;
  const totalTime = Math.max(0.0, tEnd - tStart);

  // A. Timing
  feats.time_used_ratio = Math.min(1.0, totalTime / FP_MAX_DURATION);

  const firstClickTime = clicks.length ? clicks[0].time : tEnd;
  const instrTime = instrEvs.length ? instrEvs[0].time : tStart;
  feats.rt_first_click = Math.max(0.0, firstClickTime - instrTime);

  const targetClicks = clicks.filter(
    (e) => e.type === "bubble_click" && e.is_correct === true
  );
  if (targetClicks.length) {
    const rts = targetClicks.map((e) => Math.max(0.0, e.time - instrTime));
    const sum = rts.reduce((a, b) => a + b, 0);
    feats.rt_mean = sum / rts.length;
  } else {
    feats.rt_mean = totalTime;
  }

  if (clicks.length >= 2) {
    const times = clicks.map((e) => e.time);
    const intervals = [];
    for (let i = 0; i < times.length - 1; i++) {
      intervals.push(times[i + 1] - times[i]);
    }
    const meanIci = intervals.reduce((a, b) => a + b, 0) / intervals.length;
    const varIci =
      intervals.reduce((s, d) => s + (d - meanIci) ** 2, 0) /
      intervals.length;
    const stdIci = Math.sqrt(varIci);
    feats.ici_mean = meanIci;
    feats.ici_cv = stdIci / (meanIci + 1e-6);
  } else {
    feats.ici_mean = totalTime;
    feats.ici_cv = 0.0;
  }

  // B. Movement / path
  const {
    avg_speed,
    max_speed,
    curvature_mean,
    teleport_fraction,
    speed_std,
  } = pathFeatures(moves, clicks);
  feats.avg_speed = avg_speed;
  feats.max_speed = max_speed;
  feats.curvature_mean = curvature_mean;
  feats.teleport_fraction = teleport_fraction;
  feats.speed_std = speed_std;

  feats.move_count = moves.length;
  feats.click_count = clicks.length;

  // C. Click accuracy
  const { offset_mean, offset_std } = clickOffsets(clicks);
  feats.offset_mean = offset_mean;
  feats.offset_std = offset_std;

  // D. Errors / brute-force
  let incorrectClicks = 0;
  let emptyClicks = 0;
  for (const e of clicks) {
    if (e.type === "bubble_click" && e.is_correct === false) {
      incorrectClicks += 1;
    }
    if (e.type === "empty_click") {
      emptyClicks += 1;
    }
  }
  feats.incorrect_bubble_clicks = incorrectClicks;
  feats.empty_clicks = emptyClicks;

  const totalClicks = clicks.length;
  feats.total_clicks = totalClicks;
  feats.empty_click_ratio =
    totalClicks > 0 ? emptyClicks / totalClicks : 0.0;
  feats.clicks_per_second =
    totalTime > 0 ? totalClicks / totalTime : 0.0;

  // E. Exploration / attention
  const visitedInstr = moves.some(
    (e) => e.my >= 0 && e.my <= 60
  );
  feats.visited_instruction_area = visitedInstr ? 1.0 : 0.0;

  feats.pre_first_click_path_length = preFirstClickPath(
    moves,
    firstClickTime
  );

  // G. Performance level
  feats.attempts_count = 1.0;
  feats.superhuman_flag = superhumanFlag(feats);

  return feats;
}

function pathFeatures(moves, clicks) {
  if (moves.length < 2) {
    return {
      avg_speed: 0.0,
      max_speed: 0.0,
      curvature_mean: 1.0,
      teleport_fraction: 0.0,
      speed_std: 0.0,
    };
  }

  const TELEPORT_THRESHOLD = 3000.0;
  const speeds = [];
  let teleports = 0;

  for (let i = 0; i < moves.length - 1; i++) {
    const e1 = moves[i];
    const e2 = moves[i + 1];
    const dt = e2.time - e1.time;
    if (dt <= 0) continue;
    const dx = e2.mx - e1.mx;
    const dy = e2.my - e1.my;
    const dist = Math.hypot(dx, dy);
    const v = dist / dt;
    speeds.push(v);
    if (v > TELEPORT_THRESHOLD) teleports += 1;
  }

  let avg_speed = 0.0;
  let max_speed = 0.0;
  let speed_std = 0.0;
  let teleport_fraction = 0.0;

  if (speeds.length) {
    const sum = speeds.reduce((a, b) => a + b, 0);
    avg_speed = sum / speeds.length;
    max_speed = Math.max(...speeds);
    const meanV = avg_speed;
    const varV =
      speeds.reduce((s, v) => s + (v - meanV) ** 2, 0) /
      speeds.length;
    speed_std = Math.sqrt(varV);
    teleport_fraction = teleports / speeds.length;
  }

  let curvature_mean = 1.0;
  if (clicks.length >= 2) {
    const vals = [];
    for (let i = 0; i < clicks.length - 1; i++) {
      const tStart = clicks[i].time;
      const tEnd = clicks[i + 1].time;
      const segment = moves.filter(
        (m) => m.time >= tStart && m.time <= tEnd
      );
      if (segment.length < 2) continue;
      let pathLen = 0.0;
      for (let j = 0; j < segment.length - 1; j++) {
        const dx = segment[j + 1].mx - segment[j].mx;
        const dy = segment[j + 1].my - segment[j].my;
        pathLen += Math.hypot(dx, dy);
      }
      const straight = Math.hypot(
        segment[segment.length - 1].mx - segment[0].mx,
        segment[segment.length - 1].my - segment[0].my
      );
      if (straight > 0) {
        vals.push(pathLen / straight);
      }
    }
    curvature_mean = vals.length
      ? vals.reduce((a, b) => a + b, 0) / vals.length
      : 1.0;
  }

  return {
    avg_speed,
    max_speed,
    curvature_mean,
    teleport_fraction,
    speed_std,
  };
}

function clickOffsets(clicks) {
  const offsets = [];
  for (const e of clicks) {
    if (e.type !== "bubble_click") continue;
    const center = e.bubble_center;
    if (!center || center.length !== 2) continue;
    const [cx, cy] = center;
    const dx = e.mx - cx;
    const dy = e.my - cy;
    offsets.push(Math.hypot(dx, dy));
  }
  if (!offsets.length) {
    return { offset_mean: 0.0, offset_std: 0.0 };
  }
  const meanOff =
    offsets.reduce((a, b) => a + b, 0) / offsets.length;
  const varOff =
    offsets.reduce((s, d) => s + (d - meanOff) ** 2, 0) /
    offsets.length;
  const stdOff = Math.sqrt(varOff);
  return { offset_mean: meanOff, offset_std: stdOff };
}

function preFirstClickPath(moves, firstClickTime) {
  const pre = moves.filter((m) => m.time < firstClickTime);
  if (pre.length < 2) return 0.0;
  let path = 0.0;
  for (let i = 0; i < pre.length - 1; i++) {
    const dx = pre[i + 1].mx - pre[i].mx;
    const dy = pre[i + 1].my - pre[i].my;
    path += Math.hypot(dx, dy);
  }
  return path;
}

function superhumanFlag(feats) {
  const rt_first = feats.rt_first_click ?? 999.0;
  const rt_mean = feats.rt_mean ?? 999.0;
  const offset_mean = feats.offset_mean ?? 999.0;
  const offset_std = feats.offset_std ?? 999.0;
  const incorrect = feats.incorrect_bubble_clicks ?? 1.0;
  const empty = feats.empty_clicks ?? 1.0;
  const ici_cv = feats.ici_cv ?? 1.0;
  const ici_mean = feats.ici_mean ?? 999.0;

  const too_fast = rt_first < 0.15 && rt_mean < 0.25;
  const too_precise = offset_mean < 2.0 && offset_std < 1.0;
  const no_errors = incorrect === 0.0 && empty === 0.0;
  const too_regular = ici_cv < 0.1 && ici_mean < 0.4;

  const superhuman = too_fast && too_precise && no_errors && too_regular;
  return superhuman ? 1.0 : 0.0;
}

function classifyFingerprint(features, captchaPassed) {
  let suspicious = false;
  const reasons = [];
  let risk = 0.0;

  let risk_movement = 0.0;
  let risk_timing = 0.0;
  let risk_errors = 0.0;
  let risk_attention = 0.0;

  const tele = features.teleport_fraction ?? 0.0;
  const avg_speed = features.avg_speed ?? 0.0;
  const max_speed = features.max_speed ?? 0.0;
  const speed_std = features.speed_std ?? 0.0;

  const rt_first = features.rt_first_click ?? 999.0;
  const rt_mean = features.rt_mean ?? 999.0;
  const ici_mean = features.ici_mean ?? 999.0;
  const ici_cv = features.ici_cv ?? 0.0;

  const off_mean = features.offset_mean ?? 0.0;
  const off_std = features.offset_std ?? 0.0;

  const inc_clicks = features.incorrect_bubble_clicks ?? 0.0;
  const empty_clicks = features.empty_clicks ?? 0.0;
  const total_clicks = features.total_clicks ?? 0.0;
  const empty_ratio = features.empty_click_ratio ?? 0.0;
  const cps = features.clicks_per_second ?? 0.0;

  const visited_instr = features.visited_instruction_area ?? 0.0;
  const pre_path = features.pre_first_click_path_length ?? 0.0;

  const time_used = features.time_used_ratio ?? 0.0;
  const superhuman_flag = features.superhuman_flag ?? 0.0;

  const move_count = features.move_count ?? 0.0;
  const click_count = features.click_count ?? 0.0;

  // 1) Hard fails
  if (tele > 0.15) {
    suspicious = true;
    reasons.push("teleport_fraction_high");
    risk += 0.35;
    risk_movement += 0.35;
  } else if (tele > 0.08 && avg_speed > 900) {
    suspicious = true;
    reasons.push("teleports_with_high_speed");
    risk += 0.25;
    risk_movement += 0.25;
  }

  if (rt_first < 0.15 && rt_mean < 0.25) {
    suspicious = true;
    reasons.push("reaction_too_fast");
    risk += 0.3;
    risk_timing += 0.3;
  }

  if (superhuman_flag === 1.0) {
    suspicious = true;
    reasons.push("superhuman_pattern");
    risk += 0.4;
    risk_timing += 0.4;
  }

  if (click_count >= 2) {
    const moves_per_click = move_count / Math.max(click_count, 1.0);

    if (moves_per_click < 2.0) {
      risk += 0.2;
      risk_movement += 0.2;
      reasons.push("very_few_moves_per_click");
    }

    if (move_count <= 3 && captchaPassed) {
      suspicious = true;
      risk += 0.3;
      risk_movement += 0.3;
      reasons.push("almost_no_mouse_path_but_passed");
    }
  }

  // 2) Precision & regularity
  if (off_mean < 3.0 && off_std < 1.5) {
    risk += 0.15;
    risk_movement += 0.15;
    reasons.push("very_precise_clicks");
  }

  if (ici_cv < 0.12 && ici_mean < 0.45) {
    let base_add = 0.15;

    if (move_count <= 3 && click_count >= 2) {
      base_add = 0.3;
      suspicious = true;
      reasons.push("regular_timing_with_sparse_movement");
    }

    risk += base_add;
    risk_timing += base_add;
    reasons.push("timing_too_regular");
  }

  if (speed_std < 300.0 && avg_speed > 600.0) {
    risk += 0.1;
    risk_movement += 0.1;
    reasons.push("speed_pattern_too_stable");
  }

  if (
    off_mean < 3.0 &&
    off_std < 1.5 &&
    ici_cv < 0.12 &&
    ici_mean < 0.45
  ) {
    suspicious = true;
    reasons.push("precision_plus_regular_timing");
    risk += 0.2;
    risk_movement += 0.1;
    risk_timing += 0.1;
  }

  // 3) Brute-force style
  if (total_clicks >= 15 && empty_ratio > 0.5) {
    suspicious = true;
    reasons.push("empty_click_bruteforce");
    risk += 0.3;
    risk_errors += 0.3;
  }

  if (cps > 3.0) {
    suspicious = true;
    reasons.push("click_rate_too_high");
    risk += 0.25;
    risk_errors += 0.25;
  } else if (cps > 2.0) {
    risk += 0.15;
    risk_errors += 0.15;
    reasons.push("click_rate_high");
  }

  if (captchaPassed && inc_clicks >= 2) {
    suspicious = true;
    reasons.push("many_incorrect_bubble_clicks_but_passed");
    risk += 0.25;
    risk_errors += 0.25;
  } else if (inc_clicks >= 4) {
    risk += 0.15;
    risk_errors += 0.15;
    reasons.push("many_incorrect_bubble_clicks");
  }

  // 4) Attention cues
  if (visited_instr < 0.5 && rt_first < 0.4) {
    risk += 0.15;
    risk_attention += 0.15;
    reasons.push("no_instruction_visit_fast_rt");
  }

  if (pre_path < 30.0 && rt_first < 0.4) {
    risk += 0.1;
    risk_attention += 0.1;
    reasons.push("no_pre_click_exploration");
  }

  if (pre_path < 10.0 && rt_first > 2.0 && captchaPassed) {
    risk += 0.2;
    risk_attention += 0.2;
    suspicious = true;
    reasons.push("no_pre_click_path_but_slow_decision");
  }

  // 5) Time usage
  if (time_used < 0.15 && captchaPassed) {
    risk += 0.15;
    risk_timing += 0.15;
    reasons.push("very_fast_overall");
  }

  risk = Math.max(0.0, Math.min(1.0, risk));

  let is_human;
  if (suspicious || risk >= 0.5) {
    is_human = false;
    suspicious = true;
  } else {
    is_human = true;
  }

  return {
    is_human,
    suspicious,
    risk_score: risk,
    risk_movement,
    risk_timing,
    risk_errors,
    risk_attention,
    reasons,
  };
}
