from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import html
import json
import zipfile


class ReportWriterError(Exception):
    """Raised when report output cannot be written safely."""


def write_report_outputs(report: dict[str, Any], out_dir: str | Path, formats: set[str], *, repo_root: str | Path) -> dict[str, str]:
    output_dir = _resolve_outputs_dir(out_dir, Path(repo_root))
    output_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, str] = {}
    if "json" in formats:
        path = output_dir / "report.json"
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        written["json"] = str(path)
    if "markdown" in formats:
        path = output_dir / "report.md"
        path.write_text(render_markdown(report), encoding="utf-8")
        written["markdown"] = str(path)
    if "docx" in formats:
        path = output_dir / "report.docx"
        write_docx(report, path)
        written["docx"] = str(path)
    return written


def parse_formats(value: str) -> set[str]:
    formats = {item.strip().lower() for item in value.split(",") if item.strip()}
    allowed = {"markdown", "json", "docx"}
    if not formats:
        raise ReportWriterError("at least one output format is required")
    unsupported = formats - allowed
    if unsupported:
        raise ReportWriterError(f"unsupported report format: {', '.join(sorted(unsupported))}")
    return formats


def render_markdown(report: dict[str, Any]) -> str:
    metadata = report.get("metadata", {})
    items = list(report.get("ranked_updates", []))
    watchlist = list(report.get("company_model_watchlist", []))
    followups = list(report.get("follow_up_checklist", []))
    source_errors = list(report.get("source_errors", []))
    lines: list[str] = []
    lines.append("# AI Daily Brief - Global and Major Model Updates")
    lines.append("")
    lines.append("## Metadata")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("| --- | --- |")
    for key in ("date", "timezone", "scope", "source_strategy", "generation_mode", "openai_used", "telegram_sent"):
        lines.append(f"| {_label(key)} | {_escape_pipe(str(metadata.get(key, '')))} |")
    lines.append("")
    lines.append("## Executive Summary")
    lines.append("")
    summary = report.get("executive_summary", [])
    if summary:
        for item in summary:
            lines.append(f"- {item}")
    else:
        lines.append("- No high-confidence live AI update was captured from the allowlisted public sources for this run.")
    lines.append("")
    lines.append("## Top Updates Ranked by Importance")
    lines.append("")
    if items:
        lines.append("| Rank | Update | Company / Model | Score | Confidence | Sources |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for item in items:
            sources = ", ".join(f"[{source['source_id']}]({source['url']})" for source in item.get("sources", []))
            lines.append(
                f"| {item.get('rank')} | {_escape_pipe(item.get('title', ''))} | {_escape_pipe(item.get('company_model', ''))} | {item.get('importance_score')} | {item.get('confidence')} | {sources} |"
            )
    else:
        lines.append("No ranked update passed the MVP fetch and review gates.")
    lines.append("")
    lines.append("## Key Judgments")
    lines.append("")
    judgments = report.get("key_judgments", [])
    if judgments:
        for judgment in judgments:
            lines.append(f"- {judgment}")
    else:
        lines.append("- Treat this run as a source-monitoring artifact until a human reviewer checks every source URL and claim boundary.")
    lines.append("")
    lines.append("## Detailed News Analysis")
    lines.append("")
    if items:
        for item in items:
            lines.append(f"### {item.get('rank')}. {item.get('title')}")
            lines.append("")
            lines.append(f"- Date: {item.get('published_at') or metadata.get('date')}")
            lines.append(f"- Type: {item.get('topic_type')}")
            lines.append(f"- Source: {', '.join(source['source_name'] for source in item.get('sources', []))}")
            lines.append(f"- Confidence: {item.get('confidence')}")
            lines.append(f"- What changed: {item.get('what_changed')}")
            lines.append(f"- Why it matters: {item.get('why_it_matters')}")
            lines.append(f"- Impact: {item.get('impact')}")
            lines.append(f"- Boundary / uncertainty: {item.get('boundary')}")
            lines.append("")
    else:
        lines.append("No detailed item is ready. Review source errors and rerun later if needed.")
        lines.append("")
    lines.append("## Company and Model Watchlist")
    lines.append("")
    if watchlist:
        for item in watchlist:
            lines.append(f"- {item}")
    else:
        lines.append("- No company or model watchlist item was promoted from this run.")
    lines.append("")
    lines.append("## Follow-up Checklist")
    lines.append("")
    if followups:
        for item in followups:
            lines.append(f"- [ ] {item}")
    else:
        lines.append("- [ ] Re-run the live report command after source availability is confirmed.")
    if source_errors:
        lines.append("")
        lines.append("## Source Fetch Notes")
        lines.append("")
        for error in source_errors:
            lines.append(f"- {error.get('source_id')}: {error.get('error')}")
    lines.append("")
    lines.append("## Conclusion")
    lines.append("")
    lines.append(str(report.get("conclusion", "This report is a manually generated local artifact. Review sources before publication or downstream delivery.")))
    lines.append("")
    return "\n".join(lines)


def write_docx(report: dict[str, Any], path: str | Path) -> None:
    target = Path(path)
    paragraphs = _markdown_to_paragraphs(render_markdown(report))
    document_xml = _document_xml(paragraphs)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _content_types_xml())
        archive.writestr("_rels/.rels", _rels_xml())
        archive.writestr("docProps/core.xml", _core_xml(now))
        archive.writestr("docProps/app.xml", _app_xml())
        archive.writestr("word/document.xml", document_xml)
        archive.writestr("word/_rels/document.xml.rels", "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"/>")


def _markdown_to_paragraphs(markdown: str) -> list[tuple[str, str]]:
    paragraphs: list[tuple[str, str]] = []
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("# "):
            paragraphs.append(("Heading1", line[2:]))
        elif line.startswith("## "):
            paragraphs.append(("Heading2", line[3:]))
        elif line.startswith("### "):
            paragraphs.append(("Heading3", line[4:]))
        elif line.startswith("| ---"):
            continue
        else:
            paragraphs.append(("Normal", line))
    return paragraphs


def _document_xml(paragraphs: list[tuple[str, str]]) -> str:
    body = []
    for style, text in paragraphs:
        style_xml = "" if style == "Normal" else f"<w:pPr><w:pStyle w:val=\"{style}\"/></w:pPr>"
        body.append(f"<w:p>{style_xml}<w:r><w:t xml:space=\"preserve\">{html.escape(text)}</w:t></w:r></w:p>")
    return "".join(
        [
            "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>",
            "<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\"><w:body>",
            *body,
            "<w:sectPr><w:pgSz w:w=\"12240\" w:h=\"15840\"/><w:pgMar w:top=\"1440\" w:right=\"1440\" w:bottom=\"1440\" w:left=\"1440\"/></w:sectPr>",
            "</w:body></w:document>",
        ]
    )


def _resolve_outputs_dir(out_dir: str | Path, repo_root: Path) -> Path:
    raw = str(out_dir)
    if not raw or "://" in raw or raw.startswith(("~", "\\")):
        raise ReportWriterError("unsafe output path rejected")
    candidate = Path(out_dir)
    if not candidate.is_absolute():
        if any(part in {"", ".."} for part in raw.replace("\\", "/").split("/")):
            raise ReportWriterError("unsafe output path rejected")
        candidate = repo_root / candidate
    resolved = candidate.resolve()
    outputs_root = (repo_root / "outputs").resolve()
    try:
        resolved.relative_to(outputs_root)
    except ValueError as exc:
        raise ReportWriterError("output path must stay under outputs/") from exc
    return resolved


def _label(value: str) -> str:
    return value.replace("_", " ").title()


def _escape_pipe(value: str) -> str:
    return value.replace("|", "\\|")


def _content_types_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/><Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/></Types>"""


def _rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/></Relationships>"""


def _core_xml(timestamp: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>AI Daily Brief</dc:title><dc:creator>AI Signal Brief</dc:creator><cp:lastModifiedBy>AI Signal Brief</cp:lastModifiedBy><dcterms:created xsi:type="dcterms:W3CDTF">{timestamp}</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">{timestamp}</dcterms:modified></cp:coreProperties>"""


def _app_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>AI Signal Brief</Application></Properties>"""