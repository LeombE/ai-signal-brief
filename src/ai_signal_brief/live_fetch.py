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
from urllib import parse, request
from xml.etree import ElementTree
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .validation import DATE_ONLY, _public_https_host, find_public_safety_issues, find_secret_like_values


FETCH_USER_AGENT = "ai-signal-brief/0.1 public-source-review"
MAX_RESPONSE_BYTES = 1_000_000
MAX_HTML_PARSE_BYTES = 350_000
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
FEED_MIME_MARKERS = ("rss", "atom", "xml")
ARTICLE_PATH_MARKERS = (
    "news",
    "blog",
    "post",
    "posts",
    "article",
    "articles",
    "research",
    "updates",
    "release",
    "releases",
    "changelog",
    "announcements",
    "discover",
)
NAVIGATION_PATH_MARKERS = (
    "privacy",
    "terms",
    "cookies",
    "login",
    "signin",
    "sign-in",
    "signup",
    "subscribe",
    "newsletter",
    "careers",
    "jobs",
    "contact",
    "about",
    "tag",
    "tags",
    "category",
    "categories",
    "authors",
    "pricing",
    "legal",
)
GENERIC_TITLE_RE = re.compile(
    r"^(?:news|blog|updates|research|articles|all posts|latest|resources|company|pricing|careers|home|homepage)(?:\s*[|:-].*)?$",
    re.IGNORECASE,
)
MOJIBAKE_REPLACEMENTS = {
    "????????": "-",
    "????????": "-",
    "????????": "-",
    "????????": "'",
    "???????": "'",
    "???????": '"',
    "???????": '"',
    "???": "-",
    "???": "-",
    "???": "'",
    "???": "'",
    "???": '"',
    "???": '"',
    "? ": " ",
    "?": "",
}


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
    feed_url: str | None = None


@dataclass(frozen=True)
class LiveFetchResult:
    observations: list[dict[str, Any]]
    source_errors: list[dict[str, str]]
    retrieved_at: str


@dataclass(frozen=True)
class _ArticleLink:
    url: str
    text: str


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
            source_observations = _parse_source_payload(source, text, retrieved, cutoff, read)
            observations.extend(source_observations[: max(1, min(source.max_items, max_items))])
        except Exception as exc:  # noqa: BLE001 - source errors are reported, not fatal.
            errors.append({"source_id": source.source_id, "url": source.url, "error": _safe_error(exc)})

    observations = _dedupe_observations(observations)
    observations.sort(key=_observation_sort_key, reverse=True)
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
    _validate_public_fetch_url(url, f"{path}.url", errors)
    feed_url = source.get("feed_url")
    if feed_url is not None:
        _validate_public_fetch_url(feed_url, f"{path}.feed_url", errors)
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


def _validate_public_fetch_url(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, str) or _public_https_host(value) is None:
        errors.append(f"{path} must be public HTTPS")
    if isinstance(value, str) and _url_has_query_or_fragment_or_credentials(value):
        errors.append(f"{path} must not contain credentials, query, or fragment")


def _validate_blocked_markers(source: dict[str, Any], path: str, errors: list[str]) -> None:
    text = json.dumps(source, ensure_ascii=False).lower()
    for marker in BLOCKED_SOURCE_MARKERS:
        if marker in text:
            errors.append(f"{path} contains blocked source marker: {marker}")


def _source_from_dict(source: dict[str, Any]) -> LiveSource:
    feed_url = source.get("feed_url")
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
        feed_url=str(feed_url) if isinstance(feed_url, str) and feed_url else None,
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


def _parse_source_payload(source: LiveSource, text: str, retrieved_at: str, cutoff: datetime, reader: Reader) -> list[dict[str, Any]]:
    if source.fetch_mode in {"rss", "atom"} or _looks_like_feed(text):
        observations = _parse_feed(source, text, retrieved_at, cutoff, source.url)
        if observations:
            return observations

    parser = _MetadataParser(base_url=source.url)
    parser.feed(text[:MAX_HTML_PARSE_BYTES])

    feed_urls = _preferred_feed_urls(source, parser.feed_links)
    for feed_url in feed_urls:
        observations = _try_parse_feed_url(source, feed_url, retrieved_at, cutoff, reader)
        if observations:
            return observations

    article_observations = _parse_html_article_cards(source, parser, retrieved_at, cutoff)
    if article_observations:
        return article_observations
    return _parse_html_metadata(source, parser, retrieved_at)


