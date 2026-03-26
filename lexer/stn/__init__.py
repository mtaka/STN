"""STN lexer — parse STN text into an AST.

Usage::

    from stn import parse

    result = parse("(a b ; c d)")
    # result.ast  — root Node
    # result.ast.items[0]  — Node for (a b ; c d)
    # result.data — {}
"""

import re
from typing import NamedTuple

from .data import parse_data_block
from .errors import STNError, STNSyntaxError
from .nodes import Node
from .parser import parse_tokens
from .tokenizer import Token, TokenType, tokenize

# New spec: ====data==== (case-insensitive, 4+ equals on each side)
_DATA_MARKER_RE = re.compile(r"^={4,}data={4,}$", re.MULTILINE | re.IGNORECASE)


class ParseResult(NamedTuple):
    """Result of :func:`parse` — AST plus optional data block."""

    ast: Node
    data: dict[str, str]


__all__ = [
    "parse",
    "ParseResult",
    "Node",
    "Token",
    "TokenType",
    "STNError",
    "STNSyntaxError",
]


def parse(text: str) -> ParseResult:
    """Parse STN text and return a :class:`ParseResult`.

    This is the primary public API.  The returned result contains an
    ``ast`` (the implicit root :class:`Node`) and a ``data`` dict
    populated from an optional data-block (introduced by a line matching
    ``====data====``).
    """
    text = text.replace("\r\n", "\n")

    m = _DATA_MARKER_RE.search(text)
    if m:
        stn_text = text[: m.start()]
        data_text = text[m.end() :]
        # strip leading newline after marker
        if data_text.startswith("\n"):
            data_text = data_text[1:]
        data = parse_data_block(data_text)
    else:
        stn_text = text
        data = {}

    tokens = tokenize(stn_text)
    ast = parse_tokens(tokens)
    return ParseResult(ast, data)
