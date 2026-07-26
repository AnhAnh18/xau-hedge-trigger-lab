"""Causal M4 trigger samples, controls, and reviewed model features."""
from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

WINDOWS_MS = (500, 1000, 2000, 5000, 10000, 30000, 60000)
H1_WINDOWS_MS = (2000, 5000, 10000, 30000, 60000)
H2_WINDOWS_MS = (1000, 2000, 5000)
H3_WINDOWS_MS = (500, 1000, 2000)
BOOTSTRAP_DRAWS = 5000
CONTROL_SUPPORT_MIN_STATE_AGE_SECONDS = 7.0
MODEL_STATE_AGE_CLIP_SECONDS = 60.0
H2_RETRACEMENT_WINSOR_QUANTILE = 0.99
PRIMARY_BEHAVIORS = {
    "REHEDGE_SELL",
    "REHEDGE_BUY",
    "UNLOCK_TO_BUY",
    "UNLOCK_TO_SELL",
}

MODEL_ID_COLUMNS = (
    "matched_event_id",
)
MODEL_TARGET_COLUMNS = ("sample_type",)
MODEL_CONTEXT_COLUMNS = (
    "behavior_type",
    "trigger_family",
    "date_split",
)
MODEL_BASE_PREDICTOR_COLUMNS = (
    "state_age_pretransition_seconds_clipped_60s",
)
MARKET_FEATURE_SUFFIXES = (
    "valid",
    "range_width",
    "range_position",
    "distance_from_high",
    "distance_from_low",
    "time_since_high_ms",
    "time_since_low_ms",
    "mid_return",
    "tick_count",
    "uptick_count",
    "downtick_count",
    "tick_imbalance",
    "realized_volatility",
    "spread",
)
H2_FEATURE_SUFFIXES = (
    "valid",
    "high_touched_before_event",
    "low_touched_before_event",
    "high_touch_lead_ms",
    "low_touch_lead_ms",
    "high_breach_fraction",
    "low_breach_fraction",
    "retracement_after_high_fraction_winsorized",
    "bounce_after_low_fraction_winsorized",
    "high_sequence_complete",
    "low_sequence_complete",
)

AUDIT_BASE_COLUMNS = (
    "sample_id",
    "sample_type",
    "matched_event_id",
    "behavior_type",
    "trigger_family",
    "required_state",
    "volume",
    "reported_time",
    "price_anchor_time",
    "state_anchor_time",
    "pretransition_interval_id",
    "state_lineage_source",
    "state_age_pretransition_seconds",
    "state_age_stratum",
    "eligible_control_count",
    "is_control_supported",
    "control_support_reason",
    "actual_control_count",
    "matched_positive_state_age_seconds",
    "matched_positive_state_age_stratum",
    "control_sampling_reason",
    "control_distance_seconds",
    "date_split",
    "match_quality",
    "match_tier",
    "time_error_ms",
    "price_error",
    "time_since_previous_event_seconds",
)


def control_state(behavior: str) -> str:
    return {
        "REHEDGE_SELL": "ONE_BUY",
        "REHEDGE_BUY": "ONE_SELL",
        "UNLOCK_TO_BUY": "HEDGED_1X1",
        "UNLOCK_TO_SELL": "HEDGED_1X1",
    }[behavior]


def trigger_family(behavior: str) -> str:
    return "rehedge" if behavior.startswith("REHEDGE") else "unlock"


def effective_event_times(aligned_events: pd.DataFrame) -> pd.Series:
    """Prefer tick-matched time and fall back to the second-resolution report time."""
    result = pd.to_datetime(aligned_events.matched_timestamp)
    for fallback in ("reported_time", "event_time"):
        if fallback in aligned_events:
            result = result.fillna(pd.to_datetime(aligned_events[fallback]))
    return result.dropna()


def state_age_stratum(age_seconds: float | int | None) -> str | None:
    if age_seconds is None or pd.isna(age_seconds):
        return None
    age = float(age_seconds)
    if age <= 6:
        return "0-6s"
    if age <= 10:
        return "7-10s"
    if age <= 30:
        return "10-30s"
    if age <= 60:
        return "30-60s"
    return ">60s"


