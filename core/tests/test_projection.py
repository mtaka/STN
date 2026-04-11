"""Tests for Projection: to_obj / to_json / from_dict."""

import json

import pytest

from stn_core import Document, Empty
from stn_core.values import VNumber, VText, VBool, VEntity, VList, VEnum


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def doc(src: str) -> Document:
    return Document.loads(src)


# ---------------------------------------------------------------------------
# VEntity.to_obj
# ---------------------------------------------------------------------------

def test_entity_to_obj_basic():
    d = doc("@@x (:name [Joe] :age 36)")
    e = d.locals_["x"]
    assert e.to_obj() == {"name": "Joe", "age": 36}


def test_entity_to_obj_float():
    d = doc("@@x (:ratio 3.14)")
    e = d.locals_["x"]
    result = e.to_obj()
    assert abs(result["ratio"] - 3.14) < 1e-9


def test_entity_to_obj_nested():
    d = doc("@@x (:person (:name [Alice] :score 90))")
    e = d.locals_["x"]
    assert e.to_obj() == {"person": {"name": "Alice", "score": 90}}


def test_entity_to_obj_with_type_name():
    d = doc("@%P (:name)\n@@x %P(:name [Bob])")
    e = d.locals_["x"]
    result = e.to_obj()
    assert result["@type"] == "P"
    assert result["name"] == "Bob"


def test_entity_to_obj_unnamed_fields():
    """Positional-only entity is serialized as a list, not a dict."""
    d = doc("@@x (10 20 30)")
    e = d.locals_["x"]
    result = e.to_obj()
    assert result == [10, 20, 30]


# ---------------------------------------------------------------------------
# VList.to_obj → to_json → to_yaml
# ---------------------------------------------------------------------------

def test_vlist_to_obj():
    lst = VList(items=[VNumber(1), VText("a"), VBool(True)])
    assert lst.to_obj() == [1, "a", True]


def test_entity_to_json():
    d = doc("@@x (:name [Joe] :score 100)")
    e = d.locals_["x"]
    obj = json.loads(e.to_json())
    assert obj == {"name": "Joe", "score": 100}


def test_entity_to_json_indent():
    d = doc("@@x (:a 1)")
    e = d.locals_["x"]
    s = e.to_json(indent=2)
    assert "\n" in s
    assert json.loads(s) == {"a": 1}


def test_entity_to_yaml():
    import yaml
    d = doc("@@x (:name [Alice] :age 30)")
    e = d.locals_["x"]
    s = e.to_yaml()
    obj = yaml.safe_load(s)
    assert obj == {"name": "Alice", "age": 30}


def test_entity_to_yaml_unicode():
    import yaml
    d = doc("@@x (:name [山田])")
    e = d.locals_["x"]
    s = e.to_yaml()
    assert "山田" in s   # allow_unicode=True


def test_vlist_to_yaml():
    import yaml
    lst = VList(items=[VNumber(1), VNumber(2), VNumber(3)])
    obj = yaml.safe_load(lst.to_yaml())
    assert obj == [1, 2, 3]


def test_doc_to_yaml():
    import yaml
    d = doc(":title [Hello] ; :count 3")
    s = d.to_yaml()
    obj = yaml.safe_load(s)
    assert obj == {"title": "Hello", "count": 3}


# ---------------------------------------------------------------------------
# Document.to_obj
# ---------------------------------------------------------------------------

def test_doc_to_obj_named_entries():
    d = doc(":title [Hello] ; :count 3")
    result = d.to_obj()
    assert result == {"title": "Hello", "count": 3}


def test_doc_to_obj_unnamed_entries():
    """All-unnamed entries → list of values."""
    d = doc("1 ; 2")
    assert d.to_obj() == [1, 2]


def test_doc_to_obj_single_unnamed_unwrapped():
    """Single unnamed entry → value directly (not wrapped in list)."""
    d = doc("(:a 1 :b 2)")
    assert d.to_obj() == {"a": 1, "b": 2}


