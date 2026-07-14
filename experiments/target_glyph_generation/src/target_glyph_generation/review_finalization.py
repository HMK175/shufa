"""Read-only finalization of manually reviewed single-image OCR labels.

The OCR audit intentionally leaves review spreadsheets editable by a human.  This
module never rewrites those inputs: it parses their decisions in memory, reports
any ambiguity, and produces candidates only when the full review is safe to use.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
import csv
import io
from pathlib import Path


Key = tuple[str, str, str, str]

LABEL_REQUIRED_FIELDNAMES = (
    "dataset_id",
    "style_id",
    "source_split",
    "raw_filename",
    "image_path",
    "ocr_text",
    "character",
    "review_state",
)
DRAFT_FIELDNAMES = (
    "dataset_id",
    "style_id",
    "source_split",
    "raw_filename",
    "manual_character",
    "decision",
    "note",
)
CANDIDATE_FIELDNAMES = (
    "dataset_id",
    "style_id",
    "character",
    "source_split",
    "target_path",
    "raw_filename",
    "review_state",
)
REJECTED_FIELDNAMES = (
    "dataset_id",
    "style_id",
    "source_split",
    "raw_filename",
    "target_path",
    "note",
)
ISSUE_FIELDNAMES = (
    "code",
    "dataset_id",
    "style_id",
    "source_split",
    "raw_filename",
    "source_path",
    "message",
)

_CJK_RANGES = (
    (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF),
    (0xF900, 0xFAFF),
)
_VALID_DECISIONS = frozenset({"", "accept", "reject"})


@dataclass(frozen=True)
class OcrLabel:
    """One original OCR label, identified by the immutable source image key."""

    dataset_id: str
    style_id: str
    source_split: str
    raw_filename: str
    image_path: str
    ocr_text: str
    character: str
    review_state: str

    @property
    def key(self) -> Key:
        return (self.dataset_id, self.style_id, self.source_split, self.raw_filename)


@dataclass(frozen=True)
class DraftEntry:
    """One human review decision after harmless legacy normalization."""

    key: Key
    manual_character: str
    decision: str
    note: str
    source_path: Path


@dataclass(frozen=True)
class ReviewIssue:
    """A blocker or normalization event associated with a source image key."""

    code: str
    key: Key
    source_path: Path | None
    message: str


@dataclass(frozen=True)
class ReviewDraft:
    """Read-only parsed CSV draft and its non-destructive parsing diagnostics."""

    source_path: Path
    entries: tuple[DraftEntry, ...]
    parse_issues: tuple[ReviewIssue, ...]
    normalizations: tuple[ReviewIssue, ...]


@dataclass(frozen=True)
class FinalCandidate:
    """A candidate usable for later pairing only after the finalization gate passes."""

    dataset_id: str
    style_id: str
    character: str
    source_split: str
    target_path: str
    raw_filename: str
    review_state: str


@dataclass(frozen=True)
class RejectedRow:
    """A human-rejected source image retained for auditability only."""

    dataset_id: str
    style_id: str
    source_split: str
    raw_filename: str
    target_path: str
    note: str


@dataclass(frozen=True)
class FinalizationResult:
    """Finalization output, with all blocking diagnostics kept separate."""

    candidates: tuple[FinalCandidate, ...]
    rejected: tuple[RejectedRow, ...]
    unresolved: tuple[ReviewIssue, ...]
    conflicts: tuple[ReviewIssue, ...]
    normalizations: tuple[ReviewIssue, ...]

    @property
    def is_finalizable(self) -> bool:
        return not self.unresolved and not self.conflicts


def load_ocr_labels(path: Path) -> tuple[OcrLabel, ...]:
    """Load original audit labels without changing their CSV file."""
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"OCR labels path is not a file: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or ())
        missing = set(LABEL_REQUIRED_FIELDNAMES).difference(fieldnames)
        if missing:
            raise ValueError(f"OCR labels CSV is missing required columns: {sorted(missing)!r}")
        labels: list[OcrLabel] = []
        for row_number, row in enumerate(reader, start=2):
            if row is None or any(key is None for key in row):
                raise ValueError(f"OCR labels row {row_number} has unexpected columns")
            if all(not _strip(row.get(field)) for field in LABEL_REQUIRED_FIELDNAMES):
                continue
            labels.append(
                OcrLabel(
                    dataset_id=_strip(row.get("dataset_id")),
                    style_id=_strip(row.get("style_id")),
                    source_split=_strip(row.get("source_split")),
                    raw_filename=_strip(row.get("raw_filename")),
                    image_path=_strip(row.get("image_path")),
                    ocr_text=_strip(row.get("ocr_text")),
                    character=_strip(row.get("character")),
                    review_state=_strip(row.get("review_state")),
                )
            )
    return tuple(labels)


def load_review_draft(path: Path) -> ReviewDraft:
    """Load a manual review draft and repair known legacy formatting in memory.

    Older manually edited rows accidentally stored the image filename in
    ``source_split`` and ``train``/``test`` in ``raw_filename``.  A historical
    ``aceept`` spelling is also accepted.  Both repairs are reported and never
    written back to the source CSV.
    """
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"review draft path is not a file: {path}")
    with io.StringIO(_read_review_draft_text(path), newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != DRAFT_FIELDNAMES:
            raise ValueError("review draft header must match the emitted template exactly")

        entries: list[DraftEntry] = []
        parse_issues: list[ReviewIssue] = []
        normalizations: list[ReviewIssue] = []
        for row_number, row in enumerate(reader, start=2):
            if row is None:
                continue
            surplus = row.get(None, [])
            if any(_strip(value) for value in surplus):
                parse_issues.append(
                    _issue(
                        "unexpected_extra_column",
                        ("", "", "", ""),
                        path,
                        f"review draft row {row_number} has nonempty extra columns",
                    )
                )
            values = {field: _strip(row.get(field)) for field in DRAFT_FIELDNAMES}
            if not any(values.values()):
                continue

            key = (
                values["dataset_id"],
                values["style_id"],
                values["source_split"],
                values["raw_filename"],
            )
            if _looks_like_image_filename(key[2]) and key[3] in {"train", "test"}:
                key = (key[0], key[1], key[3], key[2])
                normalizations.append(
                    _issue(
                        "legacy_columns_swapped",
                        key,
                        path,
                        f"review draft row {row_number} swapped source_split and raw_filename in memory",
                    )
                )

            decision = values["decision"].lower()
            if decision == "aceept":
                decision = "accept"
                normalizations.append(
                    _issue(
                        "decision_aceept_normalized",
                        key,
                        path,
                        f"review draft row {row_number} normalized aceept to accept in memory",
                    )
                )
            entries.append(
                DraftEntry(
                    key=key,
                    manual_character=values["manual_character"],
                    decision=decision,
                    note=values["note"],
                    source_path=path,
                )
            )
    return ReviewDraft(path, tuple(entries), tuple(parse_issues), tuple(normalizations))


def finalize_review_drafts(
    labels: Sequence[OcrLabel], drafts: Iterable[ReviewDraft]
) -> FinalizationResult:
    """Apply drafts in memory and return candidates plus every blocking issue."""
    label_list = list(labels)
    draft_list = list(drafts)
    conflicts: list[ReviewIssue] = []
    unresolved: list[ReviewIssue] = []
    normalizations = [item for draft in draft_list for item in draft.normalizations]
    conflicts.extend(item for draft in draft_list for item in draft.parse_issues)

    labels_by_key: dict[Key, OcrLabel] = {}
    labels_by_filename: dict[tuple[str, str, str], list[OcrLabel]] = defaultdict(list)
    for label in label_list:
        if label.key in labels_by_key:
            conflicts.append(
                _issue(
                    "duplicate_ocr_label_key",
                    label.key,
                    None,
                    "OCR labels contain more than one row for the same source image",
                )
            )
        else:
            labels_by_key[label.key] = label
            labels_by_filename[(label.dataset_id, label.style_id, label.raw_filename)].append(label)

    selected: dict[Key, DraftEntry] = {}
    for draft in draft_list:
        for entry in draft.entries:
            if entry.key not in labels_by_key:
                matches = labels_by_filename[
                    (entry.key[0], entry.key[1], entry.key[3])
                ]
                if len(matches) == 1:
                    resolved_key = matches[0].key
                    normalizations.append(
                        _issue(
                            "source_split_resolved_by_unique_filename",
                            resolved_key,
                            entry.source_path,
                            "review draft source_split was resolved from a unique dataset/style/filename match",
                        )
                    )
                    entry = replace(entry, key=resolved_key)
                else:
                    conflicts.append(
                        _issue(
                            "unknown_source_key",
                            entry.key,
                            entry.source_path,
                            "review draft key does not map to an original OCR label",
                        )
                    )
                    continue
            if entry.key not in labels_by_key:
                conflicts.append(
                    _issue(
                        "unknown_source_key",
                        entry.key,
                        entry.source_path,
                        "review draft key does not map to an original OCR label",
                    )
                )
                continue
            if entry.decision not in _VALID_DECISIONS:
                unresolved.append(
                    _issue(
                        "invalid_draft_decision",
                        entry.key,
                        entry.source_path,
                        f"unsupported review decision: {entry.decision!r}",
                    )
                )
                continue
            if entry.decision == "" and entry.manual_character:
                unresolved.append(
                    _issue(
                        "manual_character_without_accept",
                        entry.key,
                        entry.source_path,
                        "manual_character requires decision=accept",
                    )
                )
                continue
            if entry.decision == "reject" and entry.manual_character:
                normalizations.append(
                    _issue(
                        "manual_character_ignored_for_reject",
                        entry.key,
                        entry.source_path,
                        "manual_character is ignored because decision=reject excludes the source image",
                    )
                )
            prior = selected.get(entry.key)
            if prior is None:
                selected[entry.key] = entry
                continue
            merged, conflict = _merge_entries(prior, entry)
            if conflict is not None:
                conflicts.append(conflict)
            else:
                selected[entry.key] = merged

    candidates: list[FinalCandidate] = []
    rejected: list[RejectedRow] = []
    for label in label_list:
        if labels_by_key.get(label.key) is not label:
            continue
        entry = selected.get(label.key)
        if entry is not None and entry.decision == "reject":
            rejected.append(
                RejectedRow(
                    dataset_id=label.dataset_id,
                    style_id=label.style_id,
                    source_split=label.source_split,
                    raw_filename=label.raw_filename,
                    target_path=label.image_path,
                    note=entry.note,
                )
            )
            continue
        if entry is not None and entry.decision == "accept":
            character = _normalize_cjk_character(entry.manual_character)
            if character is None:
                code = "manual_character_needed" if not entry.manual_character else "invalid_manual_character"
                message = (
                    "decision=accept requires one CJK manual_character before finalization"
                    if code == "manual_character_needed"
                    else "manual_character must contain exactly one CJK character"
                )
                unresolved.append(
                    _issue(
                        code,
                        label.key,
                        entry.source_path,
                        message,
                    )
                )
                continue
            candidates.append(_candidate(label, character, "manual_override"))
            continue
        character = _normalize_cjk_character(label.character) or _normalize_cjk_character(label.ocr_text)
        if character is None:
            unresolved.append(
                _issue(
                    "invalid_ocr_character",
                    label.key,
                    None,
                    "default retention requires one valid CJK OCR character",
                )
            )
            continue
        candidates.append(_candidate(label, character, "default_ocr"))

    grouped: dict[tuple[str, str, str], list[FinalCandidate]] = defaultdict(list)
    for candidate in candidates:
        grouped[(candidate.dataset_id, candidate.style_id, candidate.character)].append(candidate)
    for (dataset_id, style_id, character), group in sorted(grouped.items()):
        if len(group) > 1:
            conflicts.append(
                _issue(
                    "duplicate_style_character",
                    (dataset_id, style_id, "", ""),
                    None,
                    f"{len(group)} retained images map to the same style/character {character!r}",
                )
            )

    return FinalizationResult(
        candidates=tuple(candidates),
        rejected=tuple(rejected),
        unresolved=tuple(unresolved),
        conflicts=tuple(conflicts),
        normalizations=tuple(normalizations),
    )


def candidate_rows(candidates: Iterable[FinalCandidate]) -> list[dict[str, str]]:
    """Return CSV-ready candidate rows with a stable field order."""
    return [
        {
            "dataset_id": candidate.dataset_id,
            "style_id": candidate.style_id,
            "character": candidate.character,
            "source_split": candidate.source_split,
            "target_path": candidate.target_path,
            "raw_filename": candidate.raw_filename,
            "review_state": candidate.review_state,
        }
        for candidate in candidates
    ]


def issue_rows(issues: Iterable[ReviewIssue]) -> list[dict[str, str]]:
    """Return CSV-ready diagnostic rows."""
    return [
        {
            "code": issue.code,
            "dataset_id": issue.key[0],
            "style_id": issue.key[1],
            "source_split": issue.key[2],
            "raw_filename": issue.key[3],
            "source_path": str(issue.source_path) if issue.source_path is not None else "",
            "message": issue.message,
        }
        for issue in issues
    ]


def rejected_rows(rejected: Iterable[RejectedRow]) -> list[dict[str, str]]:
    """Return CSV-ready rejected image rows without mixing them into candidates."""
    return [
        {
            "dataset_id": item.dataset_id,
            "style_id": item.style_id,
            "source_split": item.source_split,
            "raw_filename": item.raw_filename,
            "target_path": item.target_path,
            "note": item.note,
        }
        for item in rejected
    ]


def _merge_entries(prior: DraftEntry, later: DraftEntry) -> tuple[DraftEntry, ReviewIssue | None]:
    if prior.decision != later.decision:
        if prior.decision == "accept" and not prior.manual_character and later.decision == "reject":
            return later, None
        return prior, _issue(
            "conflicting_draft_decision",
            prior.key,
            later.source_path,
            f"conflicting decisions {prior.decision!r} and {later.decision!r} for the same source image",
        )
    if prior.decision != "accept":
        return prior, None
    if prior.manual_character and later.manual_character and prior.manual_character != later.manual_character:
        return prior, _issue(
            "conflicting_draft_decision",
            prior.key,
            later.source_path,
            "conflicting manual_character values for the same source image",
        )
    return (later if later.manual_character else prior), None


def _candidate(label: OcrLabel, character: str, review_state: str) -> FinalCandidate:
    return FinalCandidate(
        dataset_id=label.dataset_id,
        style_id=label.style_id,
        character=character,
        source_split=label.source_split,
        target_path=label.image_path,
        raw_filename=label.raw_filename,
        review_state=review_state,
    )


def _issue(code: str, key: Key, source_path: Path | None, message: str) -> ReviewIssue:
    return ReviewIssue(code=code, key=key, source_path=source_path, message=message)


def _strip(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _read_review_draft_text(path: Path) -> str:
    contents = path.read_bytes()
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return contents.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"review draft uses an unsupported text encoding: {path}")


def _looks_like_image_filename(value: str) -> bool:
    lowered = value.lower()
    return lowered.endswith((".jpg", ".jpeg", ".png"))


def _normalize_cjk_character(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    character = value.strip()
    if len(character) != 1:
        return None
    codepoint = ord(character)
    return character if any(start <= codepoint <= end for start, end in _CJK_RANGES) else None
