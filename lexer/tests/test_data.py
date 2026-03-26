"""Tests for stn.data (data block parser)."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from stn import parse
from stn.data import parse_data_block


# ── parse_data_block ──────────────────────────────────────────────────────────

def test_no_sections_returns_all():
    result = parse_data_block("hello world")
    assert result == {"_ALL": "hello world"}

def test_empty_returns_empty():
    result = parse_data_block("")
    assert result == {}

def test_single_section():
    text = "---- @sec1\nhello"
    result = parse_data_block(text)
    assert result["sec1"] == "hello"

def test_multiple_sections():
    text = "---- @sec1\nhello\n---- @sec2\nworld"
    result = parse_data_block(text)
    assert result["sec1"] == "hello"
    assert result["sec2"] == "world"

def test_section_with_multiple_dashes():
    text = "-------- @section\ncontent"
    result = parse_data_block(text)
    assert result["section"] == "content"

def test_section_with_space_after_dashes():
    text = "----   @sec\ncontent"
    result = parse_data_block(text)
    assert result["sec"] == "content"

def test_prev_content_before_first_section():
    text = "preamble\n---- @sec\ncontent"
    result = parse_data_block(text)
    assert result["_PREV"] == "preamble"
    assert result["sec"] == "content"

def test_empty_prev_is_omitted():
    text = "---- @sec\ncontent"
    result = parse_data_block(text)
    assert "_PREV" not in result
    assert result["sec"] == "content"

def test_old_double_at_not_separator():
    """@@sec is the old format; it should NOT be recognized as a separator."""
    text = "----@@sec\ncontent"
    result = parse_data_block(text)
    assert "_ALL" in result   # no section found → falls through to _ALL


# ── Integration: data block marker ───────────────────────────────────────────

def test_data_block_new_marker_lowercase():
    text = "@@x foo\n====data====\nhello"
    r = parse(text)
    assert r.data == {"_ALL": "hello"}

def test_data_block_marker_uppercase():
    text = "foo\n====DATA====\nhello"
    r = parse(text)
    assert r.data == {"_ALL": "hello"}

def test_data_block_marker_mixed_case():
    text = "foo\n====Data====\nhello"
    r = parse(text)
    assert r.data == {"_ALL": "hello"}

def test_data_block_marker_more_equals():
    text = "foo\n========data========\nhello"
    r = parse(text)
    assert r.data == {"_ALL": "hello"}

def test_data_block_sections_via_parse():
    text = "foo\n====data====\n---- @sec1\nhello\n---- @sec2\nworld"
    r = parse(text)
    assert r.data["sec1"] == "hello"
    assert r.data["sec2"] == "world"

def test_no_data_block():
    r = parse("(a b c)")
    assert r.data == {}

def test_old_data_marker_not_recognized():
    """====DATA==== (exact old format) still matches (case-insensitive)."""
    text = "foo\n====DATA====\nhello"
    r = parse(text)
    assert r.data == {"_ALL": "hello"}
