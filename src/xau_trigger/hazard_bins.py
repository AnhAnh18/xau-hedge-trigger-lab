"""Causal risk-bin construction for the bounded M5-002 pilot.

This module reuses the canonical support logic in :mod:`xau_trigger.risk_time`
and deliberately contains no fitted model.  Named cohorts remain isolated so
supplemental ticks cannot change the M2-M4 canonical coverage.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from xau_trigger.parsers.tick_export import parse_ticks
from xau_trigger.risk_time import (
    ELIGIBLE_STATES,
    append_right_censored_tail,
    detect_coverage_gaps,
    partition_risk_time,
)


ENDPOINT_SPECS = {
    "HEDGED_1X1": {
        "endpoint": "unlock_occurrence",
        "targets": {"UNLOCK_TO_BUY", "UNLOCK_TO_SELL"},
    },
    "ONE_BUY": {
        "endpoint": "rehedge_sell_occurrence",
        "targets": {"REHEDGE_SELL"},
    },
    "ONE_SELL": {
        "endpoint": "rehedge_buy_occurrence",
        "targets": {"REHEDGE_BUY"},
    },
}

INTERNAL_DEVELOPMENT_DAY = "2026-07-23"
INTERNAL_HOLDOUT_DAY = "2026-07-24"
COMMON_HOUR_START = 12
COMMON_HOUR_END = 24


def _require_columns(frame: pd.DataFrame, required: Iterable[str]) -> None:
    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_tick_cohort(
    paths: Iterable[str | Path],
    sessions: Iterable[str],
    *,
    expected_sha256: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Parse only registered session rows into a separately named cohort.

    Duplicate timestamps are preserved.  The caller controls the output path;
    this function never reads or writes the M2-M4 canonical ticks parquet.
    When checksums are supplied, only the uniquely matching files are parsed.
    """
    registered = {str(pd.Timestamp(day).date()) for day in sessions}
    candidates = sorted(
        {
            Path(item)
            for item in paths
            if Path(item).is_file()
            and Path(item).suffix.lower() in {".csv", ".tsv"}
        },
        key=lambda item: item.name,
    )
    expected = list(expected_sha256 or [])
    if expected:
        if len(expected) != len(set(expected)):
            raise ValueError("Expected tick checksums must be unique")
        matches: dict[str, list[Path]] = {digest: [] for digest in expected}
        for path in candidates:
            digest = _file_sha256(path)
            if digest in matches:
                matches[digest].append(path)
        unresolved = {
            digest: len(paths_for_digest)
            for digest, paths_for_digest in matches.items()
            if len(paths_for_digest) != 1
        }
        if unresolved:
            raise ValueError(
                "Pinned tick checksum must resolve to exactly one file: "
                f"{unresolved}"
            )
        candidates = [matches[digest][0] for digest in expected]

    frames = []
    for path in candidates:
        ticks = parse_ticks(path)
        dates = ticks["timestamp"].dt.strftime("%Y-%m-%d")
        selected = ticks.loc[dates.isin(registered)].copy()
        if not selected.empty:
            frames.append(selected)
    if not frames:
        raise ValueError("No ticks found for the registered cohort sessions")
    combined = pd.concat(frames, ignore_index=True)
    combined = combined.sort_values("timestamp", kind="stable").reset_index(
        drop=True
    )
    observed = set(combined["timestamp"].dt.strftime("%Y-%m-%d"))
    missing = sorted(registered - observed)
    if missing:
        raise ValueError(f"Missing registered tick sessions: {missing}")
    if not combined["timestamp"].is_monotonic_increasing:
        raise ValueError("Cohort ticks must be monotonically non-decreasing")
    return combined