def test_doc_to_obj_semicolon_in_nested():
    """`(a b c; d e f)` — `;` inside () splits into sub-lists."""
    d = doc("(a b c; d e f)")
    assert d.to_obj() == [["a", "b", "c"], ["d", "e", "f"]]


def test_doc_to_obj_empty():
    d = doc("")
    assert d.to_obj() == {}


# ---------------------------------------------------------------------------
# Document.from_dict — plain mode
# ---------------------------------------------------------------------------

def test_from_dict_plain_strings():
    d = Document.from_dict({"name": "Alice", "city": "Tokyo"})
    assert d.getval("name") == VText("Alice")
    assert d.getval("city") == VText("Tokyo")


def test_from_dict_plain_numbers():
    d = Document.from_dict({"age": 30, "score": 99.5})
    result = d.getval("age")
    assert result == VNumber(30)


def test_from_dict_plain_nested():
    d = Document.from_dict({"person": {"name": "Bob", "age": 25}})
    entity = d.getval("person")
    assert isinstance(entity, VEntity)
    assert entity.fields["name"] == VText("Bob")
    assert entity.fields["age"] == VNumber(25)


def test_from_dict_plain_list():
    d = Document.from_dict({"items": [1, 2, 3]})
    lst = d.getval("items")
    assert isinstance(lst, VList)
    assert lst.items == [VNumber(1), VNumber(2), VNumber(3)]


def test_from_dict_plain_bool():
    d = Document.from_dict({"flag": True, "other": False})
    assert d.getval("flag") == VBool(True)
    assert d.getval("other") == VBool(False)


def test_from_dict_parent_is_set():
    """from_dict() triggers finalization — entities get document reference."""
    d = Document.from_dict({"x": {"a": 1}})
    e = d.getval("x")
    assert isinstance(e, VEntity)
    assert e.document is d


# ---------------------------------------------------------------------------
# Document.from_dict — include_defs mode
# ---------------------------------------------------------------------------

def test_from_dict_local_var():
    d = Document.from_dict({"@@taro": {"name": "Taro", "age": 20}}, include_defs=True)
    assert "taro" in d.locals_
    e = d.locals_["taro"]
    assert e.fields["name"] == VText("Taro")


def test_from_dict_symbol():
    d = Document.from_dict({"@#R001": {"x": 10}}, include_defs=True)
    assert "R001" in d.symbols
    e = d.symbols["R001"]
    assert e.fields["x"] == VNumber(10)


def test_from_dict_typedef():
    d = Document.from_dict(
        {"@%Person": {"name": "", "age": "%"}},
        include_defs=True,
    )
    assert "Person" in d.typedefs
    td = d.typedefs["Person"]
    members = {m.name: m.kind for m in td.members}
    assert members["name"] == "text"
    assert members["age"] == "number"


def test_from_dict_mixed():
    d = Document.from_dict(
        {
            "@%Tag": {"label": ""},
            "@@item": {"name": "Widget"},
            "title": "My Doc",
        },
        include_defs=True,
    )
    assert "Tag" in d.typedefs
    assert "item" in d.locals_
    assert d.getval("title") == VText("My Doc")


# ---------------------------------------------------------------------------
# Round-trip: STN → to_obj → from_dict → to_obj
# ---------------------------------------------------------------------------

def test_roundtrip_basic():
    original = doc(":name [Alice] ; :age 30")
    d1 = original.to_obj()
    restored = Document.from_dict(d1)
    assert restored.to_obj() == d1


def test_roundtrip_nested():
    original = doc("@@x (:inner (:a 1 :b 2))")
    e = original.locals_["x"]
    d1 = e.to_obj()
    restored_entity = Document.from_dict({"x": d1}).getval("x")
    assert isinstance(restored_entity, VEntity)
    assert restored_entity.to_obj() == d1
