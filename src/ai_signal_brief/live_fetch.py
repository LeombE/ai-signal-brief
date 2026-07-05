from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, time
from email.utils import parsedate_to_datetime
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from typing import Any, Callable
from urllib import request
from xml.etree import ElementTree
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .validation import DATE_ONLY, _public_https_host, find_public_safety_issues, find_secret_like_values


FETCH_USER_AGENT = "ai-signal-brief/0.1 public-source-review"
MAX_RESPONSE_BYTES = 1_000_000
VALID_FETCH_MODES = {"rss", "atom", "html_metadata"}
VALID_SOURCE_TYPES = {"official", "paper", "repository", "regulatory", "news", "social", "other"}
BLOCKED_SOURCE_MARKERS = (
    "login_required",
    "paywall",
    "private_repo",
    "signed_url",
    "raw_html_archive",
)
RAW_HTML_RE = re.compile(r"(?is)<\s*(?:html|body|script|style|iframe|form)\b")


class LiveFetchError(Exception):
    """Raised when live source configuration or fetching fails."""


@dataclass(frozen=True)
class LiveSource:
    source_id: str
    source_name: str
    publisher: str
    url: str
    source_type: str
    priority: int
    reliability_tier: str
    fetch_mode: str
    max_items: int
    timeout_seconds: int
    source_confidence: str
    enabled: bool


@dataclass(frozen=True)
class LiveFetchResult:
    observations: list[dict[str, Any]]
    source_errors: list[dict[str, str]]
    retrieved_at: str


Reader = Callable[[str, int], bytes]


def load_live_sources_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise LiveFetchError(f"source config does not exist: {config_path}") from exc
    except json.JSONDecodeError as exc:
        raise LiveFetchError(f"source config is not valid JSON: {exc}") from exc
    validate_live_sources_config(data)
    return data


