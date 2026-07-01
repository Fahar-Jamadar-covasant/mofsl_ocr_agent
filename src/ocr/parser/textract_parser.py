from src.ocr.parser.block_index import BlockIndex
from src.ocr.parser.models import PageResult
from src.ocr.parser.reading_order import (
    TableExtractor,
    SelectionExtractor,
    SelectionGrouper,
    SignatureExtractor,
    VisualLineBuilder,
)


class TextractParser:

    def __init__(self, textract: dict):
        self.index       = BlockIndex(textract["Blocks"])
        self._tables     = TableExtractor(self.index)
        self._selections = SelectionExtractor(self.index)
        self._grouper    = SelectionGrouper()
        self._signatures = SignatureExtractor()
        self._lines      = VisualLineBuilder()

    def parse(self, page: int) -> PageResult:
        page_blocks = self.index.get_page_blocks(page)

        tables,          table_line_ids     = self._tables.extract(page_blocks)
        flat_checkboxes, selection_line_ids = self._selections.extract(page_blocks)
        selections                          = self._grouper.group(flat_checkboxes, page_blocks)
        signatures,      signature_line_ids = self._signatures.extract(page_blocks)

        word_id_to_selected: dict[str, bool] = {
            word_id: cb.selected
            for cb in flat_checkboxes
            for word_id in cb.word_ids
        }

        excluded_line_ids = table_line_ids | selection_line_ids | signature_line_ids
        lines = self._lines.build(
            page_blocks,
            excluded_line_ids,
            index=self.index,
            word_id_to_selected=word_id_to_selected,
        )

        return PageResult(
            page=page,
            lines=lines,
            tables=tables,
            selections=selections,
            signatures=signatures,
        )

    def parse_all(self) -> list[PageResult]:
        return [self.parse(page_num) for page_num in self.index.page_numbers()]
