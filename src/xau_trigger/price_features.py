"""Causal tick features for the preregistered M5-003 risk bins."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd


REHEDGE_ENDPOINT_SIGNS = {
    "rehedge_sell_occurrence": 1.0,
    "rehedge_buy_occurrence": -1.0,
}

REHEDGE_FEATURES = (
    "signed_mid_change_2s",
    "signed_mid_change_5s",
    "signed_tick_imbalance_2s",
    "signed_tick_imbalance_5s",
    "side_boundary_proximity_2s",
    "side_boundary_proximity_5s",
    "side_prior_boundary_touch_2s",
    "side_prior_boundary_touch_5s",
    "realized_volatility_10s",
    "spread_at_anchor",
    "absolute_state_start_displacement",
    "signed_state_start_displacement",
)

UNLOCK_FEATURES = (
    "absolute_mid_change_2s",
    "absolute_mid_change_5s",
    "absolute_tick_imbalance_2s",
    "absolute_tick_imbalance_5s",
    "range_width_2s",
    "range_width_5s",
    "range_width_10s",
    "either_prior_boundary_touch_2s",
    "either_prior_boundary_touch_5s",
    "realized_volatility_10s",
    "spread_at_anchor",
    "absolute_state_start_displacement",
)

FEATURE_ALLOWLISTS = {
    "rehedge_buy_occurrence": REHEDGE_FEATURES,
    "rehedge_sell_occurrence": REHEDGE_FEATURES,
    "unlock_occurrence": UNLOCK_FEATURES,
}

VALIDITY_COLUMNS = (
    "window_2s_valid",
    "window_5s_valid",
    "window_10s_valid",
    "h2_2s_valid",
    "h2_5s_valid",
    "state_start_reference_valid",
    "current_snapshot_valid",
)


def _require_columns(frame: pd.DataFrame, required: Iterable[str]) -> None:
    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def _timestamp_ns(values: Iterable[object]) -> np.ndarray:
    """Return nanoseconds regardless of a pandas column's stored resolution."""
    return (
        pd.DatetimeIndex(pd.to_datetime(values, errors="raise"))
        .to_numpy(dtype="datetime64[ns]")
        .astype("int64")
    )


