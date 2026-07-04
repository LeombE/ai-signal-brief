from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .topic_discovery import (
    TopicDiscoveryError,
    TopicDiscoveryResult,
    _load_valid_source_registry,
    _registry_source_ids,
    _resolve_safe_outputs_path,
    discover_topics_from_observation_data,
)


class LiveDryRunError(RuntimeError):
    """Raised when live-source dry-run metadata cannot be generated safely."""


@dataclass(frozen=True)
class LiveDryRunResult:
    output_path: Path
    candidates: dict[str, Any]


LIVE_DRY_RUN_SAFETY_FLAGS = [
    "live_dry_run",
    "metadata_only",
    "manual_review_required",
    "no_live_fetch",
    "no_publication_candidate",
]

DISALLOWED_MARKERS = (
    "login_required",
    "login-required",
    "paywalled_content",
    "paywalled-content",
    "signed_url",
    "signed-url",
    "private_url",
    "private-url",
    "private_repository",
    "private-repository",
    "private_workspace",
    "private-workspace",
    "private_model",
    "private-model",
    "raw_html",
    "raw-html",
    "raw_html_commit",
    "raw-html-commit",
    "raw_html_snapshot",
    "raw-html-snapshot",
)


def discover_topics_live_dry_run(
    *,
    scan_date: str,
    sources_path: str | Path,
    output_path: str | Path,
    artifact_only: bool,
    metadata_only: bool,
    timezone_name: str = "Asia/Kuala_Lumpur",
    repo_root: str | Path | None = None,
) -> LiveDryRunResult:
    if not artifact_only:
        raise LiveDryRunError("--artifact-only is required")
    if not metadata_only:
        raise LiveDryRunError("--metadata-only is required")

    root = Path(repo_root) if repo_root is not None else Path.cwd()
    try:
        _resolve_safe_outputs_path(output_path, root)
    except TopicDiscoveryError as exc:
        raise LiveDryRunError(str(exc)) from exc

    try:
        source_registry = _load_valid_source_registry(sources_path)
    except TopicDiscoveryError as exc:
        raise LiveDryRunError(str(exc)) from exc
    _validate_live_dry_run_registry(source_registry)
    observations = _metadata_observations_from_registry(source_registry, scan_date)

    try:
        result = discover_topics_from_observation_data(
            scan_date=scan_date,
            sources_path=sources_path,
            source_registry=source_registry,
            observations=observations,
            output_path=output_path,
            timezone_name=timezone_name,
            rank=False,
            quiet_ok=False,
            repo_root=root,
            generation_mode="live_dry_run_metadata_only",
            source_registry_label=_source_registry_label(sources_path, root),
            observation_safety_flag="live_dry_run",
            scan_id_prefix="live-dry-run-topic-scan",
            unresolved_reason="Live-source dry-run is metadata-only and requires manual source review before promotion.",
            unresolved_review_action="Inspect source URL, allowed fetch mode, timing, robots/rate-limit notes, and claim scope before enabling any live observation.",
            observation_label="live dry-run metadata observations",
        )
    except TopicDiscoveryError as exc:
        raise LiveDryRunError(str(exc)) from exc
    return LiveDryRunResult(output_path=result.output_path, candidates=result.candidates)


def _validate_live_dry_run_registry(source_registry: dict[str, Any]) -> None:
    source_ids = _registry_source_ids(source_registry)
    if not source_ids:
        raise LiveDryRunError("live dry-run source registry must contain at least one source")
    for index, source in enumerate(source_registry.get("sources", [])):
        path = f"sources[{index}]"
        if not isinstance(source, dict):
            raise LiveDryRunError(f"{path} must be an object")
        if source.get("enabled") is not False:
            raise LiveDryRunError(f"{path}.enabled must remain false")
        if source.get("fetch_mode") != "disabled":
            raise LiveDryRunError(f"{path}.fetch_mode must remain disabled")
        if source.get("manual_review_required") is not True:
            raise LiveDryRunError(f"{path}.manual_review_required must be true")
        if source.get("attribution_required") is not True:
            raise LiveDryRunError(f"{path}.attribution_required must be true")
        _require_positive_int(source, "max_requests_per_run", path)
        _require_non_negative_int(source, "min_seconds_between_requests", path)
        _require_positive_int(source, "timeout_seconds", path)
        _reject_disallowed_markers(source, path)


