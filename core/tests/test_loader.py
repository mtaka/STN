"""Tests for Document.loads() and Document.load()."""

import tempfile
import os

from stn_core import Document, Empty
from stn_core.values import VNumber, VText, VEntity


def test_loads_simple():
    doc = Document.loads("42")
    assert doc.getval(1) == VNumber(42)


def test_loads_variable():
    doc = Document.loads("@@x 10\n@x")
    assert doc.locals_["x"] == VNumber(10)
    assert doc.getval(1) == VNumber(10)


def test_loads_typedef_and_entity():
    src = """
@%Person (:name :age %)
@@joe %Person(:name [Joe] :age 30)
"""
    doc = Document.loads(src)
    assert "Person" in doc.typedefs
    assert "joe" in doc.locals_
    assert doc.locals_["joe"].fields["name"] == VText("Joe")


def test_loads_named_key():
    doc = Document.loads(":title [Hello]")
    assert doc.getval("title") == VText("Hello")


def test_loads_empty_string():
    doc = Document.loads("")
    assert doc.results == []


def test_load_from_file():
    src = ":greeting [Hello from file]"
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".stn", encoding="utf-8", delete=False
    ) as f:
        f.write(src)
        path = f.name
    try:
        doc = Document.load(path)
        assert doc.getval("greeting") == VText("Hello from file")
    finally:
        os.unlink(path)


def test_load_with_data_block():
    src = "@@x 1\n====data====\n---@image\nabc123"
    doc = Document.loads(src)
    data = doc.locals_.get("_DATA")
    assert data is not None
    assert str(data.fields["image"]) == "abc123"
