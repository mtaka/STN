"""Locator — path-based navigation on evaluated STN values.

Public API (attached as methods on VEntity / VList / Document):

    value.locate(path, callback=identity)  → generator of (result, path_str)
    value.get(path)                        → list[Value]
    value.get_first(path)                  → Value (first match, or Empty)

Path syntax:
    int / "N"         1-origin positional index
    "name"            field / prop name
    "a.b.c"           hierarchical access
    "(a b)"           multiple accessors (yields each)
    "?(:key val)"     query filter (STN condition syntax)
    "*"               all direct children (fields of VEntity, items of VList)
    "#sym"            symbol-id search in VList/VEntity
    "#name"           symbol lookup in Document
    "@name"           local variable in Document
    "%Name"           typedef in Document
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Generator

from .values import Value, VEntity, VList, _Empty, Empty

if TYPE_CHECKING:
    from .document import Document

PathResult = tuple[Any, str]
_identity: Callable = lambda x: x  # noqa: E731


# ---------------------------------------------------------------------------
# Value-level locate
# ---------------------------------------------------------------------------

def locate_value(
    value: Value,
    path: "str | int",
    callback: Callable = _identity,
) -> Generator[PathResult, None, None]:
    """Navigate *value* using *path* and yield ``(callback(result), path_str)``."""
    if isinstance(path, int):
        path = str(path)
    path = path.strip()

    if not path:
        return

    # -- Wildcard: "*" ---------------------------------------------------
    if path == "*":
        yield from _locate_wildcard(value, callback)
        return

    # -- Query: "?(:key val ...)" -----------------------------------------
    if path.startswith("?(") and path.endswith(")"):
        yield from _locate_query(value, path, callback)
        return

    # -- Multiple: "(a b c)" ----------------------------------------------
    if path.startswith("(") and path.endswith(")"):
        inner = path[1:-1].strip()
        for part in inner.split():
            yield from locate_value(value, part, callback)
        return

    # -- Symbol-id: "#sym" ------------------------------------------------
    if path.startswith("#"):
        from .getter import apply_symbol_getter
        result = apply_symbol_getter(value, path[1:])
        if not isinstance(result, _Empty):
            yield callback(result), path
        return

    # -- Hierarchical: "a.b.c" --------------------------------------------
    if "." in path:
        head, tail = path.split(".", 1)
        if head == "*":
            # Wildcard segment mid-chain: expand all children, then recurse
            for child_val, child_key in _locate_wildcard(value, _identity):
                for result, sub_path in locate_value(child_val, tail, callback):
                    yield result, f"{child_key}.{sub_path}"
            return
        from .getter import apply_getter
        intermediate = apply_getter(value, head)
        if not isinstance(intermediate, _Empty):
            for result, sub_path in locate_value(intermediate, tail, callback):
                yield result, f"{head}.{sub_path}"
        return

    # -- Simple field / index: "name" or "N" ------------------------------
    from .getter import apply_getter
    result = apply_getter(value, path)
    if not isinstance(result, _Empty):
        yield callback(result), path


def _locate_wildcard(
    value: Value,
    callback: Callable,
) -> Generator[PathResult, None, None]:
    """Handle ``*`` wildcard — yield all direct children with their key/index."""
    if isinstance(value, VEntity):
        for k, v in value.fields.items():
            yield callback(v), k
    elif isinstance(value, VList):
        for i, item in enumerate(value.items, start=1):
            yield callback(item), str(i)


def _locate_query(
    value: Value,
    path: str,
    callback: Callable,
) -> Generator[PathResult, None, None]:
    """Handle ``?(conditions)`` query paths."""
    inner = path[2:-1]  # strip "?(" and ")"
    try:
        from stn import parse as _stn_parse  # type: ignore
        from stn.nodes import Node  # type: ignore
        pr = _stn_parse(f"({inner})")
        if not pr.ast.items:
            return
        condition_node = pr.ast.items[0]
        if not isinstance(condition_node, Node):
            return
    except Exception:
        return

    from .getter import apply_query_locator
    matched = apply_query_locator(value, condition_node, None)

    if isinstance(matched, _Empty):
        return
    if isinstance(matched, VList):
        for item in matched.items:
            yield callback(item), path
    else:
        yield callback(matched), path


# ---------------------------------------------------------------------------
# Document-level locate
# ---------------------------------------------------------------------------

def locate_document(
    doc: "Document",
    path: "str | int",
    callback: Callable = _identity,
) -> Generator[PathResult, None, None]:
    """Navigate *doc* using *path* and yield ``(callback(result), path_str)``.

    Special prefixes (resolved against the document environment):
        ``#name``   → symbol (``@#`` variable)
        ``@name``   → local variable (``@@`` variable)
        ``%Name``   → typedef

    Flat access (top-level entries):
        ``"key"``   → named entry
        int / ``"N"`` → 1-origin index

    Hierarchical access (chains from a top-level entry):
        ``"key.rest"``     → get *key*, then ``locate_value(value, rest)``
        ``"key?(cond)"``   → get *key*, then ``locate_value(value, '?(cond)')``
        ``"key.(…)"``      → get *key*, then multi-accessor

    The dot (``.``) and query (``?``) separators can be chained as deeply
    as needed.  Applies *callback* to every leaf result.
    """
    if isinstance(path, int):
        path = str(path)
    path = path.strip()

    if not path:
        return

    # -- Symbol: "#name" --------------------------------------------------
    if path.startswith("#"):
        name = path[1:]
        val = doc.environment.get_symbol(name)
        if not isinstance(val, _Empty):
            yield callback(val), path
        return

    # -- Local variable: "@name" ------------------------------------------
    if path.startswith("@"):
        name = path[1:]
        val = doc.environment.get_local(name)
        if not isinstance(val, _Empty):
            yield callback(val), path
        return

    # -- TypeDef: "%Name" -------------------------------------------------
    if path.startswith("%"):
        name = path[1:]
        td = doc.environment.typedefs.get(name)
        if td is not None:
            yield callback(td), path
        return

    # -- Hierarchical: "key.rest" or "key?(cond)" -------------------------
    base, rest = _split_doc_path(path)
    if rest is not None:
        base_val = _doc_getval(doc, base)
        if not isinstance(base_val, _Empty):
            sep = "" if rest.startswith("?(") else "."
            for result, sub_path in locate_value(base_val, rest, callback):
                yield result, f"{base}{sep}{sub_path}"
        return

    # -- Flat: integer index or named key ---------------------------------
    val = _doc_getval(doc, path)
    if not isinstance(val, _Empty):
        yield callback(val), path


def _doc_getval(doc: "Document", path: str) -> "Value":
    """Resolve a flat key or integer index against doc._doc_entries."""
    try:
        return doc.getval(int(path))
    except ValueError:
        return doc.getval(path)


def _split_doc_path(path: str) -> "tuple[str, str | None]":
    """Split ``'base.rest'`` or ``'base?(cond)'`` into ``(base, rest)``.

    Returns ``(path, None)`` when no separator is found.
    Only recognises ``.`` and ``?(`` at the top level (not inside parens).
    """
    depth = 0
    for i, ch in enumerate(path):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif depth == 0:
            if ch == "." and i > 0:
                return path[:i], path[i + 1:]
            if ch == "?" and i > 0 and i + 1 < len(path) and path[i + 1] == "(":
                return path[:i], path[i:]
    return path, None


# ---------------------------------------------------------------------------
# DOM finalization — sets _parent / _document after evaluation
# ---------------------------------------------------------------------------

def _finalize_doc(doc: "Document") -> None:
    """Post-evaluation pass: set ``_parent`` / ``_document`` on all container values.

    Called at the end of ``evaluate()`` and each ``Document.merge()``.
    Already-attached nodes (``_parent is not None``) are skipped to avoid
    overwriting valid parent references during incremental REPL evaluation.
    """
    # Top-level expression entries
    for _, val in doc._doc_entries:
        _set_context(val, doc, doc)
    # Locals (@@) and symbols (@#) may hold deep trees
    for val in doc.environment.locals_.values():
        _set_context(val, doc, doc)
    for val in doc.environment.symbols.values():
        _set_context(val, doc, doc)


def _set_context(val: Value, parent: Any, document: "Document") -> None:
    """Recursively attach *parent* and *document* to container nodes."""
    if isinstance(val, VEntity):
        if val._parent is None:
            val._parent = parent
            val._document = document
        for child in list(val.fields.values()) + list(val.props.values()):
            _set_context(child, val, document)
    elif isinstance(val, VList):
        if val._parent is None:
            val._parent = parent
            val._document = document
        for item in val.items:
            _set_context(item, val, document)
