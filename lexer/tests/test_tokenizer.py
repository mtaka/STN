"""Tests for stn.tokenizer."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from stn.tokenizer import tokenize, Token, TokenType, _SIGIL_CHARS


# ── SIGIL set ──────────────────────────────────────────────────────────────

def test_sigil_chars_include_new():
    """New chars: , = \\ { } ' \" should be SIGILs."""
    for ch in [',', '=', '\\', '{', '}', "'", '"']:
        assert ch in _SIGIL_CHARS, f"{ch!r} should be in _SIGIL_CHARS"

def test_sigil_chars_exclude_underscore():
    assert '_' not in _SIGIL_CHARS

def test_sigil_tokens():
    toks = tokenize(',=\\{}\'"')
    assert all(t.type == TokenType.SIGIL for t in toks)
    assert [t.value for t in toks] == [',', '=', '\\', '{', '}', "'", '"']


# ── ATOM (underscore in identifiers) ────────────────────────────────────────

def test_underscore_in_atom():
    """_ is no longer a SIGIL; __reserved__ should be a single ATOM."""
    toks = tokenize('__reserved__')
    assert len(toks) == 1
    assert toks[0].type == TokenType.ATOM
    assert toks[0].value == '__reserved__'

def test_atom_with_underscore():
    toks = tokenize('hello_world')
    assert toks[0].value == 'hello_world'


# ── Regular literal ──────────────────────────────────────────────────────────

def test_regular_literal_basic():
    toks = tokenize('[hello world]')
    assert toks[0].type == TokenType.ATOM
    assert toks[0].value == '[hello world]'

def test_regular_literal_with_escape():
    toks = tokenize(r'[hello \] world]')
    assert toks[0].value == r'[hello \] world]'

def test_regular_literal_no_nesting():
    """[a [b] c] stops at first ] — the outer ] is left over, causing second token."""
    toks = tokenize('[a [b] c]')
    # First token is [a [b] (stops at first ]), remaining " c]" produces ATOM + SIGIL
    assert toks[0].type == TokenType.ATOM
    assert toks[0].value == '[a [b]'

def test_regular_literal_unclosed():
    with pytest.raises(Exception):
        tokenize('[hello')


# ── Backtick literal ─────────────────────────────────────────────────────────

def test_backtick_literal_basic():
    toks = tokenize('`hello world`')
    assert toks[0].type == TokenType.ATOM
    assert toks[0].value == '[hello world]'

def test_backtick_literal_with_brackets():
    toks = tokenize('`hello [world]`')
    assert toks[0].value == '[hello [world]]'

def test_backtick_literal_escape():
    toks = tokenize(r'`hello \` world`')
    assert toks[0].value == '[hello ` world]'

def test_backtick_literal_unclosed():
    with pytest.raises(Exception):
        tokenize('`hello')


# ── Block literal [[[[...]]]] ─────────────────────────────────────────────────

def test_block_literal_basic():
    text = "\n[[[[\nhello world\n]]]]\n"
    toks = tokenize(text)
    assert len(toks) == 1
    assert toks[0].type == TokenType.ATOM
    assert '[[[[' in toks[0].value
    assert ']]]]' in toks[0].value
    assert 'hello world' in toks[0].value

def test_block_literal_unclosed():
    with pytest.raises(Exception):
        tokenize("\n[[[[\nhello\n")

def test_block_literal_requires_preceding_newline():
    """[[[ without preceding newline → NOT a block literal → regular literal."""
    toks = tokenize('[[[[hello]]]]')
    # Without preceding \n, treated as regular [[ literal chain
    assert toks[0].type == TokenType.ATOM


# ── Numbers ───────────────────────────────────────────────────────────────────

def test_integer():
    toks = tokenize('42')
    assert toks[0].type == TokenType.NUMBER
    assert toks[0].value == '42'

def test_float():
    toks = tokenize('3.14')
    assert toks[0].type == TokenType.NUMBER
    assert toks[0].value == '3.14'

def test_negative_number():
    toks = tokenize('-5')
    assert toks[0].type == TokenType.NUMBER
    assert toks[0].value == '-5'


# ── preceded_by_ws ────────────────────────────────────────────────────────────

def test_preceded_by_ws_stream_start():
    toks = tokenize('hello')
    assert toks[0].preceded_by_ws is True

def test_preceded_by_ws_after_space():
    toks = tokenize('a b')
    assert toks[0].preceded_by_ws is True
    assert toks[1].preceded_by_ws is True

def test_preceded_by_ws_no_space():
    toks = tokenize('%Person')
    assert toks[0].preceded_by_ws is True   # stream start
    assert toks[1].preceded_by_ws is False  # immediately after %

def test_comment_acts_as_whitespace():
    toks = tokenize('a // comment\nb')
    assert toks[1].preceded_by_ws is True


# ── Structure tokens ──────────────────────────────────────────────────────────

def test_lparen_rparen():
    toks = tokenize('()')
    assert toks[0].type == TokenType.LPAREN
    assert toks[1].type == TokenType.RPAREN

def test_semicolon_is_sigil():
    """In new spec, ; is a SIGIL, not SEMICOLON."""
    toks = tokenize(';')
    assert toks[0].type == TokenType.SIGIL
    assert toks[0].value == ';'
