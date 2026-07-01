from dataclasses import dataclass, field
from typing import List


@dataclass
class SelectionOption:
    text: str
    selected: bool


@dataclass
class Selection:
    options: List[SelectionOption] = field(default_factory=list)


@dataclass
class Table:
    headers: List[str]
    rows: List[List[str]]


@dataclass
class Signature:
    present: bool = True


@dataclass
class PageResult:
    page: int
    lines: List[str] = field(default_factory=list)
    tables: List[Table] = field(default_factory=list)
    selections: List[Selection] = field(default_factory=list)
    signatures: List[Signature] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "page": self.page,
            "lines": self.lines,
            "tables": [
                {
                    "headers": t.headers,
                    "rows": t.rows,
                }
                for t in self.tables
            ],
            "selections": [
                {
                    "options": [
                        {"text": o.text, "selected": o.selected}
                        for o in s.options
                    ],
                }
                for s in self.selections
            ],
            "signatures": [
                {"present": sig.present}
                for sig in self.signatures
            ],
        }