def select_positives(aligned: pd.DataFrame) -> pd.DataFrame:
    result = aligned[
        aligned.is_primary_trigger_sample
        & aligned.behavior_type.isin(PRIMARY_BEHAVIORS)
    ].copy()
    result["sample_id"] = "p-" + result.event_id.astype(str)
    result["sample_type"] = "positive"
    result["matched_event_id"] = result.event_id
    result["price_anchor_time"] = result.matched_timestamp
    result["sample_time"] = result.price_anchor_time
    result["state_anchor_time"] = result.reported_time
    result["trigger_family"] = result.behavior_type.map(trigger_family)
    result["required_state"] = result.behavior_type.map(control_state)
    result["control_sampling_reason"] = None
    result["control_distance_seconds"] = 0.0
    columns = [
        "sample_id",
        "sample_type",
        "matched_event_id",
        "sample_time",
        "price_anchor_time",
        "state_anchor_time",
        "reported_time",
        "behavior_type",
        "trigger_family",
        "required_state",
        "volume",
        "control_sampling_reason",
        "control_distance_seconds",
        "match_quality",
        "match_tier",
        "time_error_ms",
        "price_error",
    ]
    return result[columns].reset_index(drop=True)


def attach_pretransition_state(
    positives: pd.DataFrame,
    intervals: pd.DataFrame,
) -> pd.DataFrame:
    """Attach the M2 interval that ends at each event, with reported-time fallback."""
    output = positives.copy()
    interval_ids: list[object] = []
    ages: list[float] = []
    sources: list[str] = []
    for positive in output.itertuples():
        anchor = pd.Timestamp(positive.state_anchor_time)
        candidates = intervals[
            (intervals.end_time == anchor)
            & (intervals.state == positive.required_state)
            & (intervals.following_event_type == positive.behavior_type)
        ]
        source = "m2_interval_lineage"
        if len(candidates) != 1:
            candidates = intervals[
                (intervals.start_time <= anchor)
                & (intervals.end_time >= anchor)
                & (intervals.state == positive.required_state)
            ]
            source = "reported_time_interval_fallback"
        if candidates.empty:
            raise RuntimeError(
                f"No pre-transition interval for event {positive.matched_event_id}"
            )
        interval = candidates.iloc[-1]
        interval_ids.append(interval.interval_id)
        ages.append(float((anchor - interval.start_time).total_seconds()))
        sources.append(source)
    output["pretransition_interval_id"] = interval_ids
    output["state_age_pretransition_seconds"] = ages
    output["state_lineage_source"] = sources
    output["state_age_stratum"] = output.state_age_pretransition_seconds.map(
        state_age_stratum
    )
    output["matched_positive_state_age_seconds"] = (
        output.state_age_pretransition_seconds
    )
    output["matched_positive_state_age_stratum"] = output.state_age_stratum
    return output


def _interval_volume(row: object) -> float | None:
    if row.state == "ONE_BUY":
        return row.buy_volume
    if row.state == "ONE_SELL":
        return row.sell_volume
    if row.state == "HEDGED_1X1" and row.buy_volume == row.sell_volume:
        return row.buy_volume
    return None


def _nearest_distance_ns(sorted_ns: np.ndarray, value_ns: int) -> int | None:
    if not len(sorted_ns):
        return None
    location = np.searchsorted(sorted_ns, value_ns)
    distances = []
    if location < len(sorted_ns):
        distances.append(abs(int(sorted_ns[location]) - value_ns))
    if location:
        distances.append(abs(int(sorted_ns[location - 1]) - value_ns))
    return min(distances)


