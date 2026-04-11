"""Tests for the Locator API: locate / get / get_first on values and Document."""

import pytest

from stn_core import Document, Empty
from stn_core.values import VNumber, VText, VList, VEntity


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def doc(src: str) -> Document:
    return Document.loads(src)


# ---------------------------------------------------------------------------
# DOM — parent / document references
# ---------------------------------------------------------------------------

def test_entity_parent_is_document():
    d = doc("@@x (:a 1)")
    e = d.locals_["x"]
    assert isinstance(e, VEntity)
    assert e.parent is d
    assert e.document is d


def test_nested_entity_parent():
    d = doc("@@x (:inner (:a 1))")
    outer = d.locals_["x"]
    inner = outer.fields["inner"]
    assert isinstance(inner, VEntity)
    assert inner.parent is outer
    assert inner.document is d


def test_vlist_parent():
    """VList created by a multi-match query has parent/document set."""
    from stn_core.locator import _finalize_doc
    # Build a VList manually and finalize it into a mock document
    d = doc("")
    lst = VList(items=[VEntity(typedef=None, type_name=None)])
    d._doc_entries.append(("items", lst))
    _finalize_doc(d)
    assert lst.parent is d
    assert lst.document is d
    # The child entity inside the list should also be attached
    child = lst.items[0]
    assert child.parent is lst
    assert child.document is d


def test_unattached_entity_has_none_parent():
    e = VEntity(typedef=None, type_name=None)
    assert e.parent is None
    assert e.document is None


# ---------------------------------------------------------------------------
# VEntity.locate — simple field / index
# ---------------------------------------------------------------------------

def test_entity_locate_field():
    d = doc("@@x (:name [Joe] :age 36)")
    e = d.locals_["x"]
    results = list(e.locate("name"))
    assert len(results) == 1
    val, path = results[0]
    assert val == VText("Joe")
    assert path == "name"


def test_entity_locate_index():
    d = doc("@@x (:a 1 :b 2)")
    e = d.locals_["x"]
    assert e.get_first(1) == VNumber(1)
    assert e.get_first(2) == VNumber(2)


def test_entity_locate_missing_field():
    d = doc("@@x (:a 1)")
    e = d.locals_["x"]
    assert e.get_first("missing") is Empty
    assert e.get("missing") == []


def test_entity_locate_returns_generator():
    d = doc("@@x (:name [Joe])")
    e = d.locals_["x"]
    gen = e.locate("name")
    # Can iterate twice by calling locate() again
    assert e.get_first("name") == VText("Joe")
    assert e.get_first("name") == VText("Joe")


# ---------------------------------------------------------------------------
# VEntity.locate — hierarchical path
# ---------------------------------------------------------------------------

def test_entity_locate_hierarchical():
    d = doc("@@x (:person (:name [Alice] :age 30))")
    e = d.locals_["x"]
    result = e.get_first("person.name")
    assert result == VText("Alice")


def test_entity_locate_hierarchical_path_string():
    d = doc("@@x (:a (:b (:c 99)))")
    e = d.locals_["x"]
    val, path = next(iter(e.locate("a.b.c")))
    assert val == VNumber(99)
    assert path == "a.b.c"


def test_entity_locate_hierarchical_missing_mid():
    d = doc("@@x (:a 1)")
    e = d.locals_["x"]
    assert e.get_first("a.b") is Empty


# ---------------------------------------------------------------------------
# VList.locate — index
# ---------------------------------------------------------------------------

def test_vlist_locate_index():
    """VList.locate() supports 1-origin index access."""
    from stn_core.locator import _finalize_doc
    lst = VList(items=[VNumber(10), VNumber(20), VNumber(30)])
    d = doc("")
    _finalize_doc(d)  # ensure doc is ready
    # Manually attach to test locate without full eval pipeline
    lst._parent = d
    lst._document = d
    assert lst.get_first(1) == VNumber(10)
    assert lst.get_first(2) == VNumber(20)
    assert lst.get_first(3) == VNumber(30)
    assert lst.get_first(4) is Empty


# ---------------------------------------------------------------------------
# Document.locate — named key / index
# ---------------------------------------------------------------------------

def test_doc_locate_named_key():
    d = doc(":title [Hello]")
    results = d.get("title")
    assert results == [VText("Hello")]


def test_doc_locate_index():
    d = doc("1 ; 2 ; 3")
    assert d.get_first(1) == VNumber(1)
    assert d.get_first(2) == VNumber(2)
    assert d.get_first("3") == VNumber(3)


def test_doc_locate_missing_key():
    d = doc(":foo 1")
    assert d.get("bar") == []
    assert d.get_first("bar") is Empty