class _RangeMinMax:
    """Vectorized segment-tree range min/max queries over half-open slices."""

    def __init__(self, values: np.ndarray):
        source = np.asarray(values, dtype=float)
        if not len(source):
            raise ValueError("Range index requires at least one value")
        size = 1
        while size < len(source):
            size <<= 1
        self.size = size
        self.minimum = np.full(2 * size, np.inf, dtype=float)
        self.maximum = np.full(2 * size, -np.inf, dtype=float)
        self.minimum[size : size + len(source)] = source
        self.maximum[size : size + len(source)] = source
        level = size
        while level > 1:
            parent_start = level // 2
            self.minimum[parent_start:level] = np.minimum(
                self.minimum[level : 2 * level : 2],
                self.minimum[level + 1 : 2 * level : 2],
            )
            self.maximum[parent_start:level] = np.maximum(
                self.maximum[level : 2 * level : 2],
                self.maximum[level + 1 : 2 * level : 2],
            )
            level //= 2

    def query(self, starts: np.ndarray, ends: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        left = np.asarray(starts, dtype=np.int64) + self.size
        right = np.asarray(ends, dtype=np.int64) + self.size
        if left.shape != right.shape:
            raise ValueError("Range starts and ends must have matching shapes")
        minimum = np.full(left.shape, np.inf, dtype=float)
        maximum = np.full(left.shape, -np.inf, dtype=float)
        active = left < right
        while active.any():
            take_left = active & ((left & 1) == 1)
            if take_left.any():
                minimum[take_left] = np.minimum(
                    minimum[take_left], self.minimum[left[take_left]]
                )
                maximum[take_left] = np.maximum(
                    maximum[take_left], self.maximum[left[take_left]]
                )
                left[take_left] += 1
            take_right = active & ((right & 1) == 1)
            if take_right.any():
                right[take_right] -= 1
                minimum[take_right] = np.minimum(
                    minimum[take_right], self.minimum[right[take_right]]
                )
                maximum[take_right] = np.maximum(
                    maximum[take_right], self.maximum[right[take_right]]
                )
            left //= 2
            right //= 2
            active = left < right
        empty = np.asarray(starts) >= np.asarray(ends)
        minimum[empty] = np.nan
        maximum[empty] = np.nan
        return minimum, maximum


@dataclass(frozen=True)
class _WindowStats:
    valid: np.ndarray
    count: np.ndarray
    first_mid: np.ndarray
    current_mid: np.ndarray
    minimum_mid: np.ndarray
    maximum_mid: np.ndarray
    tick_imbalance: np.ndarray
    realized_volatility: np.ndarray
    spread: np.ndarray


class CausalTickFeatureEngine:
    """Efficient causal feature extraction for sorted risk-bin anchors."""

    def __init__(self, ticks: pd.DataFrame, gaps: pd.DataFrame | None = None):
        _require_columns(ticks, ["timestamp", "mid", "spread"])
        ordered = ticks.sort_values("timestamp", kind="stable").reset_index(drop=True)
        if ordered.empty:
            raise ValueError("Tick feature engine requires at least one tick")
        timestamps = pd.to_datetime(ordered["timestamp"], errors="raise")
        if not timestamps.is_monotonic_increasing:
            raise ValueError("Tick timestamps must be monotonically non-decreasing")
        self.ns = _timestamp_ns(timestamps)
        self.mid = ordered["mid"].to_numpy(dtype=float)
        self.spread = ordered["spread"].to_numpy(dtype=float)
        changes = np.diff(self.mid)
        self.prefix_up = np.concatenate(([0], np.cumsum(changes > 0, dtype=np.int64)))
        self.prefix_down = np.concatenate(([0], np.cumsum(changes < 0, dtype=np.int64)))
        self.prefix_square = np.concatenate(([0.0], np.cumsum(np.square(changes))))
        self.range_index = _RangeMinMax(self.mid)

        if gaps is None or gaps.empty:
            self.gap_start_ns = np.array([], dtype=np.int64)
            self.gap_end_ns = np.array([], dtype=np.int64)
        else:
            _require_columns(gaps, ["break_start", "break_end"])
            ordered_gaps = gaps.sort_values("break_start", kind="stable")
            self.gap_start_ns = _timestamp_ns(ordered_gaps["break_start"])
            self.gap_end_ns = _timestamp_ns(ordered_gaps["break_end"])

    def _crosses_gap(self, starts_ns: np.ndarray, ends_ns: np.ndarray) -> np.ndarray:
        if not len(self.gap_start_ns):
            return np.zeros(len(starts_ns), dtype=bool)
        indices = np.searchsorted(self.gap_start_ns, ends_ns, side="left") - 1
        valid_index = indices >= 0
        result = np.zeros(len(starts_ns), dtype=bool)
        result[valid_index] = self.gap_end_ns[indices[valid_index]] > starts_ns[valid_index]
        return result

    def _slice_bounds(
        self,
        anchors_ns: np.ndarray,
        start_offset_ns: int,
        end_offset_ns: int,
        *,
        end_inclusive: bool,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        starts_ns = anchors_ns + start_offset_ns
        ends_ns = anchors_ns + end_offset_ns
        starts = np.searchsorted(self.ns, starts_ns, side="left")
        ends = np.searchsorted(
            self.ns, ends_ns, side="right" if end_inclusive else "left"
        )
        return starts, ends, starts_ns, ends_ns

    def rolling_stats(self, anchors_ns: np.ndarray, window_seconds: int) -> _WindowStats:
        window_ns = int(window_seconds * 1_000_000_000)
        starts, ends, starts_ns, _ = self._slice_bounds(
            anchors_ns,
            -window_ns,
            0,
            end_inclusive=True,
        )
        count = ends - starts
        valid = (
            (starts_ns >= self.ns[0])
            & (count >= 2)
            & ~self._crosses_gap(starts_ns, anchors_ns)
        )
        safe_starts = np.minimum(starts, len(self.mid) - 1)
        safe_last = np.maximum(ends - 1, 0)
        first_mid = self.mid[safe_starts].astype(float)
        current_mid = self.mid[safe_last].astype(float)
        spread = self.spread[safe_last].astype(float)
        minimum_mid, maximum_mid = self.range_index.query(starts, ends)
        transition_end = np.maximum(ends - 1, 0)
        up = self.prefix_up[transition_end] - self.prefix_up[starts]
        down = self.prefix_down[transition_end] - self.prefix_down[starts]
        square = self.prefix_square[transition_end] - self.prefix_square[starts]
        denominator = np.maximum(count - 1, 1)
        imbalance = (up - down) / denominator
        valid &= np.isfinite(current_mid) & np.isfinite(spread)
        for values in [first_mid, current_mid, minimum_mid, maximum_mid, imbalance, square, spread]:
            values[~valid] = np.nan
        return _WindowStats(
            valid=valid,
            count=count,
            first_mid=first_mid,
            current_mid=current_mid,
            minimum_mid=minimum_mid,
            maximum_mid=maximum_mid,
            tick_imbalance=imbalance.astype(float),
            realized_volatility=np.sqrt(square),
            spread=spread,
        )

    def h2_touches(
        self,
        anchors_ns: np.ndarray,
        window_seconds: int,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        window_ns = int(window_seconds * 1_000_000_000)
        prior_start, prior_end, prior_start_ns, _ = self._slice_bounds(
            anchors_ns,
            -2 * window_ns,
            -window_ns,
            end_inclusive=False,
        )
        sequence_start, sequence_end, sequence_start_ns, _ = self._slice_bounds(
            anchors_ns,
            -window_ns,
            0,
            end_inclusive=True,
        )
        _, sequence_pre_end, _, _ = self._slice_bounds(
            anchors_ns,
            -window_ns,
            0,
            end_inclusive=False,
        )
        prior_low, prior_high = self.range_index.query(prior_start, prior_end)
        sequence_pre_low, sequence_pre_high = self.range_index.query(
            sequence_start, sequence_pre_end
        )
        valid = (
            (prior_start_ns >= self.ns[0])
            & ((prior_end - prior_start) >= 2)
            & ((sequence_end - sequence_start) >= 2)
            & ~self._crosses_gap(prior_start_ns, anchors_ns)
        )
        high_touch = valid & (sequence_pre_high >= prior_high)
        low_touch = valid & (sequence_pre_low <= prior_low)
        return valid, high_touch, low_touch

    def state_start_reference(
        self,
        interval_start_ns: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        indices = np.searchsorted(self.ns, interval_start_ns, side="right") - 1
        valid = indices >= 0
        safe = np.maximum(indices, 0)
        reference_ns = self.ns[safe]
        valid &= ~self._crosses_gap(reference_ns, interval_start_ns)
        values = self.mid[safe].astype(float)
        values[~valid] = np.nan
        return valid, values

    def build(self, bins: pd.DataFrame) -> pd.DataFrame:
        required = [
            "risk_bin_id",
            "endpoint",
            "bin_start",
            "interval_start",
        ]
        _require_columns(bins, required)
        source = bins.reset_index(drop=True).copy()
        anchors_ns = _timestamp_ns(source["bin_start"])
        interval_start_ns = _timestamp_ns(source["interval_start"])
        output = pd.DataFrame({"risk_bin_id": source["risk_bin_id"].astype(str)})

        rolling = {window: self.rolling_stats(anchors_ns, window) for window in (2, 5, 10)}
        touches = {window: self.h2_touches(anchors_ns, window) for window in (2, 5)}
        reference_valid, reference_mid = self.state_start_reference(interval_start_ns)
        current = rolling[10].current_mid
        endpoints = source["endpoint"].astype(str).to_numpy()
        signs = np.array([REHEDGE_ENDPOINT_SIGNS.get(item, np.nan) for item in endpoints])

        for window in (2, 5, 10):
            output[f"window_{window}s_valid"] = rolling[window].valid
        for window in (2, 5):
            output[f"h2_{window}s_valid"] = touches[window][0]
        output["state_start_reference_valid"] = reference_valid
        output["current_snapshot_valid"] = np.isfinite(current) & np.isfinite(
            rolling[10].spread
        )

        for window in (2, 5):
            stats = rolling[window]
            mid_change = stats.current_mid - stats.first_mid
            width = stats.maximum_mid - stats.minimum_mid
            neutral = np.full(len(source), 0.5, dtype=float)
            sell_proximity = np.divide(
                stats.current_mid - stats.minimum_mid,
                width,
                out=neutral.copy(),
                where=width != 0,
            )
            buy_proximity = np.divide(
                stats.maximum_mid - stats.current_mid,
                width,
                out=neutral.copy(),
                where=width != 0,
            )
            valid = stats.valid
            output[f"signed_mid_change_{window}s"] = signs * mid_change
            output[f"absolute_mid_change_{window}s"] = np.abs(mid_change)
            output[f"signed_tick_imbalance_{window}s"] = signs * stats.tick_imbalance
            output[f"absolute_tick_imbalance_{window}s"] = np.abs(stats.tick_imbalance)
            output[f"range_width_{window}s"] = width
            output[f"side_boundary_proximity_{window}s"] = np.where(
                signs > 0, sell_proximity, buy_proximity
            )
            h2_valid, high_touch, low_touch = touches[window]
            output[f"side_prior_boundary_touch_{window}s"] = np.where(
                signs > 0, high_touch, low_touch
            ).astype(float)
            output[f"either_prior_boundary_touch_{window}s"] = (
                high_touch | low_touch
            ).astype(float)
            for column in [
                f"signed_mid_change_{window}s",
                f"absolute_mid_change_{window}s",
                f"signed_tick_imbalance_{window}s",
                f"absolute_tick_imbalance_{window}s",
                f"range_width_{window}s",
                f"side_boundary_proximity_{window}s",
            ]:
                output.loc[~valid, column] = np.nan
            for column in [
                f"side_prior_boundary_touch_{window}s",
                f"either_prior_boundary_touch_{window}s",
            ]:
                output.loc[~h2_valid, column] = np.nan

        output["range_width_10s"] = (
            rolling[10].maximum_mid - rolling[10].minimum_mid
        )
        output["realized_volatility_10s"] = rolling[10].realized_volatility
        output["spread_at_anchor"] = rolling[10].spread
        displacement = current - reference_mid
        output["absolute_state_start_displacement"] = np.abs(displacement)
        output["signed_state_start_displacement"] = signs * displacement
        output.loc[~reference_valid, "absolute_state_start_displacement"] = np.nan
        output.loc[~reference_valid, "signed_state_start_displacement"] = np.nan

        all_valid = np.ones(len(output), dtype=bool)
        for endpoint, allowlist in FEATURE_ALLOWLISTS.items():
            mask = endpoints == endpoint
            if mask.any():
                all_valid[mask] = output.loc[mask, list(allowlist)].notna().all(axis=1)
        output["all_features_valid"] = all_valid
        return output


def attach_first_exclusion_reason(audit: pd.DataFrame) -> pd.DataFrame:
    """Apply the frozen deterministic first-reason waterfall."""
    output = audit.copy()
    output["first_exclusion_reason"] = None
    rules = [
        ("unlock_before_floor_excluded", output["unlock_before_floor_excluded"]),
        ("window_10s_invalid", ~output["window_10s_valid"]),
        ("window_5s_invalid", ~output["window_5s_valid"]),
        ("window_2s_invalid", ~output["window_2s_valid"]),
        ("h2_5s_invalid", ~output["h2_5s_valid"]),
        ("h2_2s_invalid", ~output["h2_2s_valid"]),
        ("state_start_reference_invalid", ~output["state_start_reference_valid"]),
        ("current_snapshot_invalid", ~output["current_snapshot_valid"]),
    ]
    for reason, mask in rules:
        assign = output["first_exclusion_reason"].isna() & mask
        output.loc[assign, "first_exclusion_reason"] = reason
    output["is_joint_valid"] = output["first_exclusion_reason"].isna()
    return output


def prepare_candidate_bins(
    risk_bins: pd.DataFrame,
    interval_audit: pd.DataFrame,
    *,
    role_by_date: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Select registered common-hour M5-003 support and attach interval starts."""
    _require_columns(
        risk_bins,
        [
            "risk_bin_id",
            "cohort_id",
            "interval_id",
            "endpoint",
            "bin_width_ms",
            "bin_start",
            "bin_end",
            "state_age_seconds",
            "target_label",
            "is_common_hours",
            "is_cross_split_interval",
        ],
    )
    _require_columns(
        interval_audit,
        ["cohort_id", "interval_id", "bin_width_ms", "start_time"],
    )
    source = risk_bins[
        risk_bins["bin_width_ms"].isin([500, 1000])
        & risk_bins["is_common_hours"]
        & ~risk_bins["is_cross_split_interval"]
    ].copy()
    source["session_date"] = pd.to_datetime(source["bin_start"]).dt.strftime(
        "%Y-%m-%d"
    )
    roles = role_by_date or {
        "2026-07-20": "development",
        "2026-07-21": "development",
        "2026-07-22": "development",
        "2026-07-23": "development",
        "2026-07-24": "internal_reuse",
    }
    source["analysis_role"] = source["session_date"].map(roles)
    source = source[source["analysis_role"].notna()].copy()

    starts = interval_audit[
        ["cohort_id", "interval_id", "bin_width_ms", "start_time"]
    ].copy()
    starts["interval_id"] = starts["interval_id"].astype(str)
    starts = starts.drop_duplicates(
        ["cohort_id", "interval_id", "bin_width_ms"], keep="first"
    ).rename(columns={"start_time": "interval_start"})
    source["interval_id"] = source["interval_id"].astype(str)
    source = source.merge(
        starts,
        on=["cohort_id", "interval_id", "bin_width_ms"],
        how="left",
        validate="many_to_one",
    )
    if source["interval_start"].isna().any():
        raise AssertionError("Every M5-003 candidate bin requires an interval start")
    source["unlock_before_floor_excluded"] = source["endpoint"].eq(
        "unlock_occurrence"
    ) & source["state_age_seconds"].lt(5.0)
    return source.sort_values(
        ["bin_width_ms", "cohort_id", "bin_start", "interval_id"],
        kind="stable",
    ).reset_index(drop=True)


def build_feature_audit(
    candidates: pd.DataFrame,
    ticks_by_cohort: dict[str, pd.DataFrame],
    gaps_by_cohort: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build endpoint features and a deterministic joint-valid audit."""
    frames = []
    for cohort_id, group in candidates.groupby("cohort_id", sort=True):
        if cohort_id not in ticks_by_cohort:
            raise ValueError(f"Missing ticks for cohort: {cohort_id}")
        engine = CausalTickFeatureEngine(
            ticks_by_cohort[cohort_id],
            gaps_by_cohort.get(cohort_id),
        )
        feature_frame = engine.build(group)
        frames.append(
            group.reset_index(drop=True).merge(
                feature_frame,
                on="risk_bin_id",
                how="left",
                validate="one_to_one",
            )
        )
    audit = pd.concat(frames, ignore_index=True).sort_values(
        ["bin_width_ms", "cohort_id", "bin_start", "interval_id"],
        kind="stable",
    ).reset_index(drop=True)
    audit = attach_first_exclusion_reason(audit)
    if not (
        audit["is_joint_valid"]
        == (~audit["unlock_before_floor_excluded"] & audit["all_features_valid"])
    ).all():
        raise AssertionError("Joint-valid flag disagrees with feature/floor contract")

    feature_columns = sorted(set(REHEDGE_FEATURES) | set(UNLOCK_FEATURES))
    identity_columns = [
        "risk_bin_id",
        "cohort_id",
        "interval_id",
        "endpoint",
        "bin_width_ms",
        "bin_start",
        "bin_end",
        "session_date",
        "analysis_role",
        "state_age_seconds",
        "target_label",
    ]
    design = audit.loc[
        audit["is_joint_valid"], [*identity_columns, *feature_columns]
    ].copy()
    for endpoint, allowlist in FEATURE_ALLOWLISTS.items():
        endpoint_rows = design["endpoint"].eq(endpoint)
        if endpoint_rows.any() and design.loc[endpoint_rows, list(allowlist)].isna().any().any():
            raise AssertionError(f"Joint-valid design contains missing {endpoint} predictor")
    return audit, design
