"""Tests for stn.parser (and integration with tokenizer)."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from stn import parse
from stn.nodes import Node
from stn.tokenizer import TokenType


# ── Basic structure ───────────────────────────────────────────────────────────

def test_simple():
    r = parse("(a b c)")
    node = r.ast.items[0]
    assert isinstance(node, Node)
    assert [t.value for t in node.items] == ["a", "b", "c"]

def test_nested_order():
    r = parse("(a (b c) d)")
    node = r.ast.items[0]
    assert node.items[0].value == "a"
    assert isinstance(node.items[1], Node)
    assert node.items[2].value == "d"

def test_semicolon_is_token():
    r = parse("(a b ; c d)")
    node = r.ast.items[0]
    values = [item.value for item in node.items]
    assert ";" in values
    assert values == ["a", "b", ";", "c", "d"]

def test_colon_is_sigil_not_chunk_splitter():
    """: does NOT split chunks; it appears as a SIGIL token in items."""
    r = parse("(:name Joe :age 36)")
    node = r.ast.items[0]
    values = [item.value for item in node.items]
    assert values == [":", "name", "Joe", ":", "age", "36"]

def test_percent_is_sigil():
    """%Person → SIGIL(%) + ATOM(Person) with no implicit chunk."""
    r = parse("(%Person)")
    node = r.ast.items[0]
    assert node.items[0].type == TokenType.SIGIL
    assert node.items[0].value == "%"
    assert node.items[1].type == TokenType.ATOM
    assert node.items[1].value == "Person"

def test_items_mixed_tokens_and_nodes():
    r = parse("(a (b c) d)")
    node = r.ast.items[0]
    assert len(node.items) == 3
    assert isinstance(node.items[1], Node)
    assert [t.value for t in node.items[1].items] == ["b", "c"]


# ── word_head / word_tail ─────────────────────────────────────────────────────

def test_word_head_tail_basic():
    r = parse("(a b c)")
    node = r.ast.items[0]
    a, b, c = node.items
    assert a.word_head is True    # right after (
    assert a.word_tail is True    # space before b
    assert b.word_head is True
    assert b.word_tail is True
    assert c.word_head is True
    assert c.word_tail is True    # right before )

def test_word_head_after_paren():
    r = parse("(:name Joe)")
    node = r.ast.items[0]
    colon = node.items[0]
    assert colon.type == TokenType.SIGIL
    assert colon.value == ":"
    assert colon.word_head is True   # ( directly precedes

def test_glue_detection_percent_person():
    """%Person: % is word_head, Person is front-glued (word_head=False)."""
    r = parse("(%Person)")
    node = r.ast.items[0]
    pct  = node.items[0]
    name = node.items[1]
    assert pct.word_head is True
    assert pct.word_tail is False   # Person immediately follows
    assert name.word_head is False  # glued to %
    assert name.word_tail is True   # before )

def test_glue_detection_double_at():
    """@@joe: first @ is head, second @ and joe are front-glued."""
    r = parse("(@@joe)")
    node = r.ast.items[0]
    at1, at2, joe = node.items
    assert at1.word_head is True
    assert at1.word_tail is False
    assert at2.word_head is False
    assert at2.word_tail is False
    assert joe.word_head is False
    assert joe.word_tail is True

def test_glue_node_word_head_false():
    """%Person(:name Joe) — the child node ( is NOT word_head (glued to Person)."""
    r = parse("(%Person(:name Joe))")
    outer = r.ast.items[0]
    # outer.items = [%, Person, Node(:name Joe)]
    child_node = outer.items[2]
    assert isinstance(child_node, Node)
    assert child_node.word_head is False  # no space before (

def test_glue_node_word_tail_false():
    """%Person(:name Joe)!sex — child node ) is NOT word_tail (! follows)."""
    r = parse("(%Person(:name Joe)!sex)")
    outer = r.ast.items[0]
    child_node = outer.items[2]
    assert isinstance(child_node, Node)
    assert child_node.word_tail is False  # ! immediately follows )

def test_word_tail_before_rparen():
    r = parse("(a b)")
    node = r.ast.items[0]
    assert node.items[-1].word_tail is True

def test_root_word_head_tail():
    r = parse("a b c")
    assert r.ast.word_head is True
    assert r.ast.word_tail is True

def test_nested_inner_items_word_flags():
    r = parse("(a (b c) d)")
    outer = r.ast.items[0]
    inner = outer.items[1]
    b, c = inner.items
    assert b.word_head is True   # right after inner (
    assert c.word_tail is True   # right before inner )

def test_separator_with_spaces_all_heads():
    """(a b ; c d) — ; has surrounding spaces → all items are word boundaries."""
    r = parse("(a b ; c d)")
    node = r.ast.items[0]
    for item in node.items:
        assert item.word_head is True
        assert item.word_tail is True


# ── Literals inside nodes ─────────────────────────────────────────────────────

def test_literal_basic():
    r = parse("([hello world])")
    node = r.ast.items[0]
    assert node.items[0].value == "[hello world]"
    assert node.items[0].type == TokenType.ATOM

def test_literal_with_escape():
    r = parse(r"([hello \] world])")
    node = r.ast.items[0]
    assert node.items[0].value == r"[hello \] world]"

def test_backtick_literal():
    r = parse("(`hello [world]`)")
    node = r.ast.items[0]
    assert node.items[0].value == "[hello [world]]"


# ── Error cases ───────────────────────────────────────────────────────────────

def test_unclosed_paren():
    with pytest.raises(Exception):
        parse("(a b")

def test_unexpected_rparen():
    with pytest.raises(Exception):
        parse("a b)")


# ── No-chunk-split for : and % ───────────────────────────────────────────────

def test_colon_number_no_chunk():
    """:36 is just SIGIL(:) + NUMBER(36), no chunk split."""
    r = parse("(:36)")
    node = r.ast.items[0]
    assert node.items[0].value == ":"
    assert node.items[1].value == "36"
    assert len(node.items) == 2

def test_children_property():
    """Node.children returns only child Nodes."""
    r = parse("(a (b) c (d e))")
    node = r.ast.items[0]
    children = node.children
    assert len(children) == 2
    assert all(isinstance(c, Node) for c in children)