# ---------------------------------------------------------------------------
# Document.locate — symbol / local / typedef
# ---------------------------------------------------------------------------

def test_doc_locate_symbol():
    d = doc("@#R001 (:x 10)")
    results = d.get("#R001")
    assert len(results) == 1
    assert isinstance(results[0], VEntity)


def test_doc_locate_local():
    d = doc("@@joe (:name [Joe])")
    result = d.get_first("@joe")
    assert isinstance(result, VEntity)
    assert result.fields["name"] == VText("Joe")


def test_doc_locate_typedef():
    d = doc("@%Person (:name :age %)")
    result = d.get_first("%Person")
    from stn_core.typedef import TypeDef
    assert isinstance(result, TypeDef)
    assert result.name == "Person"


def test_doc_locate_symbol_missing():
    d = doc("@@x 1")
    assert d.get("#NOPE") == []


def test_doc_locate_local_missing():
    d = doc("@@x 1")
    assert d.get("@nope") == []


# ---------------------------------------------------------------------------
# locate — multiple accessors "(a b)"
# ---------------------------------------------------------------------------

def test_entity_locate_multi_fields():
    d = doc("@@x (:name [Joe] :age 36 :city [Tokyo])")
    e = d.locals_["x"]
    results = e.get("(name age)")
    assert results == [VText("Joe"), VNumber(36)]


def test_entity_locate_multi_indices():
    d = doc("@@x (:a 10 :b 20 :c 30)")
    e = d.locals_["x"]
    results = e.get("(1 3)")
    assert results == [VNumber(10), VNumber(30)]


def test_entity_locate_multi_partial_missing():
    """Missing fields in multi-access are silently skipped."""
    d = doc("@@x (:name [Joe])")
    e = d.locals_["x"]
    results = e.get("(name nope)")
    assert results == [VText("Joe")]


def test_entity_locate_multi_yields_paths():
    d = doc("@@x (:a 1 :b 2)")
    e = d.locals_["x"]
    pairs = list(e.locate("(a b)"))
    assert pairs == [(VNumber(1), "a"), (VNumber(2), "b")]


# ---------------------------------------------------------------------------
# locate — query "?(:key val)"
# ---------------------------------------------------------------------------

def test_entity_locate_query_single_match():
    src = """
@%P (:name :score %)
@@members (
  :alice %P(:name [Alice] :score 90)
  :bob   %P(:name [Bob]   :score 70)
)
"""
    d = doc(src)
    members = d.locals_["members"]
    result = members.get_first("?(:score 70)")
    assert isinstance(result, VEntity)
    assert result.fields["name"] == VText("Bob")


def test_entity_locate_query_multiple_matches():
    src = """
@%P (:name :score %)
@@members (
  :alice %P(:name [Alice] :score 90)
  :bob   %P(:name [Bob]   :score 90)
  :carol %P(:name [Carol] :score 70)
)
"""
    d = doc(src)
    members = d.locals_["members"]
    results = members.get("?(:score 90)")
    assert len(results) == 2
    names = {r.fields["name"].value for r in results}
    assert names == {"Alice", "Bob"}


def test_entity_locate_query_no_match():
    src = "@@x (:a (:v 1) :b (:v 2))"
    d = doc(src)
    e = d.locals_["x"]
    assert e.get_first("?(:v 99)") is Empty


def test_entity_locate_query_path_string():
    src = "@@x (:a (:n 1) :b (:n 2))"
    d = doc(src)
    e = d.locals_["x"]
    pairs = list(e.locate("?(:n 1)"))
    assert len(pairs) == 1
    val, path = pairs[0]
    assert path == "?(:n 1)"


# ---------------------------------------------------------------------------
# locate — symbol-id "#sym" in collection
# ---------------------------------------------------------------------------

def test_entity_locate_symbol_id():
    src = """
@%Item (:name)
@#item1 %Item(:name [First])
@#item2 %Item(:name [Second])
"""
    d = doc(src)
    r1 = d.get_first("#item1")
    assert isinstance(r1, VEntity)
    assert r1.fields["name"] == VText("First")


# ---------------------------------------------------------------------------
# locate — wildcard "*"
# ---------------------------------------------------------------------------

def test_entity_wildcard_all_fields():
    d = doc("@@x (:a 1 :b 2 :c 3)")
    e = d.locals_["x"]
    pairs = list(e.locate("*"))
    assert pairs == [
        (VNumber(1), "a"),
        (VNumber(2), "b"),
        (VNumber(3), "c"),
    ]