def canonicalize_cohort_support(
    intervals: pd.DataFrame,
    lifecycle_events: pd.DataFrame,
    ticks: pd.DataFrame,
    *,
    cohort_id: str,
    breaks: pd.DataFrame | None = None,
) -> dict:
    """Clip M2 intervals to one named cohort and partition tradeable support."""
    _require_columns(ticks, ["timestamp"])
    if ticks.empty:
        raise ValueError("A cohort requires at least one tick")
    timestamps = pd.to_datetime(ticks["timestamp"], errors="raise")
    if not timestamps.is_monotonic_increasing:
        raise ValueError("Cohort ticks must be monotonically non-decreasing")
    coverage_start = pd.Timestamp(timestamps.iloc[0])
    coverage_end = pd.Timestamp(timestamps.iloc[-1])
    canonical = append_right_censored_tail(
        intervals,
        lifecycle_events,
        coverage_end=coverage_end,
    )
    cohort_breaks = (
        detect_coverage_gaps(ticks[["timestamp"]])
        if breaks is None
        else breaks.copy()
    )
    fragments = partition_risk_time(
        canonical,
        coverage_start=coverage_start,
        coverage_end=coverage_end,
        breaks=cohort_breaks,
    )
    canonical = canonical.copy()
    canonical["interval_id"] = canonical["interval_id"].astype(str)
    fragments = fragments.copy()
    fragments["interval_id"] = fragments["interval_id"].astype(str)
    return {
        "cohort_id": cohort_id,
        "coverage_start": coverage_start,
        "coverage_end": coverage_end,
        "canonical_intervals": canonical,
        "breaks": cohort_breaks,
        "fragments": fragments,
    }