def build_control_pool(
    intervals: pd.DataFrame,
    ticks: pd.DataFrame,
    event_times: pd.Series,
    exclusion_seconds: float = 3.0,
) -> pd.DataFrame:
    ordered_ticks = ticks.sort_values("timestamp", kind="stable").reset_index(drop=True)
    tick_ns = ordered_ticks.timestamp.map(lambda value: value.value).to_numpy()
    event_ns = np.sort(
        pd.to_datetime(event_times).map(lambda value: value.value).to_numpy()
    )
    exclusion_ns = int(exclusion_seconds * 1_000_000_000)
    rows = []
    for interval in intervals.itertuples():
        volume = _interval_volume(interval)
        if (
            interval.state not in {"ONE_BUY", "ONE_SELL", "HEDGED_1X1"}
            or volume != 0.3
        ):
            continue
        start = max(
            pd.Timestamp(interval.start_time).ceil("s"),
            ordered_ticks.timestamp.min(),
        )
        end = min(
            pd.Timestamp(interval.end_time).floor("s"),
            ordered_ticks.timestamp.max(),
        )
        if end <= start:
            continue
        for candidate in pd.date_range(start, end, freq="1s", inclusive="neither"):
            candidate_distance = _nearest_distance_ns(event_ns, candidate.value)
            if candidate_distance is not None and candidate_distance <= exclusion_ns:
                continue
            tick_index = np.searchsorted(tick_ns, candidate.value, side="right") - 1
            if tick_index < 0:
                continue
            actual = ordered_ticks.iloc[tick_index].timestamp
            actual_distance = _nearest_distance_ns(event_ns, actual.value)
            if actual_distance is not None and actual_distance <= exclusion_ns:
                continue
            if actual <= interval.start_time or actual >= interval.end_time:
                continue
            age = float((actual - interval.start_time).total_seconds())
            rows.append(
                {
                    "pretransition_interval_id": interval.interval_id,
                    "sample_time": actual,
                    "price_anchor_time": actual,
                    "state_anchor_time": actual,
                    "required_state": interval.state,
                    "volume": volume,
                    "state_age_pretransition_seconds": age,
                    "state_age_stratum": state_age_stratum(age),
                    "state_lineage_source": "m2_interval_membership",
                    "date": str(actual.date()),
                    "hour": actual.hour,
                }
            )
    columns = [
        "pretransition_interval_id",
        "sample_time",
        "price_anchor_time",
        "state_anchor_time",
        "required_state",
        "volume",
        "state_age_pretransition_seconds",
        "state_age_stratum",
        "state_lineage_source",
        "date",
        "hour",
    ]
    if not rows:
        return pd.DataFrame(columns=columns)
    return (
        pd.DataFrame(rows, columns=columns)
        .drop_duplicates(["pretransition_interval_id", "sample_time"])
        .reset_index(drop=True)
    )


def annotate_control_support(
    positives: pd.DataFrame,
    pool: pd.DataFrame,
) -> pd.DataFrame:
    output = positives.copy()
    pool_counts = (
        pool.groupby(["required_state", "date", "hour"])
        .size()
        .rename("eligible_control_count")
    )
    keys = pd.MultiIndex.from_arrays(
        [
            output.required_state,
            output.sample_time.dt.date.astype(str),
            output.sample_time.dt.hour,
        ],
        names=["required_state", "date", "hour"],
    )
    output["eligible_control_count"] = (
        pool_counts.reindex(keys).fillna(0).astype(int).to_numpy()
    )
    old_enough = (
        output.state_age_pretransition_seconds
        >= CONTROL_SUPPORT_MIN_STATE_AGE_SECONDS
    )
    output["is_control_supported"] = old_enough & (
        output.eligible_control_count > 0
    )
    output["control_support_reason"] = np.select(
        [
            ~old_enough,
            output.eligible_control_count.eq(0),
        ],
        [
            "state_age_below_7s",
            "no_eligible_risk_time",
        ],
        default="supported",
    )
    return output


