"""Causal M4 trigger samples, controls, and compact tick features."""
from __future__ import annotations

import numpy as np
import pandas as pd

WINDOWS_MS = (500, 1000, 2000, 5000, 10000, 30000, 60000)
PRIMARY_BEHAVIORS = {"REHEDGE_SELL", "REHEDGE_BUY", "UNLOCK_TO_BUY", "UNLOCK_TO_SELL"}

def control_state(behavior: str) -> str:
    return {"REHEDGE_SELL": "ONE_BUY", "REHEDGE_BUY": "ONE_SELL", "UNLOCK_TO_BUY": "HEDGED_1X1", "UNLOCK_TO_SELL": "HEDGED_1X1"}[behavior]

def trigger_family(behavior: str) -> str:
    return "rehedge" if behavior.startswith("REHEDGE") else "unlock"

def effective_event_times(aligned_events: pd.DataFrame) -> pd.Series:
    """Use tick-matched time when available, then fall back to the reported event time."""
    result = pd.to_datetime(aligned_events.matched_timestamp)
    for fallback in ("reported_time", "event_time"):
        if fallback in aligned_events:
            result = result.fillna(pd.to_datetime(aligned_events[fallback]))
    return result.dropna()

def select_positives(aligned: pd.DataFrame) -> pd.DataFrame:
    result = aligned[aligned.is_primary_trigger_sample & aligned.behavior_type.isin(PRIMARY_BEHAVIORS)].copy()
    result["sample_id"] = "p-" + result.event_id.astype(str)
    result["sample_type"] = "positive"; result["matched_event_id"] = result.event_id
    result["sample_time"] = result.matched_timestamp; result["trigger_family"] = result.behavior_type.map(trigger_family)
    result["required_state"] = result.behavior_type.map(control_state); result["control_sampling_reason"] = None; result["control_distance_seconds"] = 0.0
    return result[
        [
            "sample_id",
            "sample_type",
            "matched_event_id",
            "sample_time",
            "behavior_type",
            "trigger_family",
            "required_state",
            "volume",
            "control_sampling_reason",
            "control_distance_seconds",
        ]
    ].reset_index(drop=True)

def _interval_volume(row) -> float | None:
    if row.state == "ONE_BUY": return row.buy_volume
    if row.state == "ONE_SELL": return row.sell_volume
    if row.state == "HEDGED_1X1" and row.buy_volume == row.sell_volume: return row.buy_volume
    return None

def build_control_pool(intervals: pd.DataFrame, ticks: pd.DataFrame, event_times: pd.Series, exclusion_seconds: float = 3.0) -> pd.DataFrame:
    tick_ns = ticks.timestamp.map(lambda value: value.value).to_numpy(); event_ns = np.sort(pd.to_datetime(event_times).map(lambda value: value.value).to_numpy())
    rows = []
    for row in intervals.itertuples():
        volume = _interval_volume(row)
        if row.state not in {"ONE_BUY", "ONE_SELL", "HEDGED_1X1"} or volume != 0.3: continue
        start = max(pd.Timestamp(row.start_time).ceil("s"), ticks.timestamp.min()); end = min(pd.Timestamp(row.end_time).floor("s"), ticks.timestamp.max())
        if end <= start: continue
        for candidate in pd.date_range(start, end, freq="1s", inclusive="neither"):
            candidate_ns = candidate.value; location = np.searchsorted(event_ns, candidate_ns)
            nearest = []
            if location < len(event_ns): nearest.append(abs(event_ns[location] - candidate_ns))
            if location: nearest.append(abs(event_ns[location - 1] - candidate_ns))
            if nearest and min(nearest) <= exclusion_seconds * 1_000_000_000: continue
            tick_index = np.searchsorted(tick_ns, candidate_ns, side="right") - 1
            if tick_index < 0: continue
            actual = ticks.iloc[tick_index].timestamp
            actual_ns = actual.value
            actual_location = np.searchsorted(event_ns, actual_ns)
            actual_nearest = []
            if actual_location < len(event_ns):
                actual_nearest.append(abs(event_ns[actual_location] - actual_ns))
            if actual_location:
                actual_nearest.append(abs(event_ns[actual_location - 1] - actual_ns))
            if actual_nearest and min(actual_nearest) <= exclusion_seconds * 1_000_000_000:
                continue
            if actual <= row.start_time or actual >= row.end_time:
                continue
            rows.append({"interval_id": row.interval_id, "sample_time": actual, "required_state": row.state, "volume": volume, "state_age_seconds": (actual - row.start_time).total_seconds(), "date": str(actual.date()), "hour": actual.hour})
    return pd.DataFrame(rows).drop_duplicates(["interval_id", "sample_time"]).reset_index(drop=True)