def _metadata_observations_from_registry(source_registry: dict[str, Any], scan_date: str) -> list[dict[str, Any]]:
    observed_at = f"{scan_date}T04:00:00+08:00"
    observations: list[dict[str, Any]] = []
    for source in sorted(source_registry.get("sources", []), key=lambda item: str(item.get("source_id", ""))):
        if not isinstance(source, dict):
            continue
        source_id = str(source["source_id"])
        title = str(source["title"])
        allowed_fetch_mode = str(source.get("allowed_fetch_mode", "disabled"))
        observations.append(
            {
                "observation_id": "live-dry-run-" + _slug(source_id),
                "source_id": source_id,
                "title": "Live dry-run readiness check: " + title,
                "url": str(source["url"]),
                "observed_at": observed_at,
                "published_at": None,
                "retrieved_at": observed_at,
                "source_type": str(source["source_type"]),
                "raw_signal_type": "live_source_metadata",
                "summary": (
                    "Metadata-only readiness artifact for a disabled live source. "
                    "No page content was fetched, no live observation was made, and no report claim is being created."
                ),
                "topic_type": _topic_type_from_source(source),
                "candidate_status": "unresolved",
                "companies": [],
                "models": [],
                "regions": [],
                "material_update_score": 1,
                "importance_score": 1,
                "novelty_score": 1,
                "confidence": "low",
                "uncertainty_notes": [
                    "Live fetching is disabled; this candidate only records source readiness metadata.",
                    "Allowed future fetch mode is documented as " + allowed_fetch_mode + " but is not executed.",
                    "Manual review is required before any live observation or report promotion.",
                ],
                "safety_flags": list(LIVE_DRY_RUN_SAFETY_FLAGS),
                "dedup_key": "live-dry-run-" + _slug(source_id),
                "related_observation_ids": [],
            }
        )
    return observations


def _topic_type_from_source(source: dict[str, Any]) -> str:
    category_id = str(source.get("category_id", "")).lower()
    source_type = str(source.get("source_type", "")).lower()
    if "research" in category_id or source_type == "paper":
        return "research"
    if "repository" in category_id or source_type == "repository":
        return "developer_tooling"
    if "security" in category_id:
        return "security"
    if "regulatory" in category_id or source_type == "regulatory":
        return "policy"
    if "benchmark" in category_id:
        return "benchmark"
    if "model" in category_id:
        return "model_release"
    if "changelog" in category_id or "announcement" in category_id or source_type == "official":
        return "product_release"
    return "other"


def _source_registry_label(path: str | Path, repo_root: Path) -> str:
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = repo_root / resolved
    try:
        return resolved.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(path).replace("\\", "/")


def _require_positive_int(source: dict[str, Any], field: str, path: str) -> None:
    value = source.get(field)
    if not isinstance(value, int) or value < 1:
        raise LiveDryRunError(f"{path}.{field} must be a positive integer")


def _require_non_negative_int(source: dict[str, Any], field: str, path: str) -> None:
    value = source.get(field)
    if not isinstance(value, int) or value < 0:
        raise LiveDryRunError(f"{path}.{field} must be a non-negative integer")


def _reject_disallowed_markers(source: dict[str, Any], path: str) -> None:
    for field in ("url", "title", "publisher", "robots_policy_note", "rate_limit_note", "safety_notes"):
        value = source.get(field)
        if not isinstance(value, str):
            continue
        lowered = value.lower()
        if any(marker in lowered for marker in DISALLOWED_MARKERS):
            raise LiveDryRunError(f"{path}.{field} contains a disallowed live dry-run marker")
    rules = source.get("disallowed_content_rules", [])
    if not isinstance(rules, list):
        raise LiveDryRunError(f"{path}.disallowed_content_rules must be an array")
    for index, rule in enumerate(rules):
        if not isinstance(rule, str):
            raise LiveDryRunError(f"{path}.disallowed_content_rules[{index}] must be a string")
        lowered = rule.lower()
        if any(marker in lowered for marker in ("raw_html_snapshot", "raw-html-snapshot")):
            raise LiveDryRunError(f"{path}.disallowed_content_rules[{index}] contains a disallowed raw HTML marker")


def _slug(value: str) -> str:
    chars: list[str] = []
    for char in value.lower():
        if char.isalnum():
            chars.append(char)
        elif chars and chars[-1] != "-":
            chars.append("-")
    return "".join(chars).strip("-")[:64] or "source"
