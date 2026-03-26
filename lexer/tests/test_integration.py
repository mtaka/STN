"""Integration tests — completion conditions from TASK_STN_Lexer.md."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from stn import parse
from stn.nodes import Node
from stn.tokenizer import TokenType


# ── Completion conditions ─────────────────────────────────────────────────────

def _item_values(node: Node) -> list[str]:
    return [item.value for item in node.items]


def test_new_sigils_are_single_tokens():
    """, = \\ { } ' \" each produce one SIGIL token."""
    from stn.tokenizer import tokenize, _SIGIL_CHARS
    for ch in [',', '=', '\\', '{', '}', "'", '"']:
        toks = tokenize(ch)
        assert len(toks) == 1
        assert toks[0].type == TokenType.SIGIL
        assert toks[0].value == ch

def test_underscore_atom():
    """__reserved__ is a single ATOM."""
    from stn.tokenizer import tokenize
    toks = tokenize('__reserved__')
    assert toks[0].type == TokenType.ATOM
    assert toks[0].value == '__reserved__'

def test_colon_kv_items():
    """(:name Joe :age 36) → items == [':', 'name', 'Joe', ':', 'age', '36']"""
    r = parse("(:name Joe :age 36)")
    node = r.ast.items[0]
    assert _item_values(node) == [":", "name", "Joe", ":", "age", "36"]

def test_semicolon_token_in_items():
    """(a b ; c d) → items contain ';' as a SIGIL Token."""
    r = parse("(a b ; c d)")
    node = r.ast.items[0]
    assert _item_values(node) == ["a", "b", ";", "c", "d"]
    semi = node.items[2]
    assert semi.type == TokenType.SIGIL
    assert semi.value == ";"

def test_nested_items_order():
    """(a (b c) d) → items order: a, Node, d."""
    r = parse("(a (b c) d)")
    node = r.ast.items[0]
    assert node.items[0].value == "a"
    assert isinstance(node.items[1], Node)
    assert _item_values(node.items[1]) == ["b", "c"]
    assert node.items[2].value == "d"

def test_literal_escape():
    """[hello \\] world] is a single ATOM (escaped ] inside)."""
    r = parse(r"([hello \] world])")
    node = r.ast.items[0]
    assert node.items[0].value == r"[hello \] world]"
    assert node.items[0].type == TokenType.ATOM

def test_backtick_literal():
    """`hello [world]` → ATOM value [hello [world]]."""
    r = parse("(`hello [world]`)")
    node = r.ast.items[0]
    assert node.items[0].value == "[hello [world]]"

def test_block_literal():
    """[[[[...]]]] block literal is a single ATOM."""
    text = "\n[[[[\nhello block\n]]]]\n"
    from stn.tokenizer import tokenize
    toks = tokenize(text)
    assert len(toks) == 1
    assert toks[0].type == TokenType.ATOM
    assert "hello block" in toks[0].value

def test_data_block_new_marker():
    text = "@@x foo\n====data====\nhello"
    r = parse(text)
    assert r.data == {"_ALL": "hello"}

def test_data_block_sections():
    text = "foo\n====data====\n---- @sec1\nhello\n---- @sec2\nworld"
    r = parse(text)
    assert r.data["sec1"] == "hello"
    assert r.data["sec2"] == "world"


# ── word_head / word_tail key scenarios ───────────────────────────────────────

def test_colon_sigil_word_head():
    r = parse("(:name Joe)")
    node = r.ast.items[0]
    colon = node.items[0]
    assert colon.type == TokenType.SIGIL
    assert colon.value == ":"
    assert colon.word_head is True

def test_glue_detection():
    """%Person: % is head, Person is front-glued."""
    r = parse("(%Person)")
    node = r.ast.items[0]
    pct  = node.items[0]
    name = node.items[1]
    assert pct.word_head is True
    assert name.word_head is False

def test_double_at_glue():
    """@@joe: @@ front-glued, joe front-glued."""
    r = parse("(@@joe)")
    node = r.ast.items[0]
    at1, at2, joe = node.items
    assert at1.word_head is True
    assert at2.word_head is False
    assert joe.word_head is False

def test_setter_chain_glue():
    """)!id( — everything glued."""
    r = parse("(%Person(:name Joe)!sex(M))")
    outer = r.ast.items[0]
    # outer.items: %, Person, Node(:name Joe), !, sex, Node(M)
    bang = outer.items[3]
    sex  = outer.items[4]
    m_node = outer.items[5]
    assert bang.word_head is False
    assert sex.word_head is False
    assert m_node.word_head is False

def test_word_tail_at_stream_end():
    r = parse("a b c")
    last = r.ast.items[-1]
    assert last.word_tail is True