def sample_controls(positives: pd.DataFrame, pool: pd.DataFrame, quota: int = 5) -> pd.DataFrame:
    controls = []
    used_candidates: set[tuple[object, pd.Timestamp]] = set()
    ordered_positives = positives.sort_values(["sample_time", "matched_event_id"], kind="stable")
    for positive in ordered_positives.itertuples():
        eligible = pool[
            (pool.required_state == positive.required_state)
            & (pool.date == str(positive.sample_time.date()))
            & (pool.hour == positive.sample_time.hour)
        ]
        if used_candidates:
            candidate_keys = pd.Series(
                list(zip(eligible.interval_id, eligible.sample_time)),
                index=eligible.index,
            )
            eligible = eligible[~candidate_keys.isin(used_candidates)]
        if eligible.empty: continue
        rng = np.random.default_rng(int(positive.matched_event_id))
        chosen = eligible.iloc[
            np.sort(rng.choice(len(eligible), size=min(quota, len(eligible)), replace=False))
        ]
        for number, row in enumerate(chosen.itertuples(), 1):
            used_candidates.add((row.interval_id, row.sample_time))
            controls.append({"sample_id": f"c-{positive.matched_event_id}-{number}", "sample_type": "control", "matched_event_id": positive.matched_event_id, "sample_time": row.sample_time, "behavior_type": positive.behavior_type, "trigger_family": positive.trigger_family, "required_state": positive.required_state, "volume": row.volume, "state_age_seconds": row.state_age_seconds, "control_sampling_reason": "same_date_state_hour_volume_risk_set", "control_distance_seconds": abs((row.sample_time - positive.sample_time).total_seconds()), "interval_id": row.interval_id})
    return pd.DataFrame(controls)

class TickFeatureEngine:
    def __init__(self, ticks: pd.DataFrame):
        ordered = ticks.sort_values("timestamp", kind="stable").reset_index(drop=True)
        self.timestamps = ordered.timestamp
        self.ns = ordered.timestamp.map(lambda value: value.value).to_numpy()
        self.mid = ordered.mid.to_numpy()
        self.spread = ordered.spread.to_numpy()

    def features_at(self, timestamp: pd.Timestamp, window_ms: int) -> dict:
        end = np.searchsorted(self.ns, timestamp.value, side="right")
        start_time = timestamp.value - window_ms * 1_000_000; start = np.searchsorted(self.ns, start_time, side="left")
        valid = bool(end > start and start_time >= self.ns[0] and end - start >= 2)
        prefix = f"w{window_ms}ms_"
        if not valid: return {prefix + "valid": False}
        mid = self.mid[start:end]
        current = mid[-1]; high, low = mid.max(), mid.min(); width = high - low; changes = np.diff(mid)
        high_index, low_index = np.flatnonzero(mid == high)[-1], np.flatnonzero(mid == low)[-1]
        return {prefix + "valid": True, prefix + "rolling_high": float(high), prefix + "rolling_low": float(low), prefix + "range_width": float(width), prefix + "range_position": float((current - low) / width) if width else 0.5, prefix + "distance_from_high": float(high - current), prefix + "distance_from_low": float(current - low), prefix + "time_since_high_ms": float((self.ns[end - 1] - self.ns[start + high_index]) / 1_000_000), prefix + "time_since_low_ms": float((self.ns[end - 1] - self.ns[start + low_index]) / 1_000_000), prefix + "retracement_from_high": float(high - current), prefix + "bounce_from_low": float(current - low), prefix + "mid_return": float(current / mid[0] - 1), prefix + "tick_count": int(len(mid)), prefix + "uptick_count": int((changes > 0).sum()), prefix + "downtick_count": int((changes < 0).sum()), prefix + "tick_imbalance": float(((changes > 0).sum() - (changes < 0).sum()) / max(1, len(changes))), prefix + "realized_range": float(width), prefix + "realized_volatility": float(np.sqrt(np.square(changes).sum())), prefix + "spread": float(self.spread[end - 1])}

