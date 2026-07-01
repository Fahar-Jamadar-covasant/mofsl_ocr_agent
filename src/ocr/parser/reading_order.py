"""
Reading-order reconstruction and semantic element extraction.

Pipeline
--------
1. TableExtractor       — finds TABLE blocks, builds structured Table objects,
                          returns excluded LINE IDs (lines that belong to tables).

2. SelectionExtractor   — finds KEY_VALUE_SET blocks whose value is a
                          SELECTION_ELEMENT, builds flat _FlatCheckbox list,
                          returns excluded LINE IDs (lines that belong to
                          checkbox groups).

3. SelectionGrouper     — clusters flat checkboxes by proximity, scores label
                          candidates, builds grouped Selection objects.

4. SignatureExtractor   — finds SIGNATURE blocks, returns excluded LINE IDs
                          (empty — SIGNATURE blocks carry no WORD children).

5. VisualLineBuilder    — collects remaining LINE blocks (not excluded),
                          sorts by (top, left), merges fragments that belong
                          to the same visual row, returns plain strings.

Exclusion rule
--------------
Every LINE whose words overlap a semantic element (table or checkbox) is
excluded from reading-order reconstruction.  The LINE ID — not the word ID —
is the exclusion key.  This prevents any semantic content from appearing twice
in the output.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from src.ocr.parser.block_index import BlockIndex
from src.ocr.parser.models import Table, Selection, SelectionOption, Signature


# ─────────────────────────────────────────────────────────────────────────────
# Internal model — flat checkbox (never exposed in output)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class _FlatCheckbox:
    """One checkbox as Textract detected it, with coordinates for grouping."""
    label:    str         # KEY block text,   e.g. "Male"
    selected: bool        # True when SelectionStatus == "SELECTED"
    top:      float       # BoundingBox.Top  of the KEY block
    left:     float       # BoundingBox.Left of the KEY block
    word_ids: set[str]    # WORD block IDs owned by this KEY block


# ─────────────────────────────────────────────────────────────────────────────
# Label candidate abstraction
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class _Candidate:
    """
    A normalised label candidate, independent of its Textract block type.
    Decouples LabelCandidateSource implementations from the raw block shape.
    """
    text:   str
    top:    float
    left:   float
    height: float


class LabelCandidateSource(ABC):
    """
    Abstract source of label candidates for SelectionGrouper.

    Implement this interface to extend label search to additional block types
    (e.g. LAYOUT_TEXT, LAYOUT_SECTION_HEADER) without touching the grouping
    or scoring logic.
    """

    @abstractmethod
    def candidates(self, page_blocks: list) -> list[_Candidate]:
        """Extract and normalise label candidates from a page block list."""


class LineCandidateSource(LabelCandidateSource):
    """Extracts LINE blocks as label candidates (default, always registered)."""

    def candidates(self, page_blocks: list) -> list[_Candidate]:
        result: list[_Candidate] = []
        for block in page_blocks:
            if block["BlockType"] != "LINE":
                continue
            bbox = block.get("Geometry", {}).get("BoundingBox", {})
            result.append(_Candidate(
                text=block.get("Text", ""),
                top=bbox.get("Top", 0.0),
                left=bbox.get("Left", 0.0),
                height=bbox.get("Height", 0.0),
            ))
        return result


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1 — Table extraction
# ─────────────────────────────────────────────────────────────────────────────

class TableExtractor:
    """
    Extracts TABLE blocks from a page and returns structured Table objects
    together with the set of LINE IDs that belong to those tables.
    """

    def __init__(self, index: BlockIndex):
        self.index = index

    def extract(self, page_blocks: list) -> tuple[list[Table], set[str]]:
        tables: list[Table] = []
        table_word_ids: set[str] = set()

        for block in page_blocks:

            if block["BlockType"] != "TABLE":
                continue

            cells = self.index.children_of(block)

            header_row_indices: set[int] = set()
            grid: dict[int, dict[int, str]] = {}

            for cell in cells:

                if cell["BlockType"] != "CELL":
                    continue

                row = cell["RowIndex"]
                col = cell["ColumnIndex"]

                if "COLUMN_HEADER" in cell.get("EntityTypes", []):
                    header_row_indices.add(row)

                words = self.index.children_of(cell)
                cell_text = " ".join(
                    w["Text"] for w in words if w["BlockType"] == "WORD"
                )
                grid.setdefault(row, {})[col] = cell_text

                for w in words:
                    if w["BlockType"] == "WORD":
                        table_word_ids.add(w["Id"])

            if not grid:
                continue

            sorted_row_indices = sorted(grid.keys())

            if not header_row_indices:
                header_row_indices = {sorted_row_indices[0]}

            headers: list[str] = []
            data_rows: list[list[str]] = []

            for row_idx in sorted_row_indices:
                cols = sorted(grid[row_idx].keys())
                row_cells = [grid[row_idx].get(c, "") for c in cols]
                if row_idx in header_row_indices:
                    headers = row_cells
                else:
                    data_rows.append(row_cells)

            tables.append(Table(headers=headers, rows=data_rows))

        excluded_line_ids: set[str] = set()

        if table_word_ids:
            for block in page_blocks:
                if block["BlockType"] != "LINE":
                    continue
                line_word_ids = {
                    w["Id"]
                    for w in self.index.children_of(block)
                    if w["BlockType"] == "WORD"
                }
                if line_word_ids & table_word_ids:
                    excluded_line_ids.add(block["Id"])

        return tables, excluded_line_ids


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2 — Flat checkbox extraction
# ─────────────────────────────────────────────────────────────────────────────

class SelectionExtractor:
    """
    Extracts KEY_VALUE_SET blocks whose VALUE child is a SELECTION_ELEMENT.
    """

    def __init__(self, index: BlockIndex):
        self.index = index

    def extract(self, page_blocks: list) -> tuple[list[_FlatCheckbox], set[str]]:
        flat_checkboxes: list[_FlatCheckbox] = []

        for block in page_blocks:

            if block["BlockType"] != "KEY_VALUE_SET":
                continue

            if "KEY" not in block.get("EntityTypes", []):
                continue

            selection_element = self._find_selection_element(block)

            if selection_element is None:
                continue

            key_words = self.index.children_of(block)
            label = " ".join(
                w["Text"] for w in key_words if w["BlockType"] == "WORD"
            )

            word_ids: set[str] = {
                w["Id"] for w in key_words if w["BlockType"] == "WORD"
            }

            bbox = block.get("Geometry", {}).get("BoundingBox", {})
            selected = selection_element.get("SelectionStatus") == "SELECTED"

            flat_checkboxes.append(_FlatCheckbox(
                label=label,
                selected=selected,
                top=bbox.get("Top", 0.0),
                left=bbox.get("Left", 0.0),
                word_ids=word_ids,
            ))

        return flat_checkboxes, set()

    def _find_selection_element(self, key_block: dict) -> dict | None:
        for value_block in self.index.values_of(key_block):
            for child in self.index.children_of(value_block):
                if child["BlockType"] == "SELECTION_ELEMENT":
                    return child
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2 (cont.) — Checkbox grouping and scored label resolution
# ─────────────────────────────────────────────────────────────────────────────

class SelectionGrouper:
    """
    Converts a flat list of _FlatCheckbox objects into grouped Selection objects.
    """

    def __init__(
        self,
        candidate_sources:        list[LabelCandidateSource] | None = None,
        left_threshold:           float = 0.03,
        top_threshold:            float = 0.05,
        vertical_search_window:   float = 0.15,
        horizontal_search_window: float = 0.20,
        weight_proximity:         float = 0.50,
        weight_alignment:         float = 0.30,
        weight_reading_order:     float = 0.20,
        min_score:                float = 0.30,
    ):
        self.candidate_sources        = candidate_sources or [LineCandidateSource()]
        self.left_threshold           = left_threshold
        self.top_threshold            = top_threshold
        self.vertical_search_window   = vertical_search_window
        self.horizontal_search_window = horizontal_search_window
        self.weight_proximity         = weight_proximity
        self.weight_alignment         = weight_alignment
        self.weight_reading_order     = weight_reading_order
        self.min_score                = min_score

    def group(
        self,
        flat_checkboxes: list[_FlatCheckbox],
        page_blocks:     list[dict],
    ) -> list[Selection]:
        if not flat_checkboxes:
            return []

        all_candidates: list[_Candidate] = []
        for source in self.candidate_sources:
            all_candidates.extend(source.candidates(page_blocks))

        sorted_cbs = sorted(flat_checkboxes, key=lambda cb: (cb.top, cb.left))
        clusters   = self._cluster(sorted_cbs)

        return [
            Selection(
                options=[
                    SelectionOption(text=cb.label, selected=cb.selected)
                    for cb in cluster
                ],
            )
            for cluster in clusters
        ]

    def _cluster(
        self,
        sorted_checkboxes: list[_FlatCheckbox],
    ) -> list[list[_FlatCheckbox]]:
        clusters: list[list[_FlatCheckbox]] = []
        current:  list[_FlatCheckbox]       = [sorted_checkboxes[0]]

        for cb in sorted_checkboxes[1:]:
            last         = current[-1]
            vertical_gap = cb.top  - last.top
            left_diff    = abs(cb.left - last.left)

            if vertical_gap <= self.top_threshold and left_diff <= self.left_threshold:
                current.append(cb)
            else:
                clusters.append(current)
                current = [cb]

        clusters.append(current)
        return clusters

    def _resolve_label(
        self,
        cluster:        list[_FlatCheckbox],
        all_candidates: list[_Candidate],
    ) -> str:
        window_candidates = self._gather_candidates(cluster, all_candidates)

        if not window_candidates:
            return ""

        scored = [
            (c, self._score_candidate(c, cluster, all_candidates))
            for c in window_candidates
        ]

        winner, best_score = max(scored, key=lambda x: x[1])

        return winner.text if best_score >= self.min_score else ""

    def _gather_candidates(
        self,
        cluster:        list[_FlatCheckbox],
        all_candidates: list[_Candidate],
    ) -> list[_Candidate]:
        cluster_top  = cluster[0].top
        cluster_left = min(cb.left for cb in cluster)

        return [
            c for c in all_candidates
            if c.top < cluster_top
            and (cluster_top - c.top) <= self.vertical_search_window
            and abs(c.left - cluster_left) <= self.horizontal_search_window
        ]

    def _score_candidate(
        self,
        candidate:      _Candidate,
        cluster:        list[_FlatCheckbox],
        all_candidates: list[_Candidate],
    ) -> float:
        p = self._score_proximity(candidate, cluster)
        a = self._score_alignment(candidate, cluster)
        r = self._score_reading_order(candidate, cluster, all_candidates)

        return (
            self.weight_proximity     * p +
            self.weight_alignment     * a +
            self.weight_reading_order * r
        )

    def _score_proximity(
        self,
        candidate: _Candidate,
        cluster:   list[_FlatCheckbox],
    ) -> float:
        cluster_top = cluster[0].top
        bottom      = candidate.top + candidate.height
        gap         = max(0.0, cluster_top - bottom)

        return 1.0 / (1.0 + gap / self.vertical_search_window)

    def _score_alignment(
        self,
        candidate: _Candidate,
        cluster:   list[_FlatCheckbox],
    ) -> float:
        cluster_left = min(cb.left for cb in cluster)
        left_diff    = abs(candidate.left - cluster_left)

        score = max(0.0, 1.0 - left_diff / self.horizontal_search_window)

        if candidate.left <= cluster_left:
            score = min(1.0, score + 0.05)

        return score

    def _score_reading_order(
        self,
        candidate:      _Candidate,
        cluster:        list[_FlatCheckbox],
        all_candidates: list[_Candidate],
    ) -> float:
        cluster_top   = cluster[0].top
        candidate_top = candidate.top

        intervening = sum(
            1 for c in all_candidates
            if candidate_top < c.top < cluster_top and c is not candidate
        )

        return 1.0 / (1.0 + intervening)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 3 — Signature extraction
# ─────────────────────────────────────────────────────────────────────────────

class SignatureExtractor:
    """Extracts SIGNATURE blocks from a page."""

    def extract(self, page_blocks: list) -> tuple[list[Signature], set[str]]:
        signatures = [
            Signature(present=True)
            for block in page_blocks
            if block["BlockType"] == "SIGNATURE"
        ]
        return signatures, set()


# ─────────────────────────────────────────────────────────────────────────────
# Phase 4 — Visual line reconstruction with fragment merging
# ─────────────────────────────────────────────────────────────────────────────

class VisualLineBuilder:
    """
    Builds reading-order lines from non-excluded Textract LINE blocks by
    merging fragments that Textract split across multiple LINE blocks.
    """

    def __init__(
        self,
        line_threshold:      float = 0.005,
        merge_gap_threshold: float = 0.050,
    ):
        self.line_threshold      = line_threshold
        self.merge_gap_threshold = merge_gap_threshold

    def build(
        self,
        page_blocks:          list,
        excluded_line_ids:    set[str],
        index:                BlockIndex | None = None,
        word_id_to_selected:  dict[str, bool] | None = None,
    ) -> list[str]:
        tokens = self._collect_tokens(
            page_blocks, excluded_line_ids, index, word_id_to_selected
        )

        if not tokens:
            return []

        tokens.sort(key=lambda t: (t["top"], t["left"]))

        rows = self._merge_rows(tokens)

        return [
            " ".join(t["text"] for t in sorted(row, key=lambda t: t["left"]))
            for row in rows
        ]

    def _collect_tokens(
        self,
        page_blocks:          list,
        excluded_line_ids:    set[str],
        index:                BlockIndex | None,
        word_id_to_selected:  dict[str, bool] | None,
    ) -> list[dict]:
        tokens: list[dict] = []

        for block in page_blocks:

            if block["BlockType"] != "LINE":
                continue

            if block["Id"] in excluded_line_ids:
                continue

            bbox  = block.get("Geometry", {}).get("BoundingBox", {})
            left  = bbox.get("Left",  0.0)
            width = bbox.get("Width", 0.0)

            text = self._line_text(block, index, word_id_to_selected)

            tokens.append({
                "text":  text,
                "top":   bbox.get("Top", 0.0),
                "left":  left,
                "right": left + width,
            })

        return tokens

    def _line_text(
        self,
        line_block:           dict,
        index:                BlockIndex | None,
        word_id_to_selected:  dict[str, bool] | None,
    ) -> str:
        if not index or not word_id_to_selected:
            return line_block.get("Text", "")

        words = [w for w in index.children_of(line_block) if w["BlockType"] == "WORD"]

        if not words:
            return line_block.get("Text", "")

        parts: list[str] = []
        for word in words:
            parts.append(word.get("Text", ""))
            if word["Id"] in word_id_to_selected:
                parts.append("✓" if word_id_to_selected[word["Id"]] else "✗")

        return " ".join(parts)

    def _merge_rows(self, sorted_tokens: list[dict]) -> list[list[dict]]:
        rows: list[list[dict]]  = []
        current_row: list[dict] = [sorted_tokens[0]]

        for token in sorted_tokens[1:]:

            last           = current_row[-1]
            vertical_diff  = abs(token["top"] - last["top"])
            horizontal_gap = token["left"] - last["right"]

            if (
                vertical_diff  <= self.line_threshold
                and horizontal_gap <= self.merge_gap_threshold
            ):
                current_row.append(token)
            else:
                rows.append(current_row)
                current_row = [token]

        rows.append(current_row)
        return rows