def _looks_like_feed(text: str) -> bool:
    prefix = text.lstrip()[:300].lower()
    return prefix.startswith("<?xml") or prefix.startswith("<rss") or prefix.startswith("<feed")


def _preferred_feed_urls(source: LiveSource, discovered: list[str]) -> list[str]:
    candidates: list[str] = []
    if source.feed_url:
        candidates.append(source.feed_url)
    candidates.extend(discovered)
    seen: set[str] = set()
    safe: list[str] = []
    for value in candidates:
        normalized = _normalize_public_url(value, base_url=source.url)
        if not normalized or normalized == source.url or normalized in seen:
            continue
        seen.add(normalized)
        safe.append(normalized)
    return safe[:3]


def _try_parse_feed_url(source: LiveSource, feed_url: str, retrieved_at: str, cutoff: datetime, reader: Reader) -> list[dict[str, Any]]:
    try:
        payload = reader(feed_url, source.timeout_seconds)
        text = payload.decode("utf-8", errors="replace")
    except Exception:
        return []
    return _parse_feed(source, text, retrieved_at, cutoff, feed_url)


def _parse_feed(source: LiveSource, text: str, retrieved_at: str, cutoff: datetime, base_url: str) -> list[dict[str, Any]]:
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError:
        return []
    observations: list[dict[str, Any]] = []
    entries = list(root.findall(".//item")) or list(root.findall(".//{http://www.w3.org/2005/Atom}entry"))
    for index, entry in enumerate(entries):
        title = _xml_text(entry, ("title", "{http://www.w3.org/2005/Atom}title"))
        link = _xml_text(entry, ("link", "guid")) or _atom_link(entry) or base_url
        link = _normalize_public_url(link, base_url=base_url) or base_url
        summary = _xml_text(entry, ("description", "summary", "{http://www.w3.org/2005/Atom}summary", "{http://www.w3.org/2005/Atom}content"))
        author = _xml_text(entry, ("author", "dc:creator", "{http://www.w3.org/2005/Atom}author"))
        published_raw = _xml_text(entry, ("pubDate", "published", "{http://www.w3.org/2005/Atom}published"))
        updated_raw = _xml_text(entry, ("updated", "{http://www.w3.org/2005/Atom}updated"))
        published_at = _parse_datetime(published_raw) or _parse_datetime(updated_raw)
        updated_at = _parse_datetime(updated_raw)
        if published_at is not None and published_at < cutoff:
            continue
        if not title or _is_generic_title(title) or _is_navigation_or_index_url(link, source.url):
            continue
        observations.append(
            _observation(
                source,
                title,
                link,
                published_at,
                updated_at,
                retrieved_at,
                summary,
                index,
                author=author,
                signal_level="article",
                raw_signal_type="feed_article",
            )
        )
    return observations


def _parse_html_article_cards(source: LiveSource, parser: _MetadataParser, retrieved_at: str, cutoff: datetime) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for index, link in enumerate(parser.article_links):
        url = _normalize_public_url(link.url, base_url=source.url)
        raw_title = _clean_text(link.text, limit=260)
        title = _article_title(raw_title)
        if not url or url in seen_urls:
            continue
        if _is_navigation_or_index_url(url, source.url) or _is_generic_title(title):
            continue
        if _is_product_or_category_url(url, source.url, title):
            continue
        if not _looks_like_article_url(url, source.url):
            continue
        published_at = _parse_date_from_text(raw_title)
        if published_at is not None and published_at < cutoff:
            continue
        seen_urls.add(url)
        summary = f"Article-level link discovered on {source.publisher} source page. Manual review is required to confirm publication date and claim scope."
        observations.append(
            _observation(
                source,
                title,
                url,
                published_at,
                None,
                retrieved_at,
                summary,
                index,
                author="",
                signal_level="article",
                raw_signal_type="html_article_card",
            )
        )
        if len(observations) >= source.max_items:
            break
    return observations