def sample_controls(
    positives: pd.DataFrame,
    pool: pd.DataFrame,
    quota: int = 5,
) -> pd.DataFrame:
    controls = []
    used_candidates: set[tuple[object, pd.Timestamp]] = set()
    ordered_positives = positives.sort_values(
        ["sample_time", "matched_event_id"],
        kind="stable",
    )
    for positive in ordered_positives.itertuples():
        eligible = pool[
            (pool.required_state == positive.required_state)
            & (pool.date == str(positive.sample_time.date()))
            & (pool.hour == positive.sample_time.hour)
        ]
        if used_candidates:
            candidate_keys = pd.Series(
                list(
                    zip(
                        eligible.pretransition_interval_id,
                        eligible.sample_time,
                    )
                ),
                index=eligible.index,
            )
            eligible = eligible[~candidate_keys.isin(used_candidates)]
        if eligible.empty:
            continue
        rng = np.random.default_rng(int(positive.matched_event_id))
        chosen = eligible.iloc[
            np.sort(
                rng.choice(
                    len(eligible),
                    size=min(quota, len(eligible)),
                    replace=False,
                )
            )
        ]
        for number, candidate in enumerate(chosen.itertuples(), 1):
            key = (candidate.pretransition_interval_id, candidate.sample_time)
            used_candidates.add(key)
            controls.append(
                {
                    "sample_id": f"c-{positive.matched_event_id}-{number}",
                    "sample_type": "control",
                    "matched_event_id": positive.matched_event_id,
                    "sample_time": candidate.sample_time,
                    "price_anchor_time": candidate.price_anchor_time,
                    "state_anchor_time": candidate.state_anchor_time,
                    "reported_time": pd.NaT,
                    "behavior_type": positive.behavior_type,
                    "trigger_family": positive.trigger_family,
                    "required_state": positive.required_state,
                    "volume": candidate.volume,
                    "pretransition_interval_id": (
                        candidate.pretransition_interval_id
                    ),
                    "state_lineage_source": candidate.state_lineage_source,
                    "state_age_pretransition_seconds": (
                        candidate.state_age_pretransition_seconds
                    ),
                    "state_age_stratum": candidate.state_age_stratum,
                    "matched_positive_state_age_seconds": (
                        positive.state_age_pretransition_seconds
                    ),
                    "matched_positive_state_age_stratum": (
                        positive.state_age_stratum
                    ),
                    "eligible_control_count": positive.eligible_control_count,
                    "is_control_supported": positive.is_control_supported,
                    "control_support_reason": positive.control_support_reason,
                    "control_sampling_reason": (
                        "same_date_state_hour_volume_risk_set"
                    ),
                    "control_distance_seconds": abs(
                        (candidate.sample_time - positive.sample_time).total_seconds()
                    ),
                    "match_quality": None,
                    "match_tier": None,
                    "time_error_ms": np.nan,
                    "price_error": np.nan,
                }
            )
    return pd.DataFrame(controls)


