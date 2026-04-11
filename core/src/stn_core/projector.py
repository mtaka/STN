"""Projector — bidirectional conversion between STN values and plain Python objects.

Value → obj / JSON / YAML:
    value.to_obj()    → dict or list (recursive)
    value.to_json()   → JSON string
    value.to_yaml()   → YAML string

Document → obj:
    doc.to_obj()      → dict of all top-level keyed entries

dict → Document:
    Document.from_dict(d, include_defs=False)
        include_defs=False  plain mode: keys → VEntity fields
        include_defs=True   keys prefixed with "@@" / "@%" are treated as
                            variable / typedef declarations; others as entries

Key mapping rules (to_obj):
    VText    → str
    VNumber  → int if value == int(value), else float
    VBool    → bool
    VDate    → str (ISO-8601)
    VEnum    → str
    VList    → list
    VEntity  → dict  (fields only; type_name stored under "@type" if present)
              → list if all keys are positional (_0, _1, ...)
    Empty    → None
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from .values import Value, VText, VNumber, VDate, VBool, VEnum, VList, VEntity, _Empty, Empty

if TYPE_CHECKING:
    from .document import Document


# ---------------------------------------------------------------------------
# Value → dict
# ---------------------------------------------------------------------------

def _is_positional_list(entity: VEntity) -> bool:
    """True if entity is a pure positional collection (all keys _0, _1, … in order).

    Such entities are serialized as lists rather than dicts.
    Typed entities (type_name set) and entities with props are never treated as lists.
    """
    if entity.type_name or entity.props:
        return False
    if not entity.fields:
        return False
    keys = list(entity.fields.keys())
    return keys == [f"_{i}" for i in range(len(keys))]


def value_to_obj(value: Value) -> Any:
    """Recursively convert a Value to a plain Python object (dict or list)."""
    if isinstance(value, _Empty):
        return None
    if isinstance(value, VText):
        return value.value
    if isinstance(value, VNumber):
        v = value.value
        return int(v) if v == int(v) else v
    if isinstance(value, VBool):
        return value.value
    if isinstance(value, VDate):
        return value.value
    if isinstance(value, VEnum):
        return value.value
    if isinstance(value, VList):
        return [value_to_obj(item) for item in value.items]
    if isinstance(value, VEntity):
        # Pure positional entity (_0, _1, …) → list
        if _is_positional_list(value):
            return [value_to_obj(v) for v in value.fields.values()]
        result: dict[str, Any] = {}
        if value.type_name:
            result["@type"] = value.type_name
        for k, v in value.fields.items():
            result[k] = value_to_obj(v)
        return result
    return repr(value)


def value_to_json(value: Value, **kwargs) -> str:
    """Serialize a Value to a JSON string."""
    return json.dumps(value_to_obj(value), ensure_ascii=False, **kwargs)


def value_to_yaml(value: Value, **kwargs) -> str:
    """Serialize a Value to a YAML string."""
    import yaml
    return yaml.dump(value_to_obj(value), allow_unicode=True, **kwargs)


# ---------------------------------------------------------------------------
# Document → dict
# ---------------------------------------------------------------------------

def document_to_obj(doc: "Document") -> "dict[str, Any] | list | Any":
    """Convert document top-level entries to a plain Python object.

    - All named entries          → dict
    - All unnamed, one entry     → value_to_obj of that entry (unwrapped)
    - All unnamed, many entries  → list of values
    - Mixed named/unnamed        → dict (unnamed keyed by 1-origin string index)
    """
    entries = doc._doc_entries
    if not entries:
        return {}

    all_unnamed = all(key is None for key, _ in entries)
    if all_unnamed:
        values = [value_to_obj(val) for _, val in entries]
        return values[0] if len(values) == 1 else values

    result: dict[str, Any] = {}
    for i, (key, val) in enumerate(entries, start=1):
        k = key if key is not None else str(i)
        result[k] = value_to_obj(val)
    return result


def document_to_yaml(doc: "Document", **kwargs) -> str:
    """Serialize a Document's top-level entries to a YAML string."""
    import yaml
    return yaml.dump(document_to_obj(doc), allow_unicode=True, **kwargs)