def _parse_html_metadata(source: LiveSource, parser: _MetadataParser, retrieved_at: str) -> list[dict[str, Any]]:
    title = parser.title or source.source_name
    summary = parser.description or f"Public source metadata fetched from {source.publisher}."
    return [
        _observation(
            source,
            title,
            source.url,
            None,
            None,
            retrieved_at,
            summary,
            0,
            author="",
            signal_level="source_homepage_fallback",
            raw_signal_type="homepage_metadata_fallback",
        )
    ]


def _observation(
    source: LiveSource,
    title: str,
    url: str,
    published_at: datetime | None,
    updated_at: datetime | None,
    retrieved_at: str,
    summary: str,
    index: int,
    *,
    author: str,
    signal_level: str,
    raw_signal_type: str,
) -> dict[str, Any]:
    safe_url = _normalize_public_url(url, base_url=source.url) or source.url
    clean_title = _clean_text(title, limit=220)
    clean_summary = _clean_text(summary, limit=600)
    if RAW_HTML_RE.search(clean_summary):
        clean_summary = _clean_text(re.sub(r"<[^>]+>", " ", clean_summary), limit=600)
    companies = _detect_companies(clean_title + " " + clean_summary + " " + source.publisher)
    models = _detect_models(clean_title + " " + clean_summary)
    topic_type = _topic_type(clean_title + " " + clean_summary)
    published_text = published_at.isoformat() if published_at else None
    updated_text = updated_at.isoformat() if updated_at else None
    seed = f"{source.source_id}|{safe_url}|{clean_title}|{published_text or updated_text or retrieved_at}|{signal_level}|{index}"
    return {
        "source_id": source.source_id,
        "source_name": source.source_name,
        "source_type": source.source_type,
        "publisher": source.publisher,
        "title": clean_title,
        "url": safe_url,
        "published_at": published_text,
        "updated_at": updated_text,
        "retrieved_at": retrieved_at,
        "author": _clean_text(author, limit=120) if author else None,
        "company_entities": companies,
        "models": models,
        "summary": clean_summary,
        "excerpt": clean_summary,
        "content_hash": hashlib.sha256(seed.encode("utf-8")).hexdigest(),
        "source_confidence": _fallback_confidence(source.source_confidence, signal_level),
        "source_priority": source.priority,
        "evidence_notes": _evidence_notes(source, published_at, signal_level),
        "raw_signal_type": raw_signal_type,
        "topic_type": topic_type,
        "signal_level": signal_level,
        "is_homepage_fallback": signal_level == "source_homepage_fallback",
    }


def _xml_text(entry: ElementTree.Element, names: tuple[str, ...]) -> str:
    for name in names:
        child = entry.find(name)
        if child is not None:
            text = "".join(child.itertext()).strip()
            if text:
                return text
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
    text = _repair_mojibake(html.unescape(value or ""))
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = text.replace("\u2014", "-").replace("\u2013", "-").replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit].strip()


def _repair_mojibake(value: str) -> str:
    text = value or ""
    for bad, good in MOJIBAKE_REPLACEMENTS.items():
        text = text.replace(bad, good)
    if any(marker in text for marker in ("?", "?", "??")):
        try:
            repaired = text.encode("latin-1", errors="ignore").decode("utf-8", errors="ignore")
        except UnicodeError:
            repaired = ""
        if repaired and len(repaired) >= max(8, int(len(text) * 0.55)):
            text = repaired
            for bad, good in MOJIBAKE_REPLACEMENTS.items():
                text = text.replace(bad, good)
    return text


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
        ("DeepSeek", r"\bDeepSeek\b"),
        ("Alibaba", r"\bQwen\b|\bAlibaba\b"),
        ("Moonshot AI", r"\bKimi\b|\bMoonshot\b"),
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
    if any(word in lowered for word in ("api", "developer", "sdk", "platform", "agent")):
        return "developer_tooling"
    if any(word in lowered for word in ("safety", "security", "vulnerability")):
        return "security"
    if any(word in lowered for word in ("policy", "regulation", "governance")):
        return "policy"
    if any(word in lowered for word in ("research", "paper", "benchmark", "eval")):
        return "research"
    return "other"