def validate_live_sources_config(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        raise LiveFetchError("live source config must be a JSON object")
    for field in ("schema_version", "source_policy", "sources"):
        if field not in data:
            errors.append(f"$.{field} is required")
    sources = data.get("sources")
    if not isinstance(sources, list) or not sources:
        errors.append("$.sources must be a non-empty array")
    else:
        seen: set[str] = set()
        for index, source in enumerate(sources):
            _validate_source(source, index, seen, errors)
    errors.extend(_safety_errors(data))
    if errors:
        raise LiveFetchError("; ".join(errors))
    return errors


def fetch_live_observations(
    *,
    sources_path: str | Path,
    report_date: str,
    timezone_name: str,
    max_items: int,
    lookback_hours: int,
    reader: Reader | None = None,
    retrieved_at: str | None = None,
) -> LiveFetchResult:
    _validate_date(report_date)
    zone = _zone(timezone_name)
    retrieved = retrieved_at or datetime.now(zone).replace(microsecond=0).isoformat()
    cutoff = _cutoff(report_date, timezone_name, lookback_hours)
    config = load_live_sources_config(sources_path)
    sources = [_source_from_dict(item) for item in config["sources"] if isinstance(item, dict) and item.get("enabled", True)]
    observations: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    read = reader or _read_url

    for source in sorted(sources, key=lambda item: (item.priority, item.source_id)):
        try:
            payload = read(source.url, source.timeout_seconds)
            text = payload.decode("utf-8", errors="replace")
            source_observations = _parse_source_payload(source, text, retrieved, cutoff)
            observations.extend(source_observations[: max(1, min(source.max_items, max_items))])
        except Exception as exc:  # noqa: BLE001 - source errors are reported, not fatal.
            errors.append({"source_id": source.source_id, "url": source.url, "error": _safe_error(exc)})

    observations = _dedupe_observations(observations)
    observations.sort(key=lambda item: (str(item.get("published_at") or ""), str(item.get("source_id")), str(item.get("title"))), reverse=True)
    return LiveFetchResult(observations=observations[:max_items], source_errors=errors, retrieved_at=retrieved)


def _validate_source(source: Any, index: int, seen: set[str], errors: list[str]) -> None:
    path = f"$.sources[{index}]"
    if not isinstance(source, dict):
        errors.append(f"{path} must be an object")
        return
    required = (
        "id",
        "name",
        "publisher",
        "url",
        "source_type",
        "priority",
        "reliability_tier",
        "fetch_mode",
        "enabled",
        "max_items",
        "timeout_seconds",
        "source_confidence",
    )
    for field in required:
        if field not in source:
            errors.append(f"{path}.{field} is required")
    source_id = source.get("id")
    if not isinstance(source_id, str) or not source_id:
        errors.append(f"{path}.id must be a non-empty string")
    elif source_id in seen:
        errors.append(f"{path}.id duplicates source id '{source_id}'")
    else:
        seen.add(source_id)
    url = source.get("url")
    if not isinstance(url, str) or _public_https_host(url) is None:
        errors.append(f"{path}.url must be public HTTPS")
    if isinstance(url, str) and _url_has_query_or_fragment_or_credentials(url):
        errors.append(f"{path}.url must not contain credentials, query, or fragment")
    if source.get("source_type") not in VALID_SOURCE_TYPES:
        errors.append(f"{path}.source_type is not supported")
    if source.get("fetch_mode") not in VALID_FETCH_MODES:
        errors.append(f"{path}.fetch_mode must be one of: {', '.join(sorted(VALID_FETCH_MODES))}")
    if not isinstance(source.get("priority"), int) or source.get("priority") < 1:
        errors.append(f"{path}.priority must be a positive integer")
    if not isinstance(source.get("max_items"), int) or not 1 <= source.get("max_items") <= 20:
        errors.append(f"{path}.max_items must be an integer from 1 to 20")
    if not isinstance(source.get("timeout_seconds"), int) or not 1 <= source.get("timeout_seconds") <= 30:
        errors.append(f"{path}.timeout_seconds must be an integer from 1 to 30")
    if source.get("enabled") is not True:
        errors.append(f"{path}.enabled must be true for this explicit live report source config")
    if source.get("source_confidence") not in {"high", "medium", "low"}:
        errors.append(f"{path}.source_confidence must be high, medium, or low")
    _validate_blocked_markers(source, path, errors)


def _validate_blocked_markers(source: dict[str, Any], path: str, errors: list[str]) -> None:
    text = json.dumps(source, ensure_ascii=False).lower()
    for marker in BLOCKED_SOURCE_MARKERS:
        if marker in text:
            errors.append(f"{path} contains blocked source marker: {marker}")


def _source_from_dict(source: dict[str, Any]) -> LiveSource:
    return LiveSource(
        source_id=str(source["id"]),
        source_name=str(source["name"]),
        publisher=str(source["publisher"]),
        url=str(source["url"]),
        source_type=str(source["source_type"]),
        priority=int(source["priority"]),
        reliability_tier=str(source["reliability_tier"]),
        fetch_mode=str(source["fetch_mode"]),
        max_items=int(source["max_items"]),
        timeout_seconds=int(source["timeout_seconds"]),
        source_confidence=str(source["source_confidence"]),
        enabled=bool(source["enabled"]),
    )


def _read_url(url: str, timeout_seconds: int) -> bytes:
    if _public_https_host(url) is None or _url_has_query_or_fragment_or_credentials(url):
        raise LiveFetchError("source URL must be public HTTPS without credentials, query, or fragment")
    req = request.Request(url, headers={"User-Agent": FETCH_USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, text/xml, text/html;q=0.8"})
    with request.urlopen(req, timeout=timeout_seconds) as response:  # nosec B310 - explicit allowlisted public HTTPS fetcher.
        data = response.read(MAX_RESPONSE_BYTES + 1)
    if len(data) > MAX_RESPONSE_BYTES:
        raise LiveFetchError("source response exceeded safety byte limit")
    return data


def _parse_source_payload(source: LiveSource, text: str, retrieved_at: str, cutoff: datetime) -> list[dict[str, Any]]:
    if source.fetch_mode in {"rss", "atom"}:
        observations = _parse_feed(source, text, retrieved_at, cutoff)
        if observations:
            return observations
    return _parse_html_metadata(source, text, retrieved_at)


def _parse_feed(source: LiveSource, text: str, retrieved_at: str, cutoff: datetime) -> list[dict[str, Any]]:
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError:
        return []
    observations: list[dict[str, Any]] = []
    entries = list(root.findall(".//item")) or list(root.findall(".//{http://www.w3.org/2005/Atom}entry"))
    for index, entry in enumerate(entries):
        title = _xml_text(entry, ("title", "{http://www.w3.org/2005/Atom}title"))
        link = _xml_text(entry, ("link", "guid")) or _atom_link(entry) or source.url
        summary = _xml_text(entry, ("description", "summary", "{http://www.w3.org/2005/Atom}summary", "{http://www.w3.org/2005/Atom}content"))
        published_raw = _xml_text(entry, ("pubDate", "published", "updated", "{http://www.w3.org/2005/Atom}published", "{http://www.w3.org/2005/Atom}updated"))
        published_at = _parse_datetime(published_raw)
        if published_at is not None and published_at < cutoff:
            continue
        if not title:
            continue
        observations.append(_observation(source, title, link, published_at, retrieved_at, summary, index))
    return observations


def _parse_html_metadata(source: LiveSource, text: str, retrieved_at: str) -> list[dict[str, Any]]:
    parser = _MetadataParser()
    parser.feed(text[:200_000])
    title = parser.title or source.source_name
    summary = parser.description or f"Public source metadata fetched from {source.publisher}."
    return [_observation(source, title, source.url, None, retrieved_at, summary, 0)]


def _observation(source: LiveSource, title: str, url: str, published_at: datetime | None, retrieved_at: str, summary: str, index: int) -> dict[str, Any]:
    safe_url = url if isinstance(url, str) and _public_https_host(url) is not None else source.url
    clean_title = _clean_text(title, limit=220)
    clean_summary = _clean_text(summary, limit=600)
    if RAW_HTML_RE.search(clean_summary):
        clean_summary = _clean_text(re.sub(r"<[^>]+>", " ", clean_summary), limit=600)
    companies = _detect_companies(clean_title + " " + clean_summary + " " + source.publisher)
    models = _detect_models(clean_title + " " + clean_summary)
    topic_type = _topic_type(clean_title + " " + clean_summary)
    published_text = published_at.isoformat() if published_at else None
    seed = f"{source.source_id}|{safe_url}|{clean_title}|{published_text or retrieved_at}|{index}"
    return {
        "source_id": source.source_id,
        "source_name": source.source_name,
        "source_type": source.source_type,
        "publisher": source.publisher,
        "title": clean_title,
        "url": safe_url,
        "published_at": published_text,
        "retrieved_at": retrieved_at,
        "company_entities": companies,
        "models": models,
        "summary": clean_summary,
        "excerpt": clean_summary,
        "content_hash": hashlib.sha256(seed.encode("utf-8")).hexdigest(),
        "source_confidence": source.source_confidence,
        "evidence_notes": _evidence_notes(source, published_at),
        "raw_signal_type": _raw_signal_type(source.source_type, topic_type),
        "topic_type": topic_type,
    }


def _xml_text(entry: ElementTree.Element, names: tuple[str, ...]) -> str:
    for name in names:
        child = entry.find(name)
        if child is not None and child.text:
            return child.text.strip()
    return ""


def _atom_link(entry: ElementTree.Element) -> str:
    for link in entry.findall("{http://www.w3.org/2005/Atom}link"):
        href = link.attrib.get("href")
        if href:
            return href
    return ""


def _parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ZoneInfo("UTC"))
        return parsed
    except (TypeError, ValueError, IndexError):
        pass
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ZoneInfo("UTC"))
        return parsed
    except ValueError:
        return None


def _cutoff(report_date: str, timezone_name: str, lookback_hours: int) -> datetime:
    zone = _zone(timezone_name)
    day = datetime.strptime(report_date, "%Y-%m-%d").date()
    end = datetime.combine(day, time(hour=23, minute=59, second=59), tzinfo=zone)
    return end - timedelta(hours=max(1, lookback_hours))


def _zone(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise LiveFetchError("timezone is invalid") from exc


def _validate_date(value: str) -> None:
    if not isinstance(value, str) or not DATE_ONLY.match(value):
        raise LiveFetchError("date must be YYYY-MM-DD")
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise LiveFetchError("date must be YYYY-MM-DD") from exc


def _clean_text(value: str, *, limit: int) -> str:
    text = html.unescape(value or "")
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit].strip()


def _detect_companies(text: str) -> list[str]:
    patterns = (
        ("OpenAI", r"\bOpenAI\b|\bGPT\b|\bChatGPT\b"),
        ("Anthropic", r"\bAnthropic\b|\bClaude\b"),
        ("Google", r"\bGoogle\b|\bGemini\b|\bDeepMind\b"),
        ("Meta", r"\bMeta\b|\bLlama\b"),
        ("Mistral", r"\bMistral\b"),
        ("Cohere", r"\bCohere\b|\bCommand\b"),
        ("xAI", r"\bxAI\b|\bGrok\b"),
        ("Hugging Face", r"\bHugging Face\b|\bTransformers\b"),
    )
    return [name for name, pattern in patterns if re.search(pattern, text, re.IGNORECASE)]


def _detect_models(text: str) -> list[str]:
    names = ("GPT", "ChatGPT", "Claude", "Gemini", "Llama", "Mistral", "Command", "Grok", "DeepSeek", "Qwen", "Kimi")
    found = []
    for name in names:
        if re.search(r"\b" + re.escape(name) + r"[\w.-]*", text, re.IGNORECASE):
            found.append(name)
    return sorted(set(found))


def _topic_type(text: str) -> str:
    lowered = text.lower()
    if any(word in lowered for word in ("model", "gpt", "claude", "gemini", "llama", "mistral", "grok")):
        return "model_release"
    if any(word in lowered for word in ("api", "developer", "sdk", "platform")):
        return "developer_tooling"
    if any(word in lowered for word in ("safety", "security", "vulnerability")):
        return "security"
    if any(word in lowered for word in ("policy", "regulation", "governance")):
        return "policy"
    if any(word in lowered for word in ("research", "paper", "benchmark")):
        return "research"
    return "other"


def _raw_signal_type(source_type: str, topic_type: str) -> str:
    if source_type == "official":
        return "official_release"
    if topic_type == "research":
        return "research_metadata"
    if source_type == "repository":
        return "repository_metadata"
    if source_type == "regulatory":
        return "regulatory_metadata"
    return "news_metadata"


def _evidence_notes(source: LiveSource, published_at: datetime | None) -> list[str]:
    notes = [f"Fetched from allowlisted public HTTPS source: {source.publisher}."]
    if published_at is None:
        notes.append("Published time was not available or could not be parsed; manual timing review is required.")
    if source.source_type != "official":
        notes.append("Non-official source; use as context unless corroborated by primary evidence.")
    return notes


def _dedupe_observations(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped = []
    for observation in observations:
        key = _dedup_key(observation)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(observation)
    return deduped


def _dedup_key(observation: dict[str, Any]) -> str:
    title = re.sub(r"[^a-z0-9]+", "-", str(observation.get("title", "")).lower()).strip("-")
    return f"{observation.get('source_id')}:{title[:80]}"


def _url_has_query_or_fragment_or_credentials(value: str) -> bool:
    if not value.startswith("https://"):
        return True
    tail = value[len("https://"):]
    authority = tail.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    return "@" in authority or "?" in value or "#" in value


def _safety_errors(data: Any) -> list[str]:
    errors = []
    errors.extend(find_secret_like_values(data))
    errors.extend(find_public_safety_issues(data))
    for text in _iter_strings(data):
        if RAW_HTML_RE.search(text):
            errors.append("source config contains raw HTML marker")
    return errors


def _iter_strings(value: Any) -> list[str]:
    strings: list[str] = []
    if isinstance(value, str):
        strings.append(value)
    elif isinstance(value, dict):
        for child in value.values():
            strings.extend(_iter_strings(child))
    elif isinstance(value, list):
        for child in value:
            strings.extend(_iter_strings(child))
    return strings


def _safe_error(exc: Exception) -> str:
    return re.sub(r"\s+", " ", str(exc))[:240] or exc.__class__.__name__


class _MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_title = False
        self._title_parts: list[str] = []
        self.description = ""

    @property
    def title(self) -> str:
        return _clean_text(" ".join(self._title_parts), limit=220)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.lower()
        if lowered == "title":
            self._in_title = True
        if lowered == "meta":
            attrs_dict = {key.lower(): value or "" for key, value in attrs}
            name = attrs_dict.get("name", "").lower() or attrs_dict.get("property", "").lower()
            if name in {"description", "og:description"} and attrs_dict.get("content") and not self.description:
                self.description = _clean_text(attrs_dict["content"], limit=600)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_parts.append(data)