### VLM Tracking Assistant (new)
# Also aproximates bubble diameter, so that VLM does not have to
# Sebastian Damodar Slawski
# 21367338
###

import cv2
import numpy as np
import math
import queue
import threading
import time
from typing import Tuple, List, Dict
from selenium_portal import SeleniumPortal

def fit_circle_ls(pts: np.ndarray):
    """
    least-squares circle fit: x^2 + y^2 + ax + by + c = 0
    """
    x = pts[:, 0]
    y = pts[:, 1]
    A = np.c_[2 * x, 2 * y, np.ones_like(x)]
    b = x ** 2 + y ** 2
    a, b_, c = np.linalg.lstsq(A, b, rcond = None)[0]
    cx, cy = a, b_
    r = math.sqrt(cx * cx + cy * cy + c)
    return float(cx), float(cy), float(r)

def detect_bubbles(frame: np.ndarray, min_area: float = 150.0, min_points: int = 20):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    mask = ((s > 60) & (v > 80)).astype("uint8") * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

    detections: List[Dict] = []
    for c in contours:
        if len(c) < min_points:
            continue
        area = cv2.contourArea(c)
        if area < min_area:
            continue

        pts = c.reshape(-1, 2).astype(np.float32)
        try:
            cx, cy, r = fit_circle_ls(pts)
        except Exception:
            continue

        if r < 5:
            continue

        mask_c = np.zeros(frame.shape[:2], np.uint8)
        cv2.drawContours(mask_c, [c], -1, 255, -1)
        mean_color = cv2.mean(frame, mask=mask_c)[:3]
        detections.append({
            "cx": cx,
            "cy": cy,
            "r": r,
            "color": mean_color,
        })

    return detections

def _greedy_match(cost: np.ndarray):
    nT, nD = cost.shape
    pairs: List[Tuple[int, int]] = []
    usedT, usedD = set(), set()
    flat = [(cost[i, j], i, j) for i in range(nT) for j in range(nD)]
    flat.sort(key=lambda x: x[0])
    for c, i, j in flat:
        if i in usedT or j in usedD:
            continue
        pairs.append((i, j))
        usedT.add(i)
        usedD.add(j)
    return pairs

def match_tracks(
    tracks: Dict[int, Dict],
    detections: List[Dict],
    pos_w: float = 0.1,
    r_w: float = 5.0,
    col_w: float = 0.5,
    max_cost: float = 1e9,
):
    if not tracks or not detections:
        return [], list(tracks.keys()), list(range(len(detections)))

    track_ids = list(tracks.keys())
    nT, nD = len(track_ids), len(detections)
    cost = np.zeros((nT, nD), np.float32)
    for ti, tid in enumerate(track_ids):
        t = tracks[tid]
        state = t["pred_state"]
        px, py, pr = state[0, 0], state[1, 0], state[4, 0]
        col_t = np.array(t["color"])
        for dj, d in enumerate(detections):
            dx, dy, dr = d["cx"], d["cy"], d["r"]
            col_d = np.array(d["color"])
            pos_dist = math.hypot(px - dx, py - dy)
            r_dist = abs(pr - dr)
            col_dist = np.linalg.norm(col_t - col_d)
            cost[ti, dj] = pos_w * pos_dist + r_w * r_dist + col_w * col_dist

    pairs = _greedy_match(cost)
    matches = []
    unmatched_tracks = set(track_ids)
    unmatched_dets = set(range(len(detections)))
    for r, c in pairs:
        if cost[r, c] > max_cost:
            continue
        tid = track_ids[r]
        matches.append((tid, c))
        unmatched_tracks.discard(tid)
        unmatched_dets.discard(c)

    return matches, list(unmatched_tracks), list(unmatched_dets)


def resurrect_from_retired(
    det: Dict,
    retired_tracks: Dict,
    radius_tol: float = 3.0,
    color_tol: float = 60.0,
):
    if not retired_tracks:
        return None

    best_tid = None
    best_score = None
    col_d = np.array(det["color"])
    for tid, t in retired_tracks.items():
        dr = abs(t["radius"] - det["r"])
        if dr > radius_tol:
            continue

        col_t = np.array(t["color"])
        col_dist = np.linalg.norm(col_t - col_d)
        if col_dist > color_tol:
            continue

        score = dr + 0.1 * col_dist
        if best_score is None or score < best_score:
            best_score = score
            best_tid = tid

    if best_tid is None:
        return None

    t = retired_tracks.pop(best_tid)
    return best_tid, t