def attach_actual_control_counts(
    positives: pd.DataFrame,
    controls: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    counts = controls.groupby("matched_event_id").size()
    positive_output = positives.copy()
    control_output = controls.copy()
    positive_output["actual_control_count"] = (
        positive_output.matched_event_id.map(counts).fillna(0).astype(int)
    )
    control_output["actual_control_count"] = (
        control_output.matched_event_id.map(counts).fillna(0).astype(int)
    )
    return positive_output, control_output


class TickFeatureEngine:
    def __init__(self, ticks: pd.DataFrame):
        ordered = ticks.sort_values("timestamp", kind="stable").reset_index(drop=True)
        self.ns = ordered.timestamp.map(lambda value: value.value).to_numpy()
        self.mid = ordered.mid.to_numpy()
        self.spread = ordered.spread.to_numpy()

    def features_at(self, timestamp: pd.Timestamp, window_ms: int) -> dict:
        end = np.searchsorted(self.ns, timestamp.value, side="right")
        start_time = timestamp.value - window_ms * 1_000_000
        start = np.searchsorted(self.ns, start_time, side="left")
        valid = bool(
            end > start
            and start_time >= self.ns[0]
            and end - start >= 2
        )
        prefix = f"w{window_ms}ms_"
        if not valid:
            return {prefix + "valid": False}
        mid = self.mid[start:end]
        current = mid[-1]
        high = mid.max()
        low = mid.min()
        width = high - low
        changes = np.diff(mid)
        high_index = np.flatnonzero(mid == high)[-1]
        low_index = np.flatnonzero(mid == low)[-1]
        return {
            prefix + "valid": True,
            prefix + "rolling_high": float(high),
            prefix + "rolling_low": float(low),
            prefix + "range_width": float(width),
            prefix + "range_position": (
                float((current - low) / width) if width else 0.5
            ),
            prefix + "distance_from_high": float(high - current),
            prefix + "distance_from_low": float(current - low),
            prefix + "time_since_high_ms": float(
                (self.ns[end - 1] - self.ns[start + high_index]) / 1_000_000
            ),
            prefix + "time_since_low_ms": float(
                (self.ns[end - 1] - self.ns[start + low_index]) / 1_000_000
            ),
            prefix + "mid_return": float(current / mid[0] - 1),
            prefix + "tick_count": int(len(mid)),
            prefix + "uptick_count": int((changes > 0).sum()),
            prefix + "downtick_count": int((changes < 0).sum()),
            prefix + "tick_imbalance": float(
                ((changes > 0).sum() - (changes < 0).sum())
                / max(1, len(changes))
            ),
            prefix + "realized_volatility": float(
                np.sqrt(np.square(changes).sum())
            ),
            prefix + "spread": float(self.spread[end - 1]),
        }

    def h2_sequence_features_at(
        self,
        timestamp: pd.Timestamp,
        sequence_window_ms: int,
    ) -> dict:
        prefix = f"h2_w{sequence_window_ms}ms_"
        window_ns = sequence_window_ms * 1_000_000
        boundary_start_ns = timestamp.value - 2 * window_ns
        sequence_start_ns = timestamp.value - window_ns
        boundary_start = np.searchsorted(self.ns, boundary_start_ns, side="left")
        boundary_end = np.searchsorted(self.ns, sequence_start_ns, side="left")
        sequence_start = np.searchsorted(self.ns, sequence_start_ns, side="left")
        sequence_end = np.searchsorted(self.ns, timestamp.value, side="right")
        valid = bool(
            boundary_start_ns >= self.ns[0]
            and boundary_end - boundary_start >= 2
            and sequence_end - sequence_start >= 2
        )
        if not valid:
            return {prefix + "valid": False}

        prior = self.mid[boundary_start:boundary_end]
        sequence = self.mid[sequence_start:sequence_end]
        sequence_ns = self.ns[sequence_start:sequence_end]
        prior_high = float(prior.max())
        prior_low = float(prior.min())
        prior_range = prior_high - prior_low
        if prior_range <= 0:
            return {prefix + "valid": False}

        high_touch_indices = np.flatnonzero(sequence >= prior_high)
        low_touch_indices = np.flatnonzero(sequence <= prior_low)
        high_touched = bool(len(high_touch_indices))
        low_touched = bool(len(low_touch_indices))
        high_first = int(high_touch_indices[0]) if high_touched else None
        low_first = int(low_touch_indices[0]) if low_touched else None
        high_before = bool(
            high_touched and sequence_ns[high_first] < timestamp.value
        )
        low_before = bool(low_touched and sequence_ns[low_first] < timestamp.value)

        sequence_high = float(sequence.max())
        sequence_low = float(sequence.min())
        current = float(sequence[-1])
        high_retracement = (
            max(0.0, float(sequence[high_first:].max()) - current)
            if high_before
            else 0.0
        )
        low_bounce = (
            max(0.0, current - float(sequence[low_first:].min()))
            if low_before
            else 0.0
        )
        return {
            prefix + "valid": True,
            prefix + "prior_boundary_high": prior_high,
            prefix + "prior_boundary_low": prior_low,
            prefix + "prior_boundary_range": prior_range,
            prefix + "high_touched_before_event": high_before,
            prefix + "low_touched_before_event": low_before,
            prefix + "high_touch_lead_ms": (
                float((timestamp.value - sequence_ns[high_first]) / 1_000_000)
                if high_before
                else np.nan
            ),
            prefix + "low_touch_lead_ms": (
                float((timestamp.value - sequence_ns[low_first]) / 1_000_000)
                if low_before
                else np.nan
            ),
            prefix + "high_breach_fraction": (
                max(0.0, sequence_high - prior_high) / prior_range
            ),
            prefix + "low_breach_fraction": (
                max(0.0, prior_low - sequence_low) / prior_range
            ),
            prefix + "retracement_after_high_fraction": (
                high_retracement / prior_range
            ),
            prefix + "bounce_after_low_fraction": low_bounce / prior_range,
            prefix + "high_sequence_complete": bool(
                high_before and high_retracement > 0
            ),
            prefix + "low_sequence_complete": bool(
                low_before and low_bounce > 0
            ),
        }


def engineer_features(
    samples: pd.DataFrame,
    ticks: pd.DataFrame,
    aligned_events: pd.DataFrame,
) -> pd.DataFrame:
    engine = TickFeatureEngine(ticks)
    previous_events = np.sort(
        effective_event_times(aligned_events)
        .map(lambda value: value.value)
        .to_numpy()
    )
    output = []
    for sample in samples.itertuples():
        row = sample._asdict()
        timestamp = pd.Timestamp(sample.price_anchor_time)
        location = np.searchsorted(previous_events, timestamp.value, side="left")
        row["time_since_previous_event_seconds"] = (
            float((timestamp.value - previous_events[location - 1]) / 1e9)
            if location
            else None
        )
        for window in WINDOWS_MS:
            row.update(engine.features_at(timestamp, window))
        for window in H2_WINDOWS_MS:
            row.update(engine.h2_sequence_features_at(timestamp, window))
        output.append(row)
    return pd.DataFrame(output)


def expected_feature(
    frame: pd.DataFrame,
    window_ms: int,
    hypothesis: str,
) -> pd.Series:
    if hypothesis == "h1":
        prefix = f"w{window_ms}ms_"
        values = np.where(
            frame.behavior_type == "REHEDGE_SELL",
            frame[prefix + "range_position"],
            1 - frame[prefix + "range_position"],
        )
    elif hypothesis == "h2_touch":
        prefix = f"h2_w{window_ms}ms_"
        values = np.where(
            frame.behavior_type == "REHEDGE_SELL",
            frame[prefix + "high_touched_before_event"],
            frame[prefix + "low_touched_before_event"],
        )
    elif hypothesis in {"h2_retracement", "h2_retracement_raw"}:
        prefix = f"h2_w{window_ms}ms_"
        high_column = "retracement_after_high_fraction"
        low_column = "bounce_after_low_fraction"
        if hypothesis == "h2_retracement":
            winsorized_high = high_column + "_winsorized"
            winsorized_low = low_column + "_winsorized"
            if prefix + winsorized_high in frame:
                high_column = winsorized_high
                low_column = winsorized_low
        values = np.where(
            frame.behavior_type == "REHEDGE_SELL",
            frame[prefix + high_column],
            frame[prefix + low_column],
        )
    elif hypothesis == "h2":
        prefix = f"h2_w{window_ms}ms_"
        values = np.where(
            frame.behavior_type == "REHEDGE_SELL",
            frame[prefix + "high_sequence_complete"],
            frame[prefix + "low_sequence_complete"],
        )
    elif hypothesis == "h3":
        prefix = f"w{window_ms}ms_"
        values = np.where(
            frame.behavior_type == "UNLOCK_TO_BUY",
            frame[prefix + "mid_return"],
            -frame[prefix + "mid_return"],
        )
    else:
        raise ValueError(f"Unknown hypothesis: {hypothesis}")
    return pd.Series(values, index=frame.index, dtype=float)


def hypothesis_valid_column(hypothesis: str, window_ms: int) -> str:
    if hypothesis.startswith("h2"):
        return f"h2_w{window_ms}ms_valid"
    return f"w{window_ms}ms_valid"


def fit_h2_retracement_winsor_caps(
    engineered: pd.DataFrame,
    quantile: float = H2_RETRACEMENT_WINSOR_QUANTILE,
) -> dict[int, float]:
    development = engineered[
        (engineered.date_split == "development")
        & (engineered.trigger_family == "rehedge")
        & engineered.is_control_supported
    ]
    caps = {}
    for window in H2_WINDOWS_MS:
        valid = development[development[f"h2_w{window}ms_valid"]]
        raw = expected_feature(valid, window, "h2_retracement_raw").dropna()
        if raw.empty:
            raise RuntimeError(
                f"No development data for H2 retracement winsorization at {window} ms"
            )
        caps[window] = float(raw.quantile(quantile))
    return caps


def apply_reviewed_model_transforms(
    engineered: pd.DataFrame,
    h2_retracement_caps: dict[int, float],
) -> pd.DataFrame:
    output = engineered.copy()
    output["state_age_pretransition_seconds_clipped_60s"] = (
        output.state_age_pretransition_seconds.clip(
            lower=0,
            upper=MODEL_STATE_AGE_CLIP_SECONDS,
        )
    )
    for window, cap in h2_retracement_caps.items():
        prefix = f"h2_w{window}ms_"
        output[prefix + "retracement_after_high_fraction_winsorized"] = output[
            prefix + "retracement_after_high_fraction"
        ].clip(lower=0, upper=cap)
        output[prefix + "bounce_after_low_fraction_winsorized"] = output[
            prefix + "bounce_after_low_fraction"
        ].clip(lower=0, upper=cap)
    return output


def paired_summary(
    frame: pd.DataFrame,
    window_ms: int,
    hypothesis: str,
    seed: int = 20260725,
    bootstrap_draws: int = BOOTSTRAP_DRAWS,
) -> dict:
    valid_column = hypothesis_valid_column(hypothesis, window_ms)
    valid = frame[frame[valid_column]].copy()
    valid["score"] = expected_feature(valid, window_ms, hypothesis)
    positives = (
        valid[valid.sample_type == "positive"][
            ["matched_event_id", "score", "date_split"]
        ]
        .rename(columns={"score": "positive_score"})
        .dropna(subset=["positive_score"])
    )
    controls = (
        valid[valid.sample_type == "control"]
        .dropna(subset=["score"])
        .groupby("matched_event_id")
        .score.mean()
        .rename("control_score")
    )
    paired = positives.join(controls, on="matched_event_id").dropna()
    paired["difference"] = paired.positive_score - paired.control_score
    values = paired.difference.to_numpy()
    bootstrap_means = np.array([], dtype=float)
    if len(values):
        rng = np.random.default_rng(seed + window_ms)
        draw_indices = rng.integers(
            0,
            len(values),
            size=(bootstrap_draws, len(values)),
        )
        bootstrap_means = values[draw_indices].mean(axis=1)
    return {
        "pairs": len(paired),
        "bootstrap_draws": bootstrap_draws,
        "positive_median": (
            float(paired.positive_score.median()) if len(paired) else None
        ),
        "control_median": (
            float(paired.control_score.median()) if len(paired) else None
        ),
        "paired_mean_difference": (
            float(paired.difference.mean()) if len(paired) else None
        ),
        "matched_separation_rate": (
            float((paired.difference > 0).mean()) if len(paired) else None
        ),
        "cluster_bootstrap_ci95": (
            [
                float(np.quantile(bootstrap_means, 0.025)),
                float(np.quantile(bootstrap_means, 0.975)),
            ]
            if len(bootstrap_means)
            else None
        ),
    }


def coherent_conclusion(results: Iterable[dict]) -> str:
    ordered = sorted(results, key=lambda item: item["window_ms"])
    signs = []
    for item in ordered:
        summary = item["summary"]
        interval = summary["cluster_bootstrap_ci95"]
        if summary["pairs"] < 30 or not interval:
            signs.append(0)
        elif interval[0] > 0:
            signs.append(1)
        elif interval[1] < 0:
            signs.append(-1)
        else:
            signs.append(0)

    def longest_run(target: int) -> int:
        longest = current = 0
        for sign in signs:
            current = current + 1 if sign == target else 0
            longest = max(longest, current)
        return longest

    supported_run = longest_run(1)
    rejected_run = longest_run(-1)
    if supported_run >= 2 and rejected_run >= 2:
        return "mixed"
    if supported_run >= 2:
        return "supported"
    if rejected_run >= 2:
        return "rejected"
    if 1 in signs or -1 in signs:
        return "weak"
    return "inconclusive"


def model_predictor_columns() -> tuple[str, ...]:
    columns = list(MODEL_BASE_PREDICTOR_COLUMNS)
    for window in WINDOWS_MS:
        columns.extend(f"w{window}ms_{suffix}" for suffix in MARKET_FEATURE_SUFFIXES)
    for window in H2_WINDOWS_MS:
        columns.extend(f"h2_w{window}ms_{suffix}" for suffix in H2_FEATURE_SUFFIXES)
    return tuple(columns)


def model_output_columns() -> tuple[str, ...]:
    return (
        MODEL_ID_COLUMNS
        + MODEL_TARGET_COLUMNS
        + MODEL_CONTEXT_COLUMNS
        + model_predictor_columns()
    )


def build_model_matrix(engineered: pd.DataFrame) -> pd.DataFrame:
    allowlist = model_output_columns()
    missing = [column for column in allowlist if column not in engineered]
    if missing:
        raise RuntimeError(f"Missing reviewed model features: {missing}")
    output = engineered.loc[:, allowlist].copy()
    forbidden = {
        "sample_id",
        "state_age_pretransition_seconds",
        "control_sampling_reason",
        "control_distance_seconds",
        "time_since_previous_event_seconds",
        "eligible_control_count",
        "is_control_supported",
        "reported_time",
        "price_anchor_time",
        "state_anchor_time",
    }
    leaked = sorted(forbidden.intersection(output.columns))
    if leaked:
        raise RuntimeError(f"Sampling/audit metadata entered model matrix: {leaked}")
    return output


def build_audit_table(engineered: pd.DataFrame) -> pd.DataFrame:
    validity_columns = [f"w{window}ms_valid" for window in WINDOWS_MS]
    validity_columns.extend(f"h2_w{window}ms_valid" for window in H2_WINDOWS_MS)
    columns = [*AUDIT_BASE_COLUMNS, *validity_columns]
    missing = [column for column in columns if column not in engineered]
    if missing:
        raise RuntimeError(f"Missing audit columns: {missing}")
    return engineered.loc[:, columns].copy()