# ---------------------------------------------------------------------------
# dict → Document  (from_dict)
# ---------------------------------------------------------------------------

def dict_to_document(d: dict, include_defs: bool = False) -> "Document":
    """Build a Document from a plain Python dict.

    Parameters
    ----------
    d:
        Source dict.
    include_defs:
        If False (plain mode), every key/value pair becomes a named top-level
        entry in the document (equivalent to ``:key value``).

        If True (declaration mode), keys are interpreted as follows:
          - ``"@@name"`` → local variable declaration
          - ``"@%Name"`` → typedef declaration (value must be a dict of member names)
          - ``"@#name"`` → symbol declaration
          - Any other key → named top-level entry

    Returns
    -------
    Document with the values populated into ``_doc_entries`` / ``locals_`` /
    ``symbols_`` / ``typedefs`` as appropriate.
    """
    from .document import Document
    from .locator import _finalize_doc

    doc = Document()

    if not include_defs:
        # Plain mode: all keys become named top-level entries
        for key, raw in d.items():
            val = _raw_to_value(raw)
            doc._doc_entries.append((str(key), val))
            doc.results.append(val)
    else:
        # Declaration mode
        for key, raw in d.items():
            key = str(key)
            if key.startswith("@@"):
                name = key[2:]
                val = _raw_to_value(raw)
                doc.environment.set_local(name, val)
            elif key.startswith("@%"):
                name = key[2:]
                _register_typedef(doc, name, raw)
            elif key.startswith("@#"):
                name = key[2:]
                val = _raw_to_value(raw)
                doc.environment.set_symbol(name, val)
            else:
                val = _raw_to_value(raw)
                doc._doc_entries.append((key, val))
                doc.results.append(val)

    _finalize_doc(doc)
    return doc


def _raw_to_value(raw: Any) -> Value:
    """Convert a plain Python object to a Value."""
    if raw is None:
        return Empty
    if isinstance(raw, bool):
        return VBool(raw)
    if isinstance(raw, int):
        return VNumber(float(raw))
    if isinstance(raw, float):
        return VNumber(raw)
    if isinstance(raw, str):
        return VText(raw)
    if isinstance(raw, list):
        return VList(items=[_raw_to_value(item) for item in raw])
    if isinstance(raw, dict):
        entity = VEntity(typedef=None, type_name=raw.get("@type"))
        for k, v in raw.items():
            if k == "@type":
                continue
            entity.fields[k] = _raw_to_value(v)
        return entity
    return VText(str(raw))


def _register_typedef(doc: "Document", name: str, raw: Any) -> None:
    """Register a TypeDef from a dict of member-name → kind-string pairs.

    Kind strings:
        ""        → text (default)
        "%"       → number
        "%b"      → bool
        "%d"      → date
        "%f"      → float (alias for number)
        "%s(A B)" → enum with choices A, B
    """
    from .typedef import TypeDef, MemberDef

    members: list[MemberDef] = []
    if isinstance(raw, dict):
        for mname, kind_str in raw.items():
            if mname == "@type":
                continue
            md = _parse_member_kind(mname, str(kind_str))
            members.append(md)

    td = TypeDef(name=name, members=members)
    doc.environment.register_typedef(td)


def _parse_member_kind(name: str, kind_str: str) -> "MemberDef":
    from .typedef import MemberDef
    kind_str = kind_str.strip()
    if kind_str in ("", "text"):
        return MemberDef(name=name, kind="text", choices=[])
    if kind_str in ("%", "%f", "number"):
        return MemberDef(name=name, kind="number", choices=[])
    if kind_str in ("%b", "bool"):
        return MemberDef(name=name, kind="bool", choices=[])
    if kind_str in ("%d", "date"):
        return MemberDef(name=name, kind="date", choices=[])
    if kind_str.startswith("%s(") and kind_str.endswith(")"):
        choices = kind_str[3:-1].split()
        return MemberDef(name=name, kind="enum", choices=choices)
    # Unknown kind — treat as text
    return MemberDef(name=name, kind="text", choices=[])