def _fallback_confidence(source_confidence: str, signal_level: str) -> str:
    if signal_level == "source_homepage_fallback":
        return "low"
    return source_confidence


def _evidence_notes(source: LiveSource, published_at: datetime | None, signal_level: str) -> list[str]:
    notes = [f"Fetched from allowlisted public HTTPS source: {source.publisher}."]
    if signal_level == "source_homepage_fallback":
        notes.append("Homepage metadata fallback only; do not treat as an article-level news item without manual source review.")
    elif signal_level == "article" and published_at is None:
        notes.append("Article-level link was detected, but published time was not available or could not be parsed; manual timing review is required.")
    if published_at is None and signal_level != "source_homepage_fallback":
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
    url = _canonical_url(str(observation.get("url", "")))
    title = re.sub(r"[^a-z0-9]+", "-", str(observation.get("title", "")).lower()).strip("-")[:100]
    return f"{url}|{title}"


def _observation_sort_key(item: dict[str, Any]) -> tuple[int, str, int, str]:
    signal_rank = 1 if item.get("signal_level") == "article" else 0
    published = str(item.get("published_at") or item.get("updated_at") or "")
    source_priority = int(item.get("source_priority") or 99)
    return (signal_rank, published, -source_priority, str(item.get("title") or ""))


def _normalize_public_url(value: str, *, base_url: str) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    joined = parse.urljoin(base_url, html.unescape(value.strip()))
    parsed = parse.urlsplit(joined)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        return None
    stripped = parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", "", ""))
    if _public_https_host(stripped) is None or _url_has_query_or_fragment_or_credentials(stripped):
        return None
    return stripped


def _canonical_url(value: str) -> str:
    parsed = parse.urlsplit(value)
    path = re.sub(r"/+$", "", parsed.path or "/") or "/"
    return parse.urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, "", ""))


def _url_has_query_or_fragment_or_credentials(value: str) -> bool:
    if not value.startswith("https://"):
        return True
    parsed = parse.urlsplit(value)
    return bool(parsed.username or parsed.password or parsed.query or parsed.fragment)


def _looks_like_article_url(url: str, source_url: str) -> bool:
    parsed = parse.urlsplit(url)
    source = parse.urlsplit(source_url)
    path = parsed.path.lower().strip("/")
    if not path or parsed.netloc.lower() != source.netloc.lower():
        return False
    parts = [part for part in path.split("/") if part]
    strict_markers = {"news", "blog", "post", "posts", "article", "articles", "changelog", "announcements"}
    if len(parts) >= 2 and any(marker in parts for marker in strict_markers):
        return True
    if len(parts) >= 3 and "discover" in parts and "blog" in parts:
        return True
    return False


def _looks_like_article_title(title: str) -> bool:
    clean = _clean_text(title, limit=220)
    if len(clean) < 14 or _is_generic_title(clean):
        return False
    lowered = clean.lower()
    return any(word in lowered for word in ("launch", "release", "introducing", "update", "model", "api", "research", "safety", "available", "new"))


def _article_title(value: str) -> str:
    text = _clean_text(value, limit=220)
    text = re.sub(r"^(?:read|learn more about|watch|view)\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^(?:product|research|announcements?|company|featured)\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(
        r"^(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{1,2},\s+20\d{2}\s+",
        "",
        text,
        flags=re.IGNORECASE,
    )
    return _clean_text(text, limit=220)


