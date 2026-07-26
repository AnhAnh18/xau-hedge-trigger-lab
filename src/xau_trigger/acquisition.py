"""Deterministic, privacy-safe validation for pre-registered M5 inputs."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable

from lxml import html
import pandas as pd

from xau_trigger.parsers.mt5_report import parse_report, parse_report_summary
from xau_trigger.parsers.tick_export import parse_ticks
from xau_trigger.risk_time import detect_coverage_gaps


REQUIRED_PLAN_KEYS = {
    "schema_version",
    "plan_id",
    "registered_on",
    "symbol",
    "server_timezone",
    "sessions",
    "tick_export",
    "trade_report",
    "coverage_gap_policy",
    "analysis_windows",
    "privacy",
}


def _require_keys(mapping: dict, required: set[str], label: str) -> None:
    missing = sorted(required - set(mapping))
    if missing:
        raise ValueError(f"{label} is missing required keys: {missing}")


def _parse_clock(value: str) -> int:
    parts = value.split(":")
    if len(parts) != 3:
        raise ValueError(f"Invalid server-clock time: {value}")
    hour, minute, second = (int(part) for part in parts)
    if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
        raise ValueError(f"Invalid server-clock time: {value}")
    return hour * 3600 + minute * 60 + second


def load_acquisition_plan(path: str | Path) -> dict:
    """Load and validate the machine-readable pre-registration."""
    plan_path = Path(path)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    _require_keys(plan, REQUIRED_PLAN_KEYS, "acquisition plan")
    if plan["schema_version"] != 1:
        raise ValueError("Unsupported acquisition-plan schema version")

    sessions = [str(pd.Timestamp(value).date()) for value in plan["sessions"]]
    if not sessions:
        raise ValueError("Acquisition plan must register at least one session")
    if sessions != sorted(set(sessions)):
        raise ValueError("Acquisition sessions must be unique and sorted")
    plan["sessions"] = sessions

    tick = plan["tick_export"]
    _require_keys(
        tick,
        {
            "allowed_suffixes",
            "delimiter",
            "required_columns",
            "first_tick_no_later_than_server_time",
            "last_tick_no_earlier_than_server_time",
            "preserve_duplicate_milliseconds",
        },
        "tick-export plan",
    )
    if not tick["preserve_duplicate_milliseconds"]:
        raise ValueError("M5 requires duplicate millisecond ticks to be preserved")
    if tick["delimiter"] != "\t":
        raise ValueError("Canonical MT5 tick intake requires a tab delimiter")
    source_hashes = tick.get("source_sha256_allowlist")
    if source_hashes is not None:
        if (
            not source_hashes
            or len(source_hashes) != len(set(source_hashes))
            or any(
                len(value) != 64
                or any(character not in "0123456789abcdef" for character in value)
                for value in source_hashes
            )
        ):
            raise ValueError(
                "Tick source SHA-256 allowlist must contain unique lowercase digests"
            )
    _parse_clock(tick["first_tick_no_later_than_server_time"])
    _parse_clock(tick["last_tick_no_earlier_than_server_time"])

    report = plan["trade_report"]
    _require_keys(
        report,
        {
            "allowed_suffixes",
            "required_sections",
            "required_period_start",
            "required_period_end",
            "require_observed_event_on_each_session",
        },
        "trade-report plan",
    )
    if pd.Timestamp(report["required_period_end"]) < pd.Timestamp(
        report["required_period_start"]
    ):
        raise ValueError("Trade-report period end precedes its start")
    if not report["require_observed_event_on_each_session"]:
        raise ValueError("Each registered session requires observed report events")

    gap = plan["coverage_gap_policy"]
    _require_keys(
        gap,
        {
            "threshold_seconds",
            "default_classification",
            "scheduled_classification_min_recurring_sessions",
            "same_server_clock_tolerance_seconds",
            "retune_after_results",
        },
        "coverage-gap plan",
    )
    if gap["threshold_seconds"] <= 0:
        raise ValueError("Coverage-gap threshold must be positive")
    if gap["scheduled_classification_min_recurring_sessions"] < 2:
        raise ValueError("Scheduled gaps require recurrence across sessions")
    if gap["same_server_clock_tolerance_seconds"] < 0:
        raise ValueError("Gap clock tolerance cannot be negative")
    if gap["retune_after_results"]:
        raise ValueError("Coverage-gap threshold cannot be retuned after results")

    analysis = plan["analysis_windows"]
    _require_keys(
        analysis,
        {
            "primary_server_hours",
            "secondary_full_session",
            "secondary_can_override_primary",
        },
        "analysis-window plan",
    )
    start_hour, end_hour = analysis["primary_server_hours"]
    if not (0 <= start_hour < end_hour <= 24):
        raise ValueError("Primary server hours must satisfy 0 <= start < end <= 24")
    if analysis["secondary_can_override_primary"]:
        raise ValueError("Secondary analysis cannot override primary inference")
    privacy = plan["privacy"]
    _require_keys(
        privacy,
        {
            "raw_files_committed_to_git",
            "output_file_identifiers_are_generated_aliases",
            "record_sha256",
        },
        "privacy plan",
    )
    if privacy["raw_files_committed_to_git"]:
        raise ValueError("Private raw acquisition files cannot be committed")
    if not privacy["output_file_identifiers_are_generated_aliases"]:
        raise ValueError("Acquisition output must use generated file aliases")
    if not privacy["record_sha256"]:
        raise ValueError("Acquisition integrity requires SHA-256 checksums")
    return plan


def sha256_file(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _clock_seconds(timestamp: pd.Timestamp) -> float:
    return (
        timestamp.hour * 3600
        + timestamp.minute * 60
        + timestamp.second
        + timestamp.microsecond / 1_000_000
    )


def _safe_file_record(path: Path, alias: str) -> dict:
    return {
        "file_alias": alias,
        "suffix": path.suffix.lower(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _safe_error(error: Exception, path: Path, alias: str) -> str:
    message = str(error)
    for unsafe in {str(path), str(path.resolve()), path.name}:
        message = message.replace(unsafe, alias)
    return message


def _clock_distance_seconds(left: pd.Timestamp, right: pd.Timestamp) -> float:
    difference = abs(_clock_seconds(left) - _clock_seconds(right))
    return min(difference, 86400 - difference)


def classify_recurring_gaps(
    gaps: pd.DataFrame,
    *,
    minimum_sessions: int,
    tolerance_seconds: float,
) -> pd.DataFrame:
    """Classify a gap as scheduled only after repeated clock-time evidence."""
    if gaps.empty:
        output = gaps.copy()
        output["recurring_clock_matches"] = pd.Series(dtype="int64")
        return output
    output = gaps.copy()
    matches = []
    for row in output.itertuples(index=False):
        start = pd.Timestamp(row.break_start)
        end = pd.Timestamp(row.break_end)
        count = 0
        for candidate in output.itertuples(index=False):
            if (
                _clock_distance_seconds(
                    start,
                    pd.Timestamp(candidate.break_start),
                )
                <= tolerance_seconds
                and _clock_distance_seconds(
                    end,
                    pd.Timestamp(candidate.break_end),
                )
                <= tolerance_seconds
            ):
                count += 1
        matches.append(count)
    output["recurring_clock_matches"] = matches
    output["gap_classification"] = [
        (
            "scheduled_market_closed"
            if count >= minimum_sessions
            else "unknown_coverage_gap"
        )
        for count in matches
    ]
    output["exclusion_reason"] = output["gap_classification"]
    return output


def inspect_tick_exports(paths: Iterable[str | Path], plan: dict) -> dict:
    """Validate registered tick sessions without dropping duplicate timestamps."""
    allowed = {suffix.lower() for suffix in plan["tick_export"]["allowed_suffixes"]}
    candidates = sorted(
        {
            Path(path)
            for path in paths
            if Path(path).is_file() and Path(path).suffix.lower() in allowed
        },
        key=lambda path: path.name,
    )
    file_records: list[dict] = []
    frames: list[pd.DataFrame] = []
    parse_failures = 0
    for index, path in enumerate(candidates, start=1):
        alias = f"tick-{index:03d}"
        record = _safe_file_record(path, alias)
        try:
            ticks = parse_ticks(path)
        except Exception as error:
            record.update(
                {
                    "status": "FAIL",
                    "error_type": type(error).__name__,
                    "error": _safe_error(error, path, alias),
                }
            )
            parse_failures += 1
        else:
            ticks = ticks.copy()
            ticks["source_file_alias"] = alias
            frames.append(ticks)
            record.update(
                {
                    "status": "PASS",
                    "rows": int(len(ticks)),
                    "first_timestamp": ticks["timestamp"].min().isoformat(),
                    "last_timestamp": ticks["timestamp"].max().isoformat(),
                    "duplicate_millisecond_rows": int(
                        ticks["time_msc"].duplicated(keep=False).sum()
                    ),
                    "missing_quote_updates": ticks.attrs.get(
                        "missing_quote_updates",
                        {},
                    ),
                }
            )
        file_records.append(record)

    combined = (
        pd.concat(frames, ignore_index=True)
        if frames
        else pd.DataFrame(columns=["timestamp", "source_file_alias"])
    )
    if not combined.empty:
        combined["session_date"] = combined["timestamp"].dt.strftime("%Y-%m-%d")
        combined = combined.sort_values("timestamp", kind="stable").reset_index(
            drop=True
        )

    gap_policy = plan["coverage_gap_policy"]
    all_gaps = (
        classify_recurring_gaps(
            detect_coverage_gaps(
                combined[["timestamp"]],
                threshold_seconds=gap_policy["threshold_seconds"],
            ),
            minimum_sessions=gap_policy[
                "scheduled_classification_min_recurring_sessions"
            ],
            tolerance_seconds=gap_policy[
                "same_server_clock_tolerance_seconds"
            ],
        )
        if not combined.empty
        else pd.DataFrame()
    )

    required_sessions = plan["sessions"]
    first_limit = _parse_clock(
        plan["tick_export"]["first_tick_no_later_than_server_time"]
    )
    last_limit = _parse_clock(
        plan["tick_export"]["last_tick_no_earlier_than_server_time"]
    )
    session_records = []
    for session in required_sessions:
        group = (
            combined.loc[combined["session_date"] == session].copy()
            if not combined.empty
            else combined.copy()
        )
        if group.empty:
            session_records.append(
                {
                    "date": session,
                    "status": "INCOMPLETE",
                    "reason": "no_registered_ticks",
                    "rows": 0,
                }
            )
            continue
        group = group.sort_values("timestamp", kind="stable")
        first_tick = pd.Timestamp(group["timestamp"].iloc[0])
        last_tick = pd.Timestamp(group["timestamp"].iloc[-1])
        starts_on_time = _clock_seconds(first_tick) <= first_limit
        ends_on_time = _clock_seconds(last_tick) >= last_limit
        if all_gaps.empty:
            gaps = all_gaps.copy()
        else:
            gaps = all_gaps[
                pd.to_datetime(all_gaps["break_start"]).dt.strftime("%Y-%m-%d")
                == session
            ].copy()
            gaps = gaps[
                pd.to_datetime(gaps["break_end"]).dt.strftime("%Y-%m-%d")
                == session
            ]
        no_intraday_gaps = gaps.empty
        session_records.append(
            {
                "date": session,
                "status": (
                    "PASS"
                    if starts_on_time and ends_on_time and no_intraday_gaps
                    else "FAIL"
                ),
                "rows": int(len(group)),
                "first_timestamp": first_tick.isoformat(),
                "last_timestamp": last_tick.isoformat(),
                "starts_by_registered_limit": starts_on_time,
                "ends_by_registered_limit": ends_on_time,
                "has_no_intraday_coverage_gap": no_intraday_gaps,
                "duplicate_millisecond_rows": int(
                    group["timestamp"].duplicated(keep=False).sum()
                ),
                "coverage_gap_count": int(len(gaps)),
                "coverage_gaps": [
                    {
                        "start": pd.Timestamp(row.break_start).isoformat(),
                        "end": pd.Timestamp(row.break_end).isoformat(),
                        "duration_seconds": round(float(row.duration_seconds), 6),
                        "classification": row.gap_classification,
                        "recurring_clock_matches": int(
                            row.recurring_clock_matches
                        ),
                    }
                    for row in gaps.itertuples(index=False)
                ],
            }
        )

    observed_dates = (
        sorted(combined["session_date"].unique().tolist())
        if not combined.empty
        else []
    )
    registered = set(required_sessions)
    cross_file_duplicate_timestamps = 0
    if not combined.empty:
        source_count = combined.groupby("timestamp")["source_file_alias"].nunique()
        cross_file_duplicate_timestamps = int((source_count > 1).sum())

    session_statuses = {record["status"] for record in session_records}
    if parse_failures or "FAIL" in session_statuses:
        status = "FAIL"
    elif "INCOMPLETE" in session_statuses:
        status = "INCOMPLETE"
    else:
        status = "PASS"
    return {
        "status": status,
        "files": file_records,
        "sessions": session_records,
        "registered_sessions": required_sessions,
        "unexpected_dates_ignored": [
            day for day in observed_dates if day not in registered
        ],
        "all_coverage_gaps": [
            {
                "start": pd.Timestamp(row.break_start).isoformat(),
                "end": pd.Timestamp(row.break_end).isoformat(),
                "duration_seconds": round(float(row.duration_seconds), 6),
                "classification": row.gap_classification,
                "recurring_clock_matches": int(row.recurring_clock_matches),
            }
            for row in all_gaps.itertuples(index=False)
        ],
        "cross_file_duplicate_timestamp_count": cross_file_duplicate_timestamps,
        "duplicate_policy": "preserve_and_report_never_deduplicate",
    }


def _decode_report(path: Path) -> str:
    raw = path.read_bytes()
    return (
        raw.decode("utf-16")
        if raw.startswith((b"\xff\xfe", b"\xfe\xff"))
        else raw.decode("utf-8")
    )


def detect_report_sections(path: str | Path) -> set[str]:
    """Return section headings without exposing report content."""
    tree = html.fromstring(_decode_report(Path(path)))
    sections = set()
    for row in tree.xpath("//tr"):
        values = [
            " ".join(cell.text_content().split()).strip().lower()
            for cell in row.xpath("./th|./td")
        ]
        joined = " ".join(values)
        if joined in {"positions", "orders", "deals", "open positions"}:
            sections.add(joined.replace(" ", "_"))
        if values and values[0] == "total net profit:":
            sections.add("summary")
    return sections


def _report_event_dates(tables: dict[str, pd.DataFrame]) -> dict[str, int]:
    timestamps = []
    for table_name, columns in {
        "positions": ["open_time", "close_time"],
        "open_positions": ["open_time"],
        "orders": ["open_time", "completion_time"],
        "deals": ["time"],
    }.items():
        table = tables[table_name]
        for column in columns:
            if column in table:
                timestamps.extend(pd.to_datetime(table[column]).dropna().tolist())
    if not timestamps:
        return {}
    dates = pd.Series(timestamps).dt.strftime("%Y-%m-%d")
    return {str(day): int(count) for day, count in dates.value_counts().sort_index().items()}


def inspect_trade_reports(paths: Iterable[str | Path], plan: dict) -> dict:
    """Validate report structure and registered-session event coverage."""
    allowed = {
        suffix.lower() for suffix in plan["trade_report"]["allowed_suffixes"]
    }
    required_sections = set(plan["trade_report"]["required_sections"])
    candidates = sorted(
        {
            Path(path)
            for path in paths
            if Path(path).is_file() and Path(path).suffix.lower() in allowed
        },
        key=lambda path: path.name,
    )
    file_records = []
    combined_event_dates: dict[str, int] = {}
    parse_failures = 0
    for index, path in enumerate(candidates, start=1):
        alias = f"report-{index:03d}"
        record = _safe_file_record(path, alias)
        try:
            sections = detect_report_sections(path)
            tables = parse_report(path)
            parse_report_summary(path)
            event_dates = _report_event_dates(tables)
        except Exception as error:
            record.update(
                {
                    "status": "FAIL",
                    "error_type": type(error).__name__,
                    "error": _safe_error(error, path, alias),
                }
            )
            parse_failures += 1
        else:
            missing_sections = sorted(required_sections - sections)
            for day, count in event_dates.items():
                combined_event_dates[day] = combined_event_dates.get(day, 0) + count
            record.update(
                {
                    "status": "PASS" if not missing_sections else "FAIL",
                    "sections": sorted(sections),
                    "missing_sections": missing_sections,
                    "positions": int(len(tables["positions"])),
                    "orders": int(len(tables["orders"])),
                    "deals": int(len(tables["deals"])),
                    "open_positions": int(len(tables["open_positions"])),
                    "observed_event_dates": event_dates,
                }
            )
            if missing_sections:
                parse_failures += 1
        file_records.append(record)

    sessions = [
        {
            "date": session,
            "observed_event_count": combined_event_dates.get(session, 0),
            "status": (
                "PASS"
                if combined_event_dates.get(session, 0) > 0
                else "INCOMPLETE"
            ),
        }
        for session in plan["sessions"]
    ]
    if parse_failures:
        status = "FAIL"
    elif not candidates or any(item["status"] == "INCOMPLETE" for item in sessions):
        status = "INCOMPLETE"
    else:
        status = "PASS"
    return {
        "status": status,
        "files": file_records,
        "sessions": sessions,
        "required_period_start": plan["trade_report"]["required_period_start"],
        "required_period_end": plan["trade_report"]["required_period_end"],
    }


def validate_acquisition(
    plan: dict,
    tick_paths: Iterable[str | Path],
    report_paths: Iterable[str | Path],
) -> dict:
    """Return a deterministic aggregate acquisition report."""
    tick_report = inspect_tick_exports(tick_paths, plan)
    trade_report = inspect_trade_reports(report_paths, plan)
    statuses = {tick_report["status"], trade_report["status"]}
    if "FAIL" in statuses:
        status = "FAIL"
    elif statuses == {"PASS"}:
        status = "PASS"
    else:
        status = "INCOMPLETE"
    payload = {
        "schema_version": 1,
        "plan_id": plan["plan_id"],
        "registered_on": plan["registered_on"],
        "sessions": plan["sessions"],
        "status": status,
        "ticks": tick_report,
        "trade_reports": trade_report,
        "privacy": {
            "raw_files_committed_to_git": False,
            "file_identifiers_are_generated_aliases": True,
            "financial_values_emitted": False,
        },
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload["deterministic_validation_sha256"] = sha256(
        encoded.encode("utf-8")
    ).hexdigest()
    return payload


def discover_files(directory: str | Path, suffixes: Iterable[str]) -> list[Path]:
    root = Path(directory)
    allowed = {suffix.lower() for suffix in suffixes}
    if not root.exists():
        return []
    return sorted(
        [
            path
            for path in root.iterdir()
            if path.is_file() and path.suffix.lower() in allowed
        ],
        key=lambda path: path.name,
    )


def build_synthetic_acquisition_files(
    plan: dict,
    directory: str | Path,
) -> tuple[Path, Path]:
    """Create anonymized full-session fixtures for the CLI dry run."""
    output = Path(directory)
    output.mkdir(parents=True, exist_ok=True)
    tick_path = output / "m5_ticks_acquisition_dry_run.tsv"
    report_path = output / "m5_report_acquisition_dry_run.html"

    tick_lines = ["<DATE>\t<TIME>\t<BID>\t<ASK>\t<LAST>\t<VOLUME>\t<FLAGS>"]
    for session in plan["sessions"]:
        timestamps = pd.date_range(
            f"{session} 01:00:00",
            f"{session} 23:50:00",
            freq="60s",
        )
        for timestamp in timestamps:
            tick_lines.append(
                f"{timestamp:%Y.%m.%d}\t{timestamp:%H:%M:%S}.000"
                "\t4000.00\t4000.20\t\t\t6"
            )
    tick_path.write_bytes(("\n".join(tick_lines) + "\n").encode("utf-8"))

    lines = ["<html><body><table>", '<tr><th colspan="14">Positions</th></tr>']
    lines.append(
        "<tr><th>Time</th><th>Position</th><th>Symbol</th><th>Type</th>"
        "<th>Volume</th><th>Price</th><th>S / L</th><th>T / P</th>"
        "<th>Time</th><th>Price</th><th>Commission</th><th>Swap</th>"
        "<th>Profit</th></tr>"
    )
    for index, session in enumerate(plan["sessions"], start=1):
        date = session.replace("-", ".")
        lines.append(
            f"<tr><td>{date} 12:00:00</td><td>{100 + index}</td>"
            "<td>XAUUSD</td><td>buy</td><td>0.3</td><td>4000.00</td>"
            f"<td></td><td></td><td>{date} 12:00:02</td>"
            "<td>4000.20</td><td>0.00</td><td>0.00</td>"
            "<td>1.00</td></tr>"
        )
    lines.extend(
        [
            '<tr><th colspan="11">Orders</th></tr>',
            "<tr><th>Open Time</th><th>Order</th><th>Symbol</th>"
            "<th>Type</th><th>Volume</th><th>Price</th><th>S / L</th>"
            "<th>T / P</th><th>Time</th><th>State</th><th>Comment</th></tr>",
        ]
    )
    for index, session in enumerate(plan["sessions"], start=1):
        date = session.replace("-", ".")
        lines.append(
            f"<tr><td>{date} 12:00:00</td><td>{200 + index}</td>"
            "<td>XAUUSD</td><td>buy</td><td>0.3 / 0.3</td>"
            f"<td>market</td><td></td><td></td><td>{date} 12:00:00</td>"
            "<td>filled</td><td></td></tr>"
        )
    lines.extend(
        [
            '<tr><th colspan="15">Deals</th></tr>',
            "<tr><th>Time</th><th>Deal</th><th>Symbol</th><th>Type</th>"
            "<th>Direction</th><th>Volume</th><th>Price</th><th>Order</th>"
            "<th>Cost</th><th>Commission</th><th>Fee</th><th>Swap</th>"
            "<th>Profit</th><th>Balance</th><th>Comment</th></tr>",
        ]
    )
    for index, session in enumerate(plan["sessions"], start=1):
        date = session.replace("-", ".")
        lines.append(
            f"<tr><td>{date} 12:00:00</td><td>{300 + index}</td>"
            "<td>XAUUSD</td><td>buy</td><td>in</td><td>0.3</td>"
            f"<td>4000.00</td><td>{200 + index}</td><td></td>"
            "<td>0.00</td><td>0.00</td><td>0.00</td><td>1.00</td>"
            "<td>1000.00</td><td></td></tr>"
        )
    first_date = plan["sessions"][0].replace("-", ".")
    lines.extend(
        [
            '<tr><th colspan="12">Open Positions</th></tr>',
            "<tr><th>Time</th><th>Position</th><th>Symbol</th><th>Type</th>"
            "<th>Volume</th><th>Price</th><th>S / L</th><th>T / P</th>"
            "<th>Market Price</th><th>Swap</th><th>Profit</th>"
            "<th>Comment</th></tr>",
            f"<tr><td>{first_date} 12:00:01</td><td>401</td>"
            "<td>XAUUSD</td><td>sell</td><td>0.3</td><td>4000.10</td>"
            "<td></td><td></td><td>4000.00</td><td>0.00</td>"
            "<td>1.00</td><td></td></tr>",
            "<tr><td>Total Net Profit:</td><td>3.00</td></tr>",
            "</table></body></html>",
        ]
    )
    report_path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    return tick_path, report_path