def test_entity_wildcard_get():
    d = doc("@@x (:a 1 :b 2 :c 3)")
    e = d.locals_["x"]
    assert e.get("*") == [VNumber(1), VNumber(2), VNumber(3)]


def test_vlist_wildcard():
    """VList.locate('*') yields items with 1-origin index as path."""
    from stn_core.values import VList, VNumber
    lst = VList(items=[VNumber(10), VNumber(20), VNumber(30)])
    pairs = list(lst.locate("*"))
    assert pairs == [
        (VNumber(10), "1"),
        (VNumber(20), "2"),
        (VNumber(30), "3"),
    ]


def test_entity_wildcard_positional():
    """Positional fields (_0, _1, ...) are also included in wildcard."""
    d = doc("@@x (apple orange)")
    e = d.locals_["x"]
    values = e.get("*")
    from stn_core.values import VText
    assert VText("apple") in values
    assert VText("orange") in values


def test_doc_wildcard_hierarchical():
    """doc.get('members.*') yields all children of the 'members' entry."""
    src = """
@%P (:name :age %)
:members (
  :alice %P(:name [Alice] :age 30)
  :bob   %P(:name [Bob]   :age 25)
)
"""
    d = doc(src)
    results = d.get("members.*")
    assert len(results) == 2
    names = {r.fields["name"].value for r in results}
    assert names == {"Alice", "Bob"}


def test_doc_wildcard_deep_chain():
    """doc.get('members.*.name') extracts 'name' from every member."""
    src = """
@%P (:name :age %)
:members (
  :alice %P(:name [Alice] :age 30)
  :bob   %P(:name [Bob]   :age 25)
)
"""
    d = doc(src)
    names = d.get("members.*.name")
    assert sorted(v.value for v in names) == ["Alice", "Bob"]


def test_doc_wildcard_path_strings():
    """locate() yields expanded path strings like 'members.alice'."""
    src = ":members (:x 1 :y 2)"
    d = doc(src)
    pairs = list(d.locate("members.*"))
    assert sorted(p for _, p in pairs) == ["members.x", "members.y"]


# ---------------------------------------------------------------------------
# locate — Document hierarchical paths
# ---------------------------------------------------------------------------

def test_doc_locate_hierarchical_index():
    """doc.get_first('members.1') → first item of top-level 'members'."""
    src = """
@%P (:name :age %)
:members (
  %P(:name [Alice] :age 30)
  %P(:name [Bob]   :age 25)
)
"""
    d = doc(src)
    result = d.get_first("members.1")
    assert isinstance(result, VEntity)
    assert result.fields["name"] == VText("Alice")


def test_doc_locate_hierarchical_named():
    """`doc.get_first('members.alice')` navigates into a named sub-field."""
    src = """
@%P (:name :score %)
:roster (
  :alice %P(:name [Alice] :score 90)
  :bob   %P(:name [Bob]   :score 70)
)
"""
    d = doc(src)
    result = d.get_first("roster.alice")
    assert isinstance(result, VEntity)
    assert result.fields["score"] == VNumber(90)


def test_doc_locate_hierarchical_deep():
    """`doc.get_first('config.db.host')` chains multiple levels."""
    src = ":config (:db (:host [localhost] :port 5432))"
    d = doc(src)
    assert d.get_first("config.db.host") == VText("localhost")
    assert d.get_first("config.db.port") == VNumber(5432)


def test_doc_locate_hierarchical_query():
    """`doc.get('members?(:age 30)')` filters top-level 'members'."""
    src = """
@%P (:name :age %)
:members (
  %P(:name [Alice] :age 30)
  %P(:name [Bob]   :age 25)
  %P(:name [Carol] :age 30)
)
"""
    d = doc(src)
    results = d.get("members?(:age 30)")
    assert len(results) == 2
    names = {r.fields["name"].value for r in results}
    assert names == {"Alice", "Carol"}


def test_doc_locate_hierarchical_missing_base():
    """Missing base key returns no results (no error)."""
    d = doc(":x 1")
    assert d.get("nope.field") == []
    assert d.get_first("nope.field") is Empty


def test_doc_locate_hierarchical_path_string():
    """locate() yields correct path strings for hierarchical access."""
    src = ":data (:a 1 :b 2)"
    d = doc(src)
    pairs = list(d.locate("data.a"))
    assert pairs == [(VNumber(1), "data.a")]


def test_doc_locate_hierarchical_query_path_string():
    """locate() yields correct path strings for query-style hierarchical access."""
    src = ":items (:x (:v 1) :y (:v 2))"
    d = doc(src)
    pairs = list(d.locate("items?(:v 1)"))
    assert len(pairs) == 1
    val, path = pairs[0]
    assert path == "items?(:v 1)"