def kalman_tracker(
    source: SeleniumPortal = None,
    roi: Tuple[float, float, float, float] = (0, 0, 1, 1),
    max_misses: int = 60,
    min_area: float = 150.0,
    stop_event: threading.Event = None,
):
    cap = source or SeleniumPortal("http://127.0.0.1:5000/captcha")
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video source {source}")

    if any([not (0.0 <= x <= 1.0) for x in roi]) or roi[0] > roi[2] or roi[1] > roi[3]:
        raise Exception(f"Invalid RoI {roi}")

    next_id = 0
    tracks: Dict[int, Dict] = {}
    retired_tracks: Dict[int, Dict] = {}
    frame_idx = 0

    def create_kalman(x: float, y: float, r: float):
        kf = cv2.KalmanFilter(5, 3)
        dt = 1.0

        kf.transitionMatrix = np.array([
            [1, 0, dt, 0, 0],
            [0, 1, 0, dt, 0],
            [0, 0, 1,  0, 0],
            [0, 0, 0,  1, 0],
            [0, 0, 0,  0, 1],
        ], np.float32)

        kf.measurementMatrix = np.array([
            [1, 0, 0, 0, 0],
            [0, 1, 0, 0, 0],
            [0, 0, 0, 0, 1],
        ], np.float32)

        kf.processNoiseCov = np.eye(5, dtype=np.float32) * 1e-3
        kf.measurementNoiseCov = np.eye(3, dtype=np.float32) * 1e-1
        kf.errorCovPost = np.eye(5, dtype=np.float32)
        kf.statePost = np.array([[x], [y], [0.0], [0.0], [r]], np.float32) # x, y, vx, vy, r
        return kf

    try:
        while True:
            if stop_event is not None and stop_event.is_set():
                break

            ret, frame = cap.read()
            if not ret:
                time.sleep(0.01)
                continue
            frame_idx += 1

            frame_h, frame_w = frame.shape[:2]
            x0 = int(roi[0] * frame_w)
            y0 = int(roi[1] * frame_h)
            x1 = int(roi[2] * frame_w)
            y1 = int(roi[3] * frame_h)
            x0 = max(0, min(frame_w, x0))
            x1 = max(0, min(frame_w, x1))
            y0 = max(0, min(frame_h, y0))
            y1 = max(0, min(frame_h, y1))

            roi_frame = frame[y0:y1, x0:x1]
            detections = detect_bubbles(roi_frame, min_area=min_area)
            for tid, t in tracks.items():
                t["pred_state"] = t["kf"].predict()

            matches, unmatched_tracks, unmatched_dets = match_tracks(tracks, detections)
            for tid, det_idx in matches:
                d = detections[det_idx]
                meas = np.array([[d["cx"]], [d["cy"]], [d["r"]]], np.float32)
                t = tracks[tid]
                t["kf"].correct(meas)
                t["misses"] = 0
                t["radius"] = 0.9 * t["radius"] + 0.1 * d["r"]
                t_color = np.array(t["color"])
                d_color = np.array(d["color"])
                t["color"] = tuple((0.9 * t_color + 0.1 * d_color).tolist())
                t["age"] += 1

            for tid in unmatched_tracks:
                tracks[tid]["misses"] += 1

            to_retire = [tid for tid, t in tracks.items() if t["misses"] > max_misses]
            for tid in to_retire:
                retired_tracks[tid] = tracks.pop(tid)

            for det_idx in unmatched_dets:
                d = detections[det_idx]
                revived = resurrect_from_retired(d, retired_tracks)
                if revived is not None:
                    tid, t = revived
                    t["kf"] = create_kalman(d["cx"], d["cy"], d["r"])
                    t["misses"] = 0
                    t["radius"] = d["r"]
                    t["color"] = d["color"]
                    t["age"] += 1
                    t["pred_state"] = t["kf"].predict()
                    meas = np.array([[d["cx"]], [d["cy"]], [d["r"]]], np.float32)
                    t["kf"].correct(meas)
                    tracks[tid] = t
                else:
                    kf = create_kalman(d["cx"], d["cy"], d["r"])
                    tracks[next_id] = {
                        "kf": kf,
                        "misses": 0,
                        "radius": d["r"],
                        "color": d["color"],
                        "age": 1,
                        "pred_state": kf.statePost.copy(),
                    }
                    next_id += 1

            readings: List[Dict] = []
            for tid, t in tracks.items():
                state = t["kf"].statePost
                cx, cy, vx, vy, r = [float(state[i, 0]) for i in range(5)]
                gx = cx + x0
                gy = cy + y0
                bbox = (int(gx - r), int(gy - r), int(2 * r), int(2 * r))

                readings.append({
                    "id": int(tid),
                    "cx": gx,
                    "cy": gy,
                    "r": r,
                    "diameter": 2 * r,
                    "vx": vx,
                    "vy": vy,
                    "bbox": bbox,
                    "color": t["color"],
                })

            yield (frame.copy(), roi_frame.copy(), readings)
    finally:
        cap.release()


