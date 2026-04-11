"""Document — the final output of STN Core evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field

from .environment import Environment
from .values import Value
from .typedef import TypeDef


@dataclass
class Document:
    """Holds the fully evaluated result of an STN source."""

    environment: Environment = field(default_factory=Environment)
    results: list[Value] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Not dataclass fields — managed manually
        self._last_result: Value | None = None
        self._doc_entries: list[tuple[str | None, Value]] = []

    # -- Convenience accessors ------------------------------------------

    @property
    def locals_(self) -> dict[str, Value]:
        return self.environment.locals_

    @property
    def symbols(self) -> dict[str, Value]:
        return self.environment.symbols

    @property
    def publics(self) -> dict[str, Value]:  # backward compat alias
        return self.environment.symbols

    @property
    def typedefs(self) -> dict[str, TypeDef]:
        return self.environment.typedefs

    @property
    def last_result(self) -> Value | None:
        """The last expression value produced by the most recent merge()."""
        return self._last_result

    # -- Top-level SObject interface ------------------------------------

    def getval(self, key: "str | int") -> Value:
        """Access top-level results by name or 1-origin index.

        - str  → first entry whose top-level key matches
        - int  → 1-origin index into all top-level result entries
        - Missing key / out-of-range index → Empty
        """
        from .values import Empty

        if isinstance(key, int):
            if key < 1:
                return Empty
            idx = key - 1
            if idx < len(self._doc_entries):
                return self._doc_entries[idx][1]
            return Empty

        for entry_key, val in self._doc_entries:
            if entry_key == key:
                return val
        return Empty

    # -- Locator API -------------------------------------------------------

    def locate(self, path: "str | int", callback=lambda x: x):
        """Yield (callback(result), path_str) pairs across the document.

        Path prefixes:
            "#name"   → symbol (@# variable)
            "@name"   → local variable (@@ variable)
            "%Name"   → typedef
            int / "N" → 1-origin index into top-level entries
            "key"     → named top-level entry key
        """
        from .locator import locate_document
        return locate_document(self, path, callback)

    def get(self, path: "str | int") -> list:
        """Return all locate() results as a list."""
        return [v for v, _ in self.locate(path)]

    def get_first(self, path: "str | int") -> Value:
        """Return the first locate() result, or Empty."""
        from .values import Empty
        for v, _ in self.locate(path):
            return v  # type: ignore[return-value]
        return Empty

    # -- Projection -------------------------------------------------------

    def to_obj(self) -> dict:
        """Return all named top-level entries as a plain dict.

        Unnamed entries use their 1-origin index (as string) as key.
        """
        from .projector import document_to_obj
        return document_to_obj(self)

    def to_yaml(self, **kwargs) -> str:
        """Serialize top-level entries to a YAML string."""
        from .projector import document_to_yaml
        return document_to_yaml(self, **kwargs)

    @staticmethod
    def from_dict(d: dict, include_defs: bool = False) -> "Document":
        """Build a Document from a plain dict.

        Parameters
        ----------
        d:
            Source dict.
        include_defs:
            False (default) — plain mode: all keys become named top-level entries.
            True            — declaration mode: keys prefixed with ``@@`` / ``@%``
                              / ``@#`` are registered as locals / typedefs / symbols.
        """
        from .projector import dict_to_document
        return dict_to_document(d, include_defs=include_defs)

    # -- Class-level constructors (Loader) ---------------------------------

    @staticmethod
    def loads(src: str) -> "Document":
        """Parse and evaluate an STN source string."""
        from stn import parse
        from .evaluator import evaluate
        return evaluate(parse(src))

    @staticmethod
    def load(path) -> "Document":
        """Load and evaluate an STN file."""
        from pathlib import Path
        return Document.loads(Path(path).read_text(encoding="utf-8"))

    # -- Incremental evaluation -----------------------------------------

    def merge(self, result) -> None:
        """Merge a ParseResult into this Document (used by STNRepl).

        - Type definitions (@%) → added/overwritten in typedefs
        - Local variables (@@) → added/overwritten in locals_
        - Public variables (@#) → added/overwritten in publics
        - Data blocks → merged into _DATA entity
        - Expression results → appended to results; last one stored in last_result
        """
        from .evaluator import _evaluate_into
        from .locator import _finalize_doc
        new_entries = _evaluate_into(result, self.environment)
        for key, val in new_entries:
            self.results.append(val)
            self._doc_entries.append((key, val))
        self._last_result = new_entries[-1][1] if new_entries else None
        _finalize_doc(self)