def engineer_features(samples: pd.DataFrame, ticks: pd.DataFrame, intervals: pd.DataFrame, aligned_events: pd.DataFrame) -> pd.DataFrame:
    engine = TickFeatureEngine(ticks); previous_events = np.sort(effective_event_times(aligned_events).map(lambda value: value.value).to_numpy()); output = []
    for sample in samples.itertuples():
        metadata = (
            "sample_id",
            "sample_type",
            "matched_event_id",
            "sample_time",
            "behavior_type",
            "trigger_family",
            "required_state",
            "volume",
            "state_age_seconds",
            "control_sampling_reason",
            "control_distance_seconds",
            "interval_id",
            "date_split",
        )
        row = {name: getattr(sample, name, None) for name in metadata}
        timestamp = pd.Timestamp(sample.sample_time)
        location = np.searchsorted(previous_events, timestamp.value, side="left")
        row["time_since_previous_event_seconds"] = float((timestamp.value - previous_events[location - 1]) / 1e9) if location else None
        if not hasattr(sample, "state_age_seconds") or pd.isna(getattr(sample, "state_age_seconds", None)):
            candidates = intervals[(intervals.start_time <= timestamp) & (intervals.end_time >= timestamp) & (intervals.state == sample.required_state)]
            row["state_age_seconds"] = float((timestamp - candidates.iloc[-1].start_time).total_seconds()) if len(candidates) else None
        for window in WINDOWS_MS: row.update(engine.features_at(timestamp, window))
        output.append(row)
    return pd.DataFrame(output)

def expected_feature(frame: pd.DataFrame, window_ms: int, hypothesis: str) -> pd.Series:
    prefix = f"w{window_ms}ms_"
    if hypothesis == "h1": return np.where(frame.behavior_type == "REHEDGE_SELL", frame[prefix + "range_position"], 1 - frame[prefix + "range_position"])
    if hypothesis == "h2": return np.where(frame.behavior_type == "REHEDGE_SELL", frame[prefix + "retracement_from_high"] / frame[prefix + "range_width"].replace(0, np.nan), frame[prefix + "bounce_from_low"] / frame[prefix + "range_width"].replace(0, np.nan))
    return np.where(frame.behavior_type == "UNLOCK_TO_BUY", frame[prefix + "mid_return"], -frame[prefix + "mid_return"])

def paired_summary(frame: pd.DataFrame, window_ms: int, hypothesis: str, seed: int = 20260725) -> dict:
    valid = frame[frame[f"w{window_ms}ms_valid"]].copy(); valid["score"] = expected_feature(valid, window_ms, hypothesis)
    positives = valid[valid.sample_type == "positive"][["matched_event_id", "score", "date_split"]].rename(columns={"score": "positive_score"})
    controls = valid[valid.sample_type == "control"].groupby("matched_event_id").score.mean().rename("control_score")
    paired = positives.join(controls, on="matched_event_id").dropna(); paired["difference"] = paired.positive_score - paired.control_score
    rng = np.random.default_rng(seed + window_ms); boot = []
    values = paired.difference.to_numpy()
    if len(values):
        for _ in range(500): boot.append(float(rng.choice(values, size=len(values), replace=True).mean()))
    return {
        "pairs": len(paired),
        "positive_median": float(paired.positive_score.median()) if len(paired) else None,
        "control_median": float(paired.control_score.median()) if len(paired) else None,
        "paired_mean_difference": float(paired.difference.mean()) if len(paired) else None,
        "matched_separation_rate": float((paired.difference > 0).mean()) if len(paired) else None,
        "cluster_bootstrap_ci95": [
            float(np.quantile(boot, .025)),
            float(np.quantile(boot, .975)),
        ] if boot else None,
    }