def kalman_tracker_worker(
    output_q: queue.Queue,
    stop_event: threading.Event,
    source: SeleniumPortal = None,
    roi: Tuple[float, float, float, float] = (0, 0, 1, 1),
    max_misses: int = 60,
    min_area: float = 10.0,
    put_timeout: float = 0.02,
    show_window: bool = False,
):
    """
    threadable worker utilising a queue
    """
    if show_window:
        cv2.namedWindow("Tracker View", cv2.WINDOW_NORMAL)

    gen = kalman_tracker(
        source=source,
        roi=roi,
        max_misses=max_misses,
        min_area=min_area,
        stop_event=stop_event
    )

    try:
        for frame, roi, readings in gen:
            if stop_event.is_set():
                break
            try:
                output_q.put((frame, roi, readings), timeout=put_timeout)
            except queue.Full:
                try: # drop old item
                    _ = output_q.get_nowait()
                except queue.Empty:
                    pass
                output_q.put((frame, roi, readings), timeout=put_timeout)
            if show_window:
                vis = frame.copy()
                for r in readings:
                    cx, cy = int(r["cx"]), int(r["cy"])
                    cv2.circle(vis, (cx, cy), 6, (0, 255, 0), 2)
                    cv2.putText(vis, f'ID {r["id"]} d={r["diameter"]}', (cx + 8, cy - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                    x, y, w, h = map(int, r["bbox"])
                    cv2.rectangle(vis, (x, y), (x + w, y + h), (0, 0, 255), 2)
                    if hasattr(source, "_pos"):
                        cv2.circle(vis, source._pos, 3, (255, 0, 0), 2)

                cv2.imshow("Tracker View", vis)
                if cv2.waitKey(1) & 0xFF == 27:
                    stop_event.set()
                    break
            else:
                for r in readings:
                    print(f'ID {r["id"]} d={r["diameter"]} x={int(r["cx"])} y={int(r["cy"])}')
    finally:
        try:
            gen.close()
        except Exception:
            pass


if __name__ == "__main__":
    import sys

    portal = SeleniumPortal("http://127.0.0.1:5000/captcha")
    q: queue.Queue = queue.Queue(maxsize=1)
    stop_ev = threading.Event()
    worker = threading.Thread(
        target=kalman_tracker_worker,
        args=(q, stop_ev),
        kwargs={"source": portal, "roi": (0.0, 0.18, 1.0, 0.95), "max_misses": 60, "put_timeout": 0.02, "show_window": True},
        daemon=True,
    )
    worker.start()

    try:
        while True:
            try:
                frame, roi, readings = q.get(timeout=1.0)
            except queue.Empty:
                continue

    finally:
        stop_ev.set()
        worker.join(timeout=2.0)
        portal.release()
        cv2.destroyAllWindows()
        sys.exit(0)