def _parse_date_from_text(value: str) -> datetime | None:
    match = re.search(
        r"\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{1,2},\s+20\d{2})\b",
        value,
        re.IGNORECASE,
    )
    if not match:
        return None
    try:
        parsed = datetime.strptime(match.group(1).replace("Sept", "Sep"), "%b %d, %Y")
    except ValueError:
        try:
            parsed = datetime.strptime(match.group(1).replace("Sept", "Sep"), "%B %d, %Y")
        except ValueError:
            return None
    return parsed.replace(tzinfo=ZoneInfo("UTC"))


def _is_product_or_category_url(url: str, source_url: str, title: str) -> bool:
    parsed = parse.urlsplit(url)
    source = parse.urlsplit(source_url)
    if parsed.netloc.lower() != source.netloc.lower():
        return True
    path = parsed.path.lower().strip("/")
    parts = [part for part in path.split("/") if part]
    if not parts:
        return True
    if len(parts) == 1:
        return True
    if parts[0] in {"products", "product", "platform", "solutions", "industry", "models", "model", "grok"}:
        return True
    if parts[-1] in {"security", "research", "product", "products", "models", "api", "studio", "transcribe"} and len(parts) <= 2:
        return True
    if title.lower() in {"security", "research", "models", "api", "studio", "transcribe"}:
        return True
    return False


def _is_navigation_or_index_url(url: str, source_url: str) -> bool:
    parsed = parse.urlsplit(url)
    source = parse.urlsplit(source_url)
    if parsed.netloc.lower() != source.netloc.lower():
        return True
    path = parsed.path.lower().strip("/")
    if not path:
        return True
    parts = [part for part in path.split("/") if part]
    if len(parts) == 1 and parts[0] in ARTICLE_PATH_MARKERS:
        return True
    if any(part in NAVIGATION_PATH_MARKERS for part in parts):
        return True
    if parts and parts[-1] in {"page", "index"}:
        return True
    return False


def _is_generic_title(title: str) -> bool:
    clean = _clean_text(title, limit=220)
    if not clean or len(clean) < 8:
        return True
    if GENERIC_TITLE_RE.match(clean):
        return True
    lowered = clean.lower()
    return lowered in {"read more", "learn more", "view all", "see all", "latest news", "all news", "all posts", "skip to main content", "security", "product", "products", "platform", "studio", "transcribe", "models", "api", "learn more learn more"}


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
    def __init__(self, *, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self._in_title = False
        self._title_parts: list[str] = []
        self.description = ""
        self.feed_links: list[str] = []
        self.article_links: list[_ArticleLink] = []
        self._current_href: str | None = None
        self._current_label_parts: list[str] = []

    @property
    def title(self) -> str:
        return _clean_text(" ".join(self._title_parts), limit=220)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.lower()
        attrs_dict = {key.lower(): value or "" for key, value in attrs}
        if lowered == "title":
            self._in_title = True
        if lowered == "meta":
            name = attrs_dict.get("name", "").lower() or attrs_dict.get("property", "").lower()
            if name in {"description", "og:description"} and attrs_dict.get("content") and not self.description:
                self.description = _clean_text(attrs_dict["content"], limit=600)
        if lowered == "link":
            rel = attrs_dict.get("rel", "").lower()
            link_type = attrs_dict.get("type", "").lower()
            href = attrs_dict.get("href", "")
            if "alternate" in rel and href and any(marker in link_type for marker in FEED_MIME_MARKERS):
                normalized = _normalize_public_url(href, base_url=self.base_url)
                if normalized:
                    self.feed_links.append(normalized)
        if lowered == "a":
            href = attrs_dict.get("href", "")
            normalized = _normalize_public_url(href, base_url=self.base_url)
            if normalized:
                self._current_href = normalized
                label = attrs_dict.get("aria-label") or attrs_dict.get("title") or ""
                self._current_label_parts = [label] if label else []

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered == "title":
            self._in_title = False
        if lowered == "a" and self._current_href:
            label = _clean_text(" ".join(self._current_label_parts), limit=220)
            if label:
                self.article_links.append(_ArticleLink(url=self._current_href, text=label))
            self._current_href = None
            self._current_label_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_parts.append(data)
        if self._current_href:
            self._current_label_parts.append(data)
