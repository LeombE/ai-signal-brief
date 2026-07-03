from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

from .fetch_adapter import FetchAdapterError, load_replay_fixture, replay_fixture_to_observation
from .topic_discovery import (
    TopicDiscoveryError,
    TopicDiscoveryResult,
    _load_valid_source_registry,
    _registry_source_ids,
    discover_topics_from_observation_data,
)


class ReplayDiscoveryError(TopicDiscoveryError):
    """Raised when replay-only topic discovery cannot run safely."""


def discover_topics_from_replay(
    *,
    scan_date: str,
    sources_path: str | Path,
    replay_dir: str | Path,
    output_path: str | Path,
    timezone_name: str = "Asia/Kuala_Lumpur",
    rank: bool = False,
    repo_root: str | Path | None = None,
) -> TopicDiscoveryResult:
    try:
        return _discover_topics_from_replay(
            scan_date=scan_date,
            sources_path=sources_path,
            replay_dir=replay_dir,
            output_path=output_path,
            timezone_name=timezone_name,
            rank=rank,
            repo_root=repo_root,
        )
    except ReplayDiscoveryError:
        raise
    except TopicDiscoveryError as exc:
        raise ReplayDiscoveryError(str(exc)) from exc


def _discover_topics_from_replay(
    *,
    scan_date: str,
    sources_path: str | Path,
    replay_dir: str | Path,
    output_path: str | Path,
    timezone_name: str,
    rank: bool,
    repo_root: str | Path | None,
) -> TopicDiscoveryResult:
    root = Path(repo_root) if repo_root is not None else Path.cwd()
    source_registry = _load_valid_source_registry(sources_path)
    _ensure_live_registry_entries_remain_disabled(source_registry)
    registry_source_ids = _registry_source_ids(source_registry)
    fixture_paths = _replay_fixture_paths(replay_dir, root)

    observations: list[dict[str, Any]] = []
    for fixture_path in fixture_paths:
        try:
            fixture = load_replay_fixture(fixture_path)
            result = replay_fixture_to_observation(fixture_path, source_id=str(fixture["source_id"]))
        except FetchAdapterError as exc:
            raise ReplayDiscoveryError(f"invalid replay fixture {fixture_path.name}: {exc}") from exc
        observation = result.observation
        source_id = str(observation["source_id"])
        if source_id not in registry_source_ids:
            raise ReplayDiscoveryError(f"replay fixture {fixture_path.name} source_id references unknown topic source")
        observations.append(_topic_observation_from_replay(observation))

    return discover_topics_from_observation_data(
        scan_date=scan_date,
        sources_path=sources_path,
        source_registry=source_registry,
        observations=observations,
        output_path=output_path,
        timezone_name=timezone_name,
        rank=rank,
        quiet_ok=False,
        repo_root=root,
        generation_mode="replay_fixture_observations_only",
        source_registry_label=_source_registry_label(sources_path, root),
        observation_safety_flag="replay_observation",
        scan_id_prefix="replay-topic-scan",
        unresolved_reason="Replay fixture observation requires manual source review before publication.",
        unresolved_review_action="Review fixture source metadata, timing, and claim scope before promotion.",
        observation_label="replay_observations",
    )

def _replay_fixture_paths(replay_dir: str | Path, repo_root: Path) -> list[Path]:
    directory = _resolve_repo_path(replay_dir, repo_root, "replay directory")
    if not directory.exists() or not directory.is_dir():
        raise ReplayDiscoveryError("replay directory not found")
    paths = sorted(path for path in directory.glob("*.json") if path.is_file())
    if not paths:
        raise ReplayDiscoveryError("replay directory contains no JSON fixtures")
    return paths


def _resolve_repo_path(path: str | Path, repo_root: Path, label: str) -> Path:
    raw_path = str(path)
    if not raw_path or "://" in raw_path or raw_path.startswith(("~", "\\")):
        raise ReplayDiscoveryError(f"unsafe {label} path rejected")
    root = repo_root.resolve()
    candidate = Path(path)
    if not candidate.is_absolute():
        normalized = raw_path.replace("\\", "/")
        pure_path = PurePosixPath(normalized)
        if any(part in {"", ".."} for part in pure_path.parts):
            raise ReplayDiscoveryError(f"unsafe {label} path rejected")
        candidate = root / Path(*pure_path.parts)
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ReplayDiscoveryError(f"{label} path must stay inside the repository") from exc
    return resolved


