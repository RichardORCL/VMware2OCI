#!/usr/bin/env python3
"""Validate only the Phase-1 automation-ready OCVS SDD template."""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path

from lxml import etree

from build_ocvs_sdd_template import CONDITIONAL_TAGS, REPEAT_TAGS, SCALAR_TAGS, SOURCE_SHA256


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W15_NS = "http://schemas.microsoft.com/office/word/2012/wordml"
NS = {"w": W_NS, "w15": W15_NS}

FORBIDDEN_LITERAL = {
    "a company making everything",
    "insert region",
    "dc location",
    "env name",
    "name surname",
    "example@example.com",
    "xxxxx",
    "<customer>",
    "insert name",
    "tbd",
    "10.0.0.0/16",
    "bm.denseio2.52",
    "bm.standard3.48",
}
FORBIDDEN_SAMPLE_NUMBERS = {"550", "1100", "3600", "47160", "60000"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("template", type=Path)
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()
    errors: list[str] = []

    if not args.template.is_file():
        fail(errors, f"Template not found: {args.template}")
    elif not zipfile.is_zipfile(args.template):
        fail(errors, "Output is not a valid ZIP/DOCX package")

    if args.source:
        if not args.source.is_file():
            fail(errors, f"Source not found: {args.source}")
        elif sha256(args.source) != SOURCE_SHA256:
            fail(errors, "The original source template has changed")

    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors), file=sys.stderr)
        return 1

    parser_xml = etree.XMLParser(resolve_entities=False, remove_blank_text=False)
    with zipfile.ZipFile(args.template) as archive:
        names = set(archive.namelist())
        required_parts = {"[Content_Types].xml", "word/document.xml", "word/styles.xml"}
        missing_parts = sorted(required_parts - names)
        if missing_parts:
            fail(errors, f"Missing DOCX parts: {', '.join(missing_parts)}")

        roots: list[tuple[str, etree._Element]] = []
        for name in sorted(names):
            if not name.startswith("word/") or not name.endswith(".xml"):
                continue
            try:
                roots.append((name, etree.fromstring(archive.read(name), parser_xml)))
            except etree.XMLSyntaxError as exc:
                fail(errors, f"Invalid XML in {name}: {exc}")

    tags: list[str] = []
    aliases: list[str] = []
    all_text: list[str] = []
    document_root = None
    for name, root in roots:
        if name == "word/document.xml":
            document_root = root
        tags.extend(root.xpath(".//w:sdtPr/w:tag/@w:val", namespaces=NS))
        aliases.extend(root.xpath(".//w:sdtPr/w:alias/@w:val", namespaces=NS))
        all_text.extend(root.xpath(".//w:t/text()", namespaces=NS))

    counts = Counter(tags)
    for tag in sorted(SCALAR_TAGS):
        if counts[tag] == 0:
            fail(errors, f"Required scalar content-control tag is missing: {tag}")
        elif counts[tag] > 1:
            fail(errors, f"Duplicate scalar content-control tag: {tag} ({counts[tag]})")

    for tag in sorted(REPEAT_TAGS | CONDITIONAL_TAGS):
        if counts[tag] != 1:
            fail(errors, f"Expected exactly one structural tag {tag}; found {counts[tag]}")

    if len(tags) != len(aliases):
        fail(errors, "One or more content controls do not have both a title and a tag")

    if document_root is not None:
        for repeat_tag in sorted(REPEAT_TAGS):
            wrappers = document_root.xpath(
                f'.//w:sdt[w:sdtPr/w:tag[@w:val="{repeat_tag}"]]'
                f'[w:sdtPr/w15:repeatingSection]', namespaces=NS
            )
            if len(wrappers) != 1:
                fail(errors, f"Invalid repeating-section wrapper: {repeat_tag}")
                continue
            items = wrappers[0].xpath(
                f'.//w:sdt[w:sdtPr/w:tag[@w:val="{repeat_tag}_item"]]'
                f'[w:sdtPr/w15:repeatingSectionItem]', namespaces=NS
            )
            if len(items) != 1:
                fail(errors, f"Invalid repeating-section item for {repeat_tag}")

        lift = document_root.xpath(
            './/w:sdt[w:sdtPr/w:tag[@w:val="section_oracle_lift"]]', namespaces=NS
        )
        if len(lift) != 1 or "Project Implementation (Only for Oracle Implementations!)" not in "".join(
            lift[0].xpath('.//w:t/text()', namespaces=NS)
        ):
            fail(errors, "Oracle Lift content is not fully enclosed by section_oracle_lift")

    text = "\n".join(all_text)
    lower_text = text.lower()
    for phrase in sorted(FORBIDDEN_LITERAL):
        if phrase in lower_text:
            fail(errors, f"Forbidden sample phrase remains: {phrase}")
    for number in sorted(FORBIDDEN_SAMPLE_NUMBERS):
        if re.search(rf"(?<![\d.,]){re.escape(number)}(?![\d.,])", text):
            fail(errors, f"Forbidden sample sizing value remains: {number}")
    if re.search(r"\b(?:10|172\.(?:1[6-9]|2\d|3[01])|192\.168)(?:\.\d{1,3}){2}/\d{1,2}\b", text):
        fail(errors, "A sample private CIDR remains")
    if "[[SDT:" in text or "[[SECTION:" in text:
        fail(errors, "An unresolved internal template marker remains")

    if errors:
        print("OCVS SDD template validation FAILED", file=sys.stderr)
        print("\n".join(f"ERROR: {error}" for error in errors), file=sys.stderr)
        return 1

    print("OCVS SDD template validation PASSED")
    print(f"Content controls: {len(tags)}")
    print(f"Unique tags: {len(counts)}")
    print(f"Scalar tags: {len(SCALAR_TAGS)}")
    print(f"Repeatable structures: {len(REPEAT_TAGS)}")
    print(f"Conditional sections: {len(CONDITIONAL_TAGS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