def _grid_starts(
    start: pd.Timestamp,
    end: pd.Timestamp,
    width_seconds: float,
) -> np.ndarray:
    width_ns = int(round(width_seconds * 1_000_000_000))
    if width_ns <= 0:
        raise ValueError("Bin width must be positive")
    start_ns = pd.Timestamp(start).value
    end_ns = pd.Timestamp(end).value
    first_ns = ((start_ns + width_ns - 1) // width_ns) * width_ns
    final_start_ns = end_ns - width_ns
    if first_ns > final_start_ns:
        return np.array([], dtype="int64")
    return np.arange(first_ns, final_start_ns + 1, width_ns, dtype="int64")


def _tradeable_ages(
    interval_start: pd.Timestamp,
    bin_start_ns: np.ndarray,
    breaks: pd.DataFrame,
) -> np.ndarray:
    source_ns = pd.Timestamp(interval_start).value
    age_ns = bin_start_ns.astype("int64") - source_ns
    excluded_ns = np.zeros(len(bin_start_ns), dtype="int64")
    if not breaks.empty:
        _require_columns(breaks, ["break_start", "break_end"])
        for row in breaks.itertuples(index=False):
            gap_start_ns = pd.Timestamp(row.break_start).value
            gap_end_ns = pd.Timestamp(row.break_end).value
            overlap_start = max(source_ns, gap_start_ns)
            overlap_end = np.minimum(bin_start_ns, gap_end_ns)
            excluded_ns += np.maximum(overlap_end - overlap_start, 0)
    ages = (age_ns - excluded_ns) / 1_000_000_000
    if (ages < -1e-9).any():
        raise ValueError("Tradeable state age cannot be negative")
    return ages.astype(float)


def _endpoint_for_state(state: str) -> str | None:
    spec = ENDPOINT_SPECS.get(state)
    return None if spec is None else str(spec["endpoint"])


def _split_for_timestamp(cohort_id: str, timestamp: pd.Timestamp) -> str:
    if cohort_id != "internal_2026_07_23_24":
        return "supplemental"
    day = pd.Timestamp(timestamp).strftime("%Y-%m-%d")
    if day == INTERNAL_DEVELOPMENT_DAY:
        return "development"
    if day == INTERNAL_HOLDOUT_DAY:
        return "holdout"
    return "outside_internal_split"


def _inside_common_hours(start: pd.Timestamp, end: pd.Timestamp) -> bool:
    day_start = pd.Timestamp(start).normalize()
    common_start = day_start + pd.Timedelta(hours=COMMON_HOUR_START)
    common_end = day_start + pd.Timedelta(hours=COMMON_HOUR_END)
    return pd.Timestamp(start) >= common_start and pd.Timestamp(end) <= common_end


def _interval_metadata(support: dict) -> pd.DataFrame:
    canonical = support["canonical_intervals"].copy()
    canonical["start_time"] = pd.to_datetime(canonical["start_time"])
    canonical["end_time"] = pd.to_datetime(canonical["end_time"])
    if "terminal_kind" not in canonical:
        canonical["terminal_kind"] = "event"
    if "is_synthetic_tail" not in canonical:
        canonical["is_synthetic_tail"] = False
    overlap = canonical[
        (canonical["end_time"] >= support["coverage_start"])
        & (canonical["start_time"] <= support["coverage_end"])
    ].copy()
    overlap["clipped_start"] = overlap["start_time"].clip(
        lower=support["coverage_start"]
    )
    overlap["clipped_end"] = overlap["end_time"].clip(
        upper=support["coverage_end"]
    )
    overlap["is_left_truncated"] = overlap["start_time"] < support["coverage_start"]
    overlap["is_right_censored"] = (
        (overlap["end_time"] > support["coverage_end"])
        | overlap["terminal_kind"].eq("right_censored")
    )
    overlap["is_cross_midnight"] = (
        overlap["start_time"].dt.normalize() != overlap["end_time"].dt.normalize()
    )
    overlap["is_eligible_state"] = overlap["state"].isin(ELIGIBLE_STATES)
    overlap["endpoint"] = overlap["state"].map(_endpoint_for_state)
    overlap["cohort_id"] = support["cohort_id"]
    return overlap


def build_wall_clock_risk_bins(
    support: dict,
    *,
    bin_width_seconds: float,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Build complete wall-clock bins and a cohort interval audit."""
    metadata = _interval_metadata(support)
    lookup = metadata.set_index("interval_id", drop=False)
    fragments = support["fragments"]
    eligible = fragments[
        fragments["is_primary_inference_eligible"]
        & fragments["is_tradeable"]
        & fragments["state"].isin(ELIGIBLE_STATES)
        & (fragments["duration_seconds"] > 0)
    ].copy()

    records: list[dict] = []
    width_ns = int(round(bin_width_seconds * 1_000_000_000))
    width_ms = int(round(bin_width_seconds * 1000))
    for fragment in eligible.itertuples(index=False):
        interval = lookup.loc[str(fragment.interval_id)]
        starts_ns = _grid_starts(
            pd.Timestamp(fragment.segment_start),
            pd.Timestamp(fragment.segment_end),
            bin_width_seconds,
        )
        if not len(starts_ns):
            continue
        ages = _tradeable_ages(
            pd.Timestamp(interval.start_time),
            starts_ns,
            support["breaks"],
        )
        endpoint = _endpoint_for_state(str(interval.state))
        target_types = ENDPOINT_SPECS[str(interval.state)]["targets"]
        source_end = pd.Timestamp(interval.end_time)
        following = interval.following_event_type
        terminal_kind = str(interval.terminal_kind)
        for start_ns, state_age in zip(starts_ns, ages):
            bin_start = pd.Timestamp(start_ns)
            bin_end = pd.Timestamp(start_ns + width_ns)
            reaches_event = terminal_kind == "event" and bin_end == source_end
            is_target = bool(reaches_event and following in target_types)
            is_competing = bool(
                reaches_event and pd.notna(following) and following not in target_types
            )
            split = _split_for_timestamp(support["cohort_id"], bin_start)
            records.append(
                {
                    "risk_bin_id": (
                        f"{support['cohort_id']}:{width_ms}:"
                        f"{interval.interval_id}:{start_ns}"
                    ),
                    "cohort_id": support["cohort_id"],
                    "interval_id": str(interval.interval_id),
                    "endpoint": endpoint,
                    "state": str(interval.state),
                    "bin_width_ms": width_ms,
                    "bin_start": bin_start,
                    "bin_end": bin_end,
                    "state_age_seconds": float(state_age),
                    "target_label": int(is_target),
                    "is_competing_terminal_bin": is_competing,
                    "competing_event_type": str(following) if is_competing else None,
                    "following_event_type": (
                        str(following) if reaches_event and pd.notna(following) else None
                    ),
                    "interval_terminal_kind": terminal_kind,
                    "split": split,
                    "is_common_hours": _inside_common_hours(bin_start, bin_end),
                    "is_cross_split_interval": False,
                    "is_primary_model_eligible": False,
                    "is_last_representable_bin": False,
                    "censor_reason": None,
                }
            )

    bins = pd.DataFrame(records)
    if bins.empty:
        raise ValueError("No complete risk bins were representable")
    bins = bins.sort_values(
        ["cohort_id", "bin_width_ms", "bin_start", "interval_id"],
        kind="stable",
    ).reset_index(drop=True)

    internal = bins[bins["cohort_id"] == "internal_2026_07_23_24"]
    split_counts = internal.groupby("interval_id")["split"].agg(
        lambda values: len(set(values) & {"development", "holdout"})
    )
    cross_split_ids = set(split_counts[split_counts > 1].index.astype(str))
    bins["is_cross_split_interval"] = bins["interval_id"].isin(cross_split_ids)
    bins["is_primary_model_eligible"] = (
        bins["cohort_id"].eq("internal_2026_07_23_24")
        & bins["split"].isin(["development", "holdout"])
        & bins["is_common_hours"]
        & ~bins["is_cross_split_interval"]
    )

    last_indices = bins.groupby(["cohort_id", "interval_id"], sort=False).tail(1).index
    bins.loc[last_indices, "is_last_representable_bin"] = True
    meta_lookup = lookup
    for index in last_indices:
        row = bins.loc[index]
        interval = meta_lookup.loc[str(row["interval_id"])]
        if row["target_label"] == 1:
            reason = "target_event"
        elif row["is_competing_terminal_bin"]:
            reason = "competing_endpoint"
        elif bool(interval.is_right_censored):
            reason = (
                "synthetic_right_censor"
                if bool(interval.is_synthetic_tail)
                else "coverage_right_censor"
            )
        else:
            reason = None
        bins.loc[index, "censor_reason"] = reason

    counts = bins.groupby("interval_id").size().rename("representable_bin_count")
    targets = bins.groupby("interval_id")["target_label"].sum().rename(
        "representable_target_count"
    )
    competing = bins.groupby("interval_id")["is_competing_terminal_bin"].sum().rename(
        "representable_competing_count"
    )
    interval_audit = metadata.merge(
        counts,
        how="left",
        left_on="interval_id",
        right_index=True,
    ).merge(targets, how="left", left_on="interval_id", right_index=True).merge(
        competing,
        how="left",
        left_on="interval_id",
        right_index=True,
    )
    for column in [
        "representable_bin_count",
        "representable_target_count",
        "representable_competing_count",
    ]:
        interval_audit[column] = interval_audit[column].fillna(0).astype(int)
    interval_audit["bin_width_ms"] = width_ms
    interval_audit["is_cross_split_interval"] = interval_audit["interval_id"].isin(
        cross_split_ids
    )
    interval_audit["model_exclusion_reason"] = None
    interval_audit.loc[
        ~interval_audit["is_eligible_state"], "model_exclusion_reason"
    ] = "ineligible_state"
    interval_audit.loc[
        interval_audit["representable_bin_count"].eq(0)
        & interval_audit["is_eligible_state"],
        "model_exclusion_reason",
    ] = "no_complete_bin"
    interval_audit.loc[
        interval_audit["is_left_truncated"], "model_exclusion_reason"
    ] = "left_truncated"
    interval_audit.loc[
        interval_audit["is_cross_split_interval"], "model_exclusion_reason"
    ] = "cross_development_holdout"

    eligible_seconds = float(eligible["duration_seconds"].sum())
    representable_seconds = float(len(bins) * bin_width_seconds)
    dropped_seconds = eligible_seconds - representable_seconds
    if dropped_seconds < -1e-6:
        raise AssertionError("Representable bins exceed eligible fragment support")
    accounting = {
        "cohort_id": support["cohort_id"],
        "bin_width_ms": width_ms,
        "eligible_fragment_seconds": round(eligible_seconds, 6),
        "representable_bin_count": int(len(bins)),
        "representable_bin_seconds": round(representable_seconds, 6),
        "dropped_partial_seconds": round(max(dropped_seconds, 0.0), 6),
        "reconciliation_delta_seconds": round(
            eligible_seconds - representable_seconds - max(dropped_seconds, 0.0),
            9,
        ),
        "cross_split_interval_ids": sorted(cross_split_ids),
        "target_bin_count": int(bins["target_label"].sum()),
        "competing_terminal_bin_count": int(
            bins["is_competing_terminal_bin"].sum()
        ),
    }
    return bins, interval_audit, accounting


def dataframe_sha256(frame: pd.DataFrame, columns: Iterable[str] | None = None) -> str:
    """Hash frame values and schema deterministically without Parquet metadata."""
    selected = frame[list(columns)].copy() if columns is not None else frame.copy()
    schema = [(column, str(selected[column].dtype)) for column in selected.columns]
    digest = sha256(json.dumps(schema, separators=(",", ":")).encode("utf-8"))
    hashes = pd.util.hash_pandas_object(selected, index=False, categorize=True)
    digest.update(hashes.to_numpy(dtype="<u8", copy=False).tobytes())
    return digest.hexdigest()
