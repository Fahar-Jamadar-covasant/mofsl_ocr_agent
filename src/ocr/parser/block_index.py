class BlockIndex:
    """
    Efficient lookup structures for a Textract block list.

    Provides:
    - O(1) block lookup by Id
    - O(1) page-grouped block access
    - Relationship traversal helpers (CHILD, VALUE)
    """

    def __init__(self, blocks: list):

        self._by_id: dict = {block["Id"]: block for block in blocks}

        self._by_page: dict = {}
        for block in blocks:
            page = block.get("Page")
            if page is not None:
                self._by_page.setdefault(page, []).append(block)

    # ── Lookups ───────────────────────────────────────────────────────────────

    def get(self, block_id: str) -> dict | None:
        return self._by_id.get(block_id)

    def get_page_blocks(self, page: int) -> list:
        return self._by_page.get(page, [])

    def page_numbers(self) -> list:
        return sorted(self._by_page.keys())

    # ── Relationship helpers ──────────────────────────────────────────────────

    def children_of(self, block: dict) -> list:
        """Return every block that is a CHILD of the given block."""
        ids = []
        for rel in block.get("Relationships", []):
            if rel["Type"] == "CHILD":
                ids.extend(rel["Ids"])
        return [self._by_id[i] for i in ids if i in self._by_id]

    def values_of(self, block: dict) -> list:
        """Return every block that is a VALUE of the given block."""
        ids = []
        for rel in block.get("Relationships", []):
            if rel["Type"] == "VALUE":
                ids.extend(rel["Ids"])
        return [self._by_id[i] for i in ids if i in self._by_id]