def _source_registry_label(path: str | Path, repo_root: Path) -> str:
    resolved = _resolve_repo_path(path, repo_root, "source registry")
    return resolved.relative_to(repo_root.resolve()).as_posix()


def _ensure_live_registry_entries_remain_disabled(source_registry: dict[str, Any]) -> None:
    for source in source_registry.get("sources", []):
        if not isinstance(source, dict):
            continue
        live_like = "source_id" in source or "fetch_mode" in source or "enabled" in source
        if not live_like:
            continue
        if source.get("enabled") is not False:
            raise ReplayDiscoveryError("live source registry entries must remain enabled: false")
        if source.get("fetch_mode") != "disabled":
            raise ReplayDiscoveryError("live source registry entries must remain fetch_mode: disabled")


def _topic_observation_from_replay(observation: dict[str, Any]) -> dict[str, Any]:
    raw_signal_type = str(observation["raw_signal_type"])
    source_type = str(observation["source_type"])
    source_confidence = str(observation.get("source_confidence", "medium"))
    return {
        "observation_id": str(observation["observation_id"]),
        "source_id": str(observation["source_id"]),
        "title": str(observation["title"]),
        "url": str(observation["url"]),
        "observed_at": str(observation["observed_at"]),
        "published_at": observation.get("published_at"),
        "retrieved_at": observation.get("retrieved_at"),
        "source_type": source_type,
        "raw_signal_type": raw_signal_type,
        "summary": str(observation["summary"]),
        "topic_type": _topic_type(raw_signal_type, source_type),
        "candidate_status": "unresolved",
        "companies": _entity_list(observation, "companies"),
        "models": _entity_list(observation, "models"),
        "regions": _entity_list(observation, "regions"),
        "material_update_score": _material_score(raw_signal_type, source_type),
        "importance_score": 3 if source_confidence == "high" else 2,
        "novelty_score": 2,
        "confidence": source_confidence,
        "source_confidence": source_confidence,
        "uncertainty_notes": [
            "Replay fixture observation is metadata-only and requires manual source review.",
            "Topic remains unresolved until a human reviewer verifies source timing and claim scope.",
        ],
        "safety_flags": sorted(set(list(observation.get("safety_flags", [])) + ["replay_observation", "manual_review_required", "no_live_fetch"])),
        "dedup_key": _dedup_key(observation),
        "related_observation_ids": [],
        "content_hash": str(observation["content_hash"]),
    }


def _entity_list(observation: dict[str, Any], field: str) -> list[str]:
    entities = observation.get("entities", {})
    if not isinstance(entities, dict):
        return []
    value = entities.get(field, [])
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _topic_type(raw_signal_type: str, source_type: str) -> str:
    signal = raw_signal_type.lower()
    if signal == "model_card":
        return "model_release"
    if signal in {"repository_release", "changelog", "release_notes", "official_release"}:
        return "product_release"
    if signal == "security_advisory":
        return "security"
    if signal == "research_paper" or source_type == "paper":
        return "research"
    if signal == "regulatory_metadata" or source_type == "regulatory":
        return "policy"
    return "other"


def _material_score(raw_signal_type: str, source_type: str) -> int:
    if raw_signal_type in {"official_release", "release_notes", "model_card", "security_advisory", "repository_release", "changelog"}:
        return 3
    if source_type in {"official", "paper", "repository", "regulatory"}:
        return 3
    return 2


def _dedup_key(observation: dict[str, Any]) -> str:
    seed = f"{observation.get('source_id', '')}-{observation.get('raw_signal_type', '')}-{observation.get('title', '')}"
    return _slug(seed)


def _slug(value: str) -> str:
    chars: list[str] = []
    for char in value.lower():
        if char.isalnum():
            chars.append(char)
        elif chars and chars[-1] != "-":
            chars.append("-")
    return "".join(chars).strip("-")[:80] or "replay-observation"