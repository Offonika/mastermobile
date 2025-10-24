"""Utilities to inject and resolve synthetic alerts in Alertmanager sandboxes."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx


@dataclass(frozen=True, slots=True)
class AlertDefinition:
    """Static metadata that defines a synthetic alert template."""

    slug: str
    alertname: str
    service: str
    severity: str
    annotations: Mapping[str, str]
    generator_url: str | None = None

    def base_labels(self) -> dict[str, str]:
        """Return a copy of the default label set."""

        return {
            "alertname": self.alertname,
            "service": self.service,
            "severity": self.severity,
            "environment": "sandbox",
        }


ALERT_DEFINITIONS: dict[str, AlertDefinition] = {
    definition.slug: definition
    for definition in (
        AlertDefinition(
            slug="call_export_run_failed",
            alertname="CallExportRunFailed",
            service="call-export",
            severity="critical",
            annotations={
                "summary": "Call export run failed",
                "description": (
                    "Synthetic alert that mimics a failed export run. "
                    "Inspect the scheduler logs and rerun the period once the root cause is resolved."
                ),
            },
        ),
        AlertDefinition(
            slug="call_export_cost_budget",
            alertname="CallExportCostBudget",
            service="call-export",
            severity="warning",
            annotations={
                "summary": "Call export cost budget exceeded",
                "description": (
                    "Synthetic alert for budget overspend. "
                    "Validate Whisper pricing, confirm optional summary generation, and notify the product owner."
                ),
            },
        ),
        AlertDefinition(
            slug="call_export_retry_storm",
            alertname="CallExportRetryStorm",
            service="call-export",
            severity="warning",
            annotations={
                "summary": "Call export retries spiking",
                "description": (
                    "Synthetic alert for retry storm conditions. "
                    "Check Bitrix24 and STT error rates, then enable throttling if required."
                ),
            },
        ),
        AlertDefinition(
            slug="call_export_5xx_growth",
            alertname="CallExport5xxGrowth",
            service="call-export",
            severity="critical",
            annotations={
                "summary": "Call export 5xx growth",
                "description": (
                    "Synthetic alert for upstream 5xx growth. "
                    "Confirm Whisper availability or switch the processing region."
                ),
            },
        ),
        AlertDefinition(
            slug="call_export_dlq_spike",
            alertname="CallExportDLQSpike",
            service="call-export",
            severity="warning",
            annotations={
                "summary": "Call export DLQ spike",
                "description": (
                    "Synthetic alert for DLQ growth. "
                    "Inspect the call_export queue and replay messages after triage."
                ),
            },
        ),
        AlertDefinition(
            slug="call_export_job_long_running",
            alertname="CallExportJobLongRunning",
            service="call-export",
            severity="warning",
            annotations={
                "summary": "Call export job running too long",
                "description": (
                    "Synthetic alert for long running call export job. "
                    "Check the orchestrator and adjust the Alertmanager filter if legacy status values are used."
                ),
            },
        ),
    )
}


class AlertManagerError(RuntimeError):
    """Raised when Alertmanager returns an unexpected response."""


def parse_key_value_pairs(raw_values: Iterable[str]) -> dict[str, str]:
    """Split ``key=value`` pairs from CLI arguments into a dictionary."""

    result: dict[str, str] = {}
    for raw in raw_values:
        entries = [item.strip() for item in raw.split(",") if item.strip()]
        for entry in entries:
            if "=" not in entry:
                msg = f"Invalid entry '{entry}'. Expected format key=value."
                raise argparse.ArgumentTypeError(msg)
            key, value = entry.split("=", maxsplit=1)
            result[key.strip()] = value.strip()
    return result


def build_payload(
    *,
    definition: AlertDefinition,
    starts_at: datetime,
    ends_at: datetime,
    extra_labels: Mapping[str, str],
    extra_annotations: Mapping[str, str],
    resolved: bool,
) -> dict[str, object]:
    """Construct the JSON payload for Alertmanager."""

    labels = definition.base_labels()
    labels.update(extra_labels)

    annotations = dict(definition.annotations)
    annotations.update(extra_annotations)

    payload: dict[str, object] = {
        "labels": labels,
        "annotations": annotations,
        "startsAt": starts_at.isoformat(),
        "endsAt": ends_at.isoformat(),
    }
    if resolved:
        payload["status"] = {"state": "resolved"}
    if definition.generator_url:
        payload["generatorURL"] = definition.generator_url
    return payload


def post_alert(
    *,
    client: httpx.Client,
    url: str,
    payload: list[dict[str, object]],
    dry_run: bool,
) -> None:
    """Send the payload to Alertmanager or print it in dry-run mode."""

    if dry_run:
        print("DRY-RUN: would POST to", url)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    response = client.post(url, json=payload, timeout=10.0)
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:  # pragma: no cover - defensive guard
        detail = exc.response.text
        raise AlertManagerError(f"Alertmanager responded with {exc.response.status_code}: {detail}") from exc

    print(f"Sent {len(payload)} alert event(s) to {url}.")


def inject_alert(
    *,
    definition: AlertDefinition,
    alertmanager_url: str,
    duration_minutes: int,
    labels: Mapping[str, str],
    annotations: Mapping[str, str],
    dry_run: bool,
) -> None:
    """Inject a synthetic alert for the provided definition."""

    if duration_minutes <= 0:
        raise argparse.ArgumentTypeError("duration must be a positive integer")

    starts_at = datetime.now(tz=UTC)
    ends_at = starts_at + timedelta(minutes=duration_minutes)
    payload = [
        build_payload(
            definition=definition,
            starts_at=starts_at,
            ends_at=ends_at,
            extra_labels=labels,
            extra_annotations=annotations,
            resolved=False,
        )
    ]
    with httpx.Client(base_url=alertmanager_url.rstrip("/")) as client:
        post_alert(
            client=client,
            url="/api/v2/alerts",
            payload=payload,
            dry_run=dry_run,
        )
    print(
        f"Injected alert '{definition.alertname}' for {duration_minutes} minute(s) into {alertmanager_url}."
    )


def resolve_alert(
    *,
    definition: AlertDefinition,
    alertmanager_url: str,
    labels: Mapping[str, str],
    annotations: Mapping[str, str],
    dry_run: bool,
) -> None:
    """Resolve a previously injected synthetic alert."""

    ends_at = datetime.now(tz=UTC)
    starts_at = ends_at - timedelta(minutes=5)
    payload = [
        build_payload(
            definition=definition,
            starts_at=starts_at,
            ends_at=ends_at,
            extra_labels=labels,
            extra_annotations=annotations,
            resolved=True,
        )
    ]
    with httpx.Client(base_url=alertmanager_url.rstrip("/")) as client:
        post_alert(
            client=client,
            url="/api/v2/alerts",
            payload=payload,
            dry_run=dry_run,
        )
    print(f"Resolved alert '{definition.alertname}' via {alertmanager_url}.")


def available_rule_slugs() -> list[str]:
    """Return the list of supported alert slugs."""

    return sorted(ALERT_DEFINITIONS)


def build_parser() -> argparse.ArgumentParser:
    """Configure the CLI parser."""

    parser = argparse.ArgumentParser(
        description="Inject or resolve synthetic alerts against an Alertmanager sandbox.",
    )
    parser.add_argument(
        "--alertmanager-url",
        default="http://localhost:9093",
        help="Alertmanager base URL (default: %(default)s)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the payload instead of sending it to Alertmanager.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inject_parser = subparsers.add_parser("inject", help="Inject a synthetic alert event.")
    inject_parser.add_argument(
        "--rule",
        required=True,
        choices=available_rule_slugs(),
        help="Alert slug to inject.",
    )
    inject_parser.add_argument(
        "--duration",
        type=int,
        default=15,
        help="Duration for the synthetic alert in minutes (default: %(default)s).",
    )
    inject_parser.add_argument(
        "--label",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Extra label to attach. Can be specified multiple times or as comma-separated values.",
    )
    inject_parser.add_argument(
        "--annotation",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Extra annotation to attach. Can be specified multiple times or as comma-separated values.",
    )

    reset_parser = subparsers.add_parser("reset", help="Resolve a synthetic alert event.")
    reset_parser.add_argument(
        "--rule",
        choices=available_rule_slugs() + ["all"],
        default="all",
        help="Alert slug to resolve (default: all).",
    )
    reset_parser.add_argument(
        "--label",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Extra label filter used during resolution. Matches the values used for injection.",
    )
    reset_parser.add_argument(
        "--annotation",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Extra annotations to include in the resolution payload.",
    )

    subparsers.add_parser("list", help="List available alert rule slugs.")

    return parser


def run(argv: list[str]) -> int:
    """Entrypoint for the CLI."""

    parser = build_parser()
    args = parser.parse_args(argv)

    labels = parse_key_value_pairs(args.label)
    annotations = parse_key_value_pairs(args.annotation)

    if args.command == "list":
        for slug in available_rule_slugs():
            print(slug)
        return 0

    if args.command == "inject":
        definition = ALERT_DEFINITIONS[args.rule]
        inject_alert(
            definition=definition,
            alertmanager_url=args.alertmanager_url,
            duration_minutes=args.duration,
            labels=labels,
            annotations=annotations,
            dry_run=args.dry_run,
        )
        return 0

    if args.command == "reset":
        if args.rule == "all":
            definitions = ALERT_DEFINITIONS.values()
        else:
            definitions = (ALERT_DEFINITIONS[args.rule],)
        for definition in definitions:
            resolve_alert(
                definition=definition,
                alertmanager_url=args.alertmanager_url,
                labels=labels,
                annotations=annotations,
                dry_run=args.dry_run,
            )
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:]))
