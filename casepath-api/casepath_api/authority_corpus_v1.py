"""Assemble an authority corpus of exact statutory passages from Fedlex Akoma Ntoso XML.

Why XML and not the web page: the Fedlex ELI landing page is a JavaScript shell containing no law text, and
the HTML twin loses the space before lettered list items, which silently corrupts any exact-quote gate
built on top of it. The Akoma Ntoso file is the same artefact the passages already in this repository were
taken from, and parsing it reproduces 18 of those 19 byte for byte. The nineteenth is a defect in the
repository, not here: its Art. 259g text carries two commas that the consolidation it names does not.

Extraction identity: visible text of the paragraph, authorial notes dropped, a separator inserted at block
boundaries so list items keep their spacing, whitespace normalised.
"""
from __future__ import annotations

import hashlib, re, urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Sequence

CONTRACT = "casepath.authority-corpus/1.0.0"
EXTRACTION_IDENTITY = "fedlex-akn3-visible-text-blockspaced-whitespace-normalization/1.1.0"
UA = {"User-Agent": "Mozilla/5.0 (research; CasePath authority corpus assembly)"}
BLOCK = {"p", "item", "listIntroduction", "listWrapUp", "intro", "wrapUp", "blockList", "paragraph", "content"}


def xml_url(eli_path: str, date: str, lang: str = "de", suffix: int = 4) -> str:
    """The filestore XML twin of an ELI, which is where the text actually lives.

    The trailing number is a per-act file index, not a constant: the Code of Obligations is -4 and the
    tenancy ordinance is -1. Callers that do not know it should use ``resolve``.
    """
    slug = "fedlex-data-admin-ch-eli-" + eli_path.strip("/").replace("/", "-") + f"-{date}-{lang}-xml-{suffix}.xml"
    return f"https://www.fedlex.admin.ch/filestore/fedlex.data.admin.ch/eli/{eli_path.strip('/')}/{date}/{lang}/xml/{slug}"


def resolve(eli_path: str, dates: Sequence[str], lang: str = "de",
            suffixes: Sequence[int] = (1, 2, 3, 4, 5, 6)) -> dict[str, Any] | None:
    """Find the consolidation date and file index that actually serve this act, and confirm its SR number."""
    for date in dates:
        for suffix in suffixes:
            url = xml_url(eli_path, date, lang, suffix)
            try:
                raw = fetch(url, timeout=30)
                root = ET.fromstring(raw)
            except Exception:
                continue
            sr = next((visible(e) for e in root.iter() if e.tag.split("}")[-1] == "docNumber"), "")
            return {"eli_path": eli_path, "date": date, "suffix": suffix, "lang": lang,
                    "sr_number": sr, "url": url, "articles": len(articles(raw)), "raw": raw}
    return None


def fetch(url: str, timeout: int = 90) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def articles(xml_bytes: bytes) -> dict[str, ET.Element]:
    root = ET.fromstring(xml_bytes)
    return {a.get("eId"): a for a in root.iter() if a.tag.split("}")[-1] == "article" and a.get("eId")}


def visible(element: ET.Element) -> str:
    def walk(x: ET.Element) -> list[str]:
        if x.tag.split("}")[-1] == "authorialNote":
            return [x.tail or ""]
        out: list[str] = []
        if x.text:
            out.append(x.text)
        for c in x:
            if c.tag.split("}")[-1] in BLOCK:
                out.append(" ")
            out.extend(walk(c))
        if x.tail:
            out.append(x.tail)
        return out
    return re.sub(r"\s+", " ", "".join(walk(element))).strip()


def _eid(article: str) -> str:
    m = re.fullmatch(r"(\d+)([a-z]?)", article)
    if not m:
        raise ValueError(f"unparsable article number: {article!r}")
    return "art_" + m.group(1) + (("_" + m.group(2)) if m.group(2) else "")


def passage(arts: dict[str, ET.Element], article: str, para: str | None) -> str | None:
    a = arts.get(_eid(article))
    if a is None:
        return None
    if para is None:
        body = [visible(c) for c in a if c.tag.split("}")[-1] not in ("num", "heading")]
        return re.sub(r"\s+", " ", " ".join(body)).strip() or None
    for p in a.iter():
        if p.tag.split("}")[-1] != "paragraph":
            continue
        num = next((visible(x) for x in p if x.tag.split("}")[-1] == "num"), "")
        if num.strip().rstrip(".") == para:
            body = [visible(c) for c in p if c.tag.split("}")[-1] != "num"]
            return re.sub(r"\s+", " ", " ".join(body)).strip() or None
    return None


def build(act_id: str, eli_path: str, date: str, wanted: list[tuple[str, str | None]],
          lang: str = "de", suffix: int = 4, raw: bytes | None = None) -> dict[str, Any]:
    """Fetch one act and extract the requested (article, paragraph) pairs. Missing ones are reported."""
    url = xml_url(eli_path, date, lang, suffix)
    if raw is None:
        raw = fetch(url)
    arts = articles(raw)
    out, missing = [], []
    for article, para in wanted:
        text = passage(arts, article, para)
        if not text:
            missing.append({"article": article, "paragraph": para, "eid": _eid(article),
                            "present_in_act": _eid(article) in arts})
            continue
        label = f"Art. {article}" + (f" Abs. {para}" if para else "")
        out.append({"authority_id": f"{act_id}-art-{article}{'-para'+para if para else ''}-{date}-{lang}",
                    "act": act_id, "article": label, "exact_text": text,
                    "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                    "snapshot_id": f"fedlex-{act_id}-{date}-{lang}", "source_url": url})
    return {"contract": CONTRACT, "extraction_identity": EXTRACTION_IDENTITY, "act": act_id,
            "eli_path": eli_path, "consolidation_date": date, "language": lang, "source_url": url,
            "source_sha256": hashlib.sha256(raw).hexdigest(), "articles_in_act": len(arts),
            "passages": out, "missing": missing}
