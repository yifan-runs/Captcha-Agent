import cv2
import numpy as np
import math
import queue
import threading
import time
from typing import Tuple, List, Dict, Generator, Optional

def kalman_tracker(
    source: int = 1,
    roi: Tuple[float, float, float, float] = (0, 0, 1, 1),
    bg_history: int = 1000,
    varThreshold: int = 50,
    max_dist: float = 100.0,
    max_misses: int = 60,
    min_area: float = 150.0,
    confirm_frames: int = 2,
    merge_dist: float = 15.0,
    shadow_detection: bool = False,
    stop_event: Optional[threading.Event] = None,
    skip: int = 30,
) -> Generator[Tuple[np.ndarray, List[Dict]], None, None]:
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video source {source}")
    
    if any([not bool(x <= 1.0 and x >= 0.0) for x in roi]) or roi[0] > roi[2] or roi[1] > roi[3]:
        raise Exception(f"Invalid RoI {roi}")

    od = cv2.createBackgroundSubtractorMOG2(history=bg_history, varThreshold=varThreshold, detectShadows=shadow_detection)
    next_id = 0
    tracks = {}
    candidates = {}
    frame_idx = 0

    def create_kalman(x: float, y: float):
        kf = cv2.KalmanFilter(4, 2)
        kf.transitionMatrix = np.array([
            [1, 0, 1, 0],
            [0, 1, 0, 1],
            [0, 0, 1, 0],
            [0, 0, 0, 1]
        ], dtype=np.float32)
        kf.measurementMatrix = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0]
        ], dtype=np.float32)
        kf.processNoiseCov = np.eye(4, dtype=np.float32) * 1e-2
        kf.measurementNoiseCov = np.eye(2, dtype=np.float32) * 1e-1
        kf.errorCovPost = np.eye(4, dtype=np.float32)
        kf.statePost = np.array([[x], [y], [0], [0]], dtype=np.float32)
        return kf

    try:
        count = 0
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
            fg = od.apply(roi_frame)
            fg_blur = cv2.GaussianBlur(fg, (5, 5), 0)
            _, mask_bin = cv2.threshold(fg_blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            mask_closed = cv2.morphologyEx(mask_bin, cv2.MORPH_CLOSE, kernel, iterations=1)
            mask_clean = cv2.morphologyEx(mask_closed, cv2.MORPH_OPEN, kernel, iterations=1)
            contours, _ = cv2.findContours(mask_clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            raw_detections = []
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area < min_area:
                    continue

                x, y, w, h = cv2.boundingRect(cnt)
                cx = x + w // 2
                cy = y + h // 2

                peri = cv2.arcLength(cnt, True)
                if peri <= 0:
                    continue
                circularity = 4.0 * math.pi * area / (peri * peri)
                if circularity < 0.35:
                    if area < (min_area * 2) or circularity < 0.18:
                        continue

                aspect = w / float(h) if h > 0 else 1.0
                if aspect < 0.4 or aspect > 2.5:
                    continue

                raw_detections.append((cx, cy, x, y, w, h))

            detections = []
            used = [False] * len(raw_detections)
            for i, (cxi, cyi, xi, yi, wi, hi) in enumerate(raw_detections):
                if used[i]:
                    continue
                sx, sy, sw, sh = xi, yi, wi, hi
                cx_sum, cy_sum, cnt_n = cxi, cyi, 1
                used[i] = True
                for j in range(i + 1, len(raw_detections)):
                    if used[j]:
                        continue
                    cxj, cyj, xj, yj, wj, hj = raw_detections[j]
                    if math.hypot(cxi - cxj, cyi - cyj) <= merge_dist:
                        used[j] = True
                        cx_sum += cxj
                        cy_sum += cyj
                        cnt_n += 1
                        sx = min(sx, xj)
                        sy = min(sy, yj)
                        sw = max(sx + sw, xj + wj) - sx
                        sh = max(sy + sh, yj + hj) - sy
                avg_cx = int(round(cx_sum / cnt_n))
                avg_cy = int(round(cy_sum / cnt_n))
                detections.append((avg_cx, avg_cy, sx, sy, sw, sh))

            predictions = {}
            for tid, t in tracks.items():
                pred = t["kf"].predict()
                px, py = float(pred[0, 0]), float(pred[1, 0])
                predictions[tid] = (px, py)

            unmatched_dets = set(range(len(detections)))
            unmatched_tracks = set(tracks.keys())
            matches = []
            for det_idx, (cx, cy, x, y, w, h) in enumerate(detections):
                best_tid = None
                best_d = max_dist
                for tid in list(unmatched_tracks):
                    px, py = predictions[tid]
                    d = math.hypot(cx - px, cy - py)
                    if d < best_d:
                        best_d = d
                        best_tid = tid
                if best_tid is not None:
                    matches.append((best_tid, det_idx))
                    unmatched_tracks.discard(best_tid)
                    unmatched_dets.discard(det_idx)

            for tid, det_idx in matches:
                cx, cy, x, y, w, h = detections[det_idx]
                meas = np.array([[cx], [cy]], dtype=np.float32)
                tracks[tid]["kf"].correct(meas)
                tracks[tid]["misses"] = 0
                tracks[tid]["bbox"] = (int(x), int(y), int(w), int(h))

            for tid in unmatched_tracks:
                tracks[tid]["misses"] += 1

            for det_idx in list(unmatched_dets):
                cx, cy, x, y, w, h = detections[det_idx]
                near_existing = False
                for tid, (px, py) in predictions.items():
                    if math.hypot(cx - px, cy - py) < (max_dist * 0.35):
                        meas = np.array([[cx], [cy]], dtype=np.float32)
                        tracks[tid]["kf"].correct(meas)
                        tracks[tid]["misses"] = 0
                        tracks[tid]["bbox"] = (int(x), int(y), int(w), int(h))
                        near_existing = True
                        break
                if near_existing:
                    continue

                qx = int(round(cx / 8.0))
                qy = int(round(cy / 8.0))
                key = (qx, qy)
                entry = candidates.get(key)
                if entry and frame_idx - entry["last_seen"] <= 2:
                    entry["count"] += 1
                    entry["last_seen"] = frame_idx
                    ex, ey, ew, eh = entry["bbox"]
                    entry["bbox"] = (int((ex + x) / 2), int((ey + y) / 2), int((ew + w) / 2), int((eh + h) / 2))
                else:
                    candidates[key] = {"count": 1, "last_seen": frame_idx, "bbox": (x, y, w, h), "cx": cx, "cy": cy}

            to_promote = []
            for key, entry in list(candidates.items()):
                if frame_idx - entry["last_seen"] > 3:
                    del candidates[key]
                    continue
                if entry["count"] >= confirm_frames:
                    cx = entry["cx"]
                    cy = entry["cy"]
                    x, y, w, h = entry["bbox"]
                    kf = create_kalman(float(cx), float(cy))
                    tracks[next_id] = {"kf": kf, "misses": 0, "bbox": (int(x), int(y), int(w), int(h))}
                    to_promote.append(next_id)
                    next_id += 1
                    del candidates[key]

            to_delete = [tid for tid, t in list(tracks.items()) if t["misses"] > max_misses]
            for tid in to_delete:
                del tracks[tid]

            readings = []
            for tid, t in tracks.items():
                state = t["kf"].statePost
                cx = float(state[0, 0])
                cy = float(state[1, 0])
                bbox = t.get("bbox")

                readings.append({
                    "id": int(tid),
                    "cx": cx + x0,
                    "cy": cy + y0,
                    "bbox": bbox,
                })
            if count > skip:
                yield (frame.copy(), roi_frame.copy(), readings)
            count += 1

    finally:
        cap.release()

def kalman_tracker_worker(
    output_q: queue.Queue[Tuple[np.ndarray, List[Dict]]],
    stop_event: threading.Event,
    source: int = 1,
    roi: Tuple[float, float, float, float] = (0, 0, 1, 1),
    bg_history: int = 1000,
    varThreshold: int = 50,
    max_dist: float = 100.0,
    max_misses: int = 60,
    min_area: float = 10.0,
    put_timeout: float = 0.02,
):
    """
    threadable worker utilising a queue
    """
    gen = kalman_tracker(
        source=source,
        roi=roi,
        bg_history=bg_history,
        varThreshold=varThreshold,
        max_dist=max_dist,
        max_misses=max_misses,
        min_area=min_area,
        stop_event=stop_event,
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
    finally:
        try:
            gen.close()
        except Exception:
            pass


if __name__ == "__main__":
    import sys

    q: queue.Queue[Tuple[np.ndarray, List[Dict]]] = queue.Queue(maxsize=1)
    stop_ev = threading.Event()
    worker = threading.Thread(
        target=kalman_tracker_worker,
        args=(q, stop_ev),
        kwargs={"source": 1, "roi": (0.025, 0.15, 0.975, 0.66), "max_dist": 150, "max_misses": 60, "put_timeout": 0.02},
        daemon=True,
    )
    worker.start()

    try:
        while True:
            try:
                frame, roi, readings = q.get(timeout=1.0)
            except queue.Empty:
                continue

            for r in readings:
                cx, cy = int(r["cx"]), int(r["cy"])
                cv2.circle(frame, (cx, cy), 6, (0, 255, 0), 2)
                cv2.putText(frame, f'ID {r["id"]}', (cx + 8, cy - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

            cv2.imshow("Tracker View", frame)
            if cv2.waitKey(1) & 0xFF == 27:
                break

    finally:
        stop_ev.set()
        worker.join(timeout=2.0)
        cv2.destroyAllWindows()
        sys.exit(0)
