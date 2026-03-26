"""STN tokenizer — converts raw text into a flat token stream."""

from enum import Enum, auto

from .errors import STNSyntaxError


class TokenType(Enum):
    LPAREN = auto()
    RPAREN = auto()
    ATOM = auto()
    SIGIL = auto()
    NUMBER = auto()


class Token:
    """A single lexical token.

    ``preceded_by_ws`` is an internal field set by the tokenizer to record
    whether this token was immediately preceded by whitespace (space, tab,
    newline) or is at the very start of the stream.  The parser uses it to
    compute ``word_head`` / ``word_tail``.

    ``word_head`` / ``word_tail`` are set by the parser once structural
    context (surrounding parentheses) is known.
    """

    __slots__ = ("type", "value", "line", "col", "preceded_by_ws", "word_head", "word_tail")

    def __init__(
        self,
        type: TokenType,
        value: str,
        line: int = 1,
        col: int = 1,
        preceded_by_ws: bool = False,
    ) -> None:
        self.type = type
        self.value = value
        self.line = line
        self.col = col
        self.preceded_by_ws: bool = preceded_by_ws
        self.word_head: bool = False   # set by parser
        self.word_tail: bool = False   # set by parser

    def __repr__(self) -> str:
        return (
            f"Token({self.type.name}, {self.value!r}, "
            f"head={self.word_head}, tail={self.word_tail})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Token):
            return NotImplemented
        return (
            self.type == other.type
            and self.value == other.value
            and self.word_head == other.word_head
            and self.word_tail == other.word_tail
        )


# New SIGIL character set per spec.
# ; , : . = + - * / % ! ? @ # $ ^ & ~ ` | \ < > { } ' "
_SIGIL_CHARS = frozenset([
    ';', ',', ':', '.', '=', '+', '-', '*', '/', '%',
    '!', '?', '@', '#', '$', '^', '&', '~', '`', '|',
    '\\', '<', '>', '{', '}', "'", '"',
])

# Characters that terminate an unquoted atom.
# '(' and ')' are structural; '[' starts a literal; SIGIL chars each form their own token.
_ATOM_BREAK = frozenset(" \t\n\r()[") | _SIGIL_CHARS


def tokenize(text: str) -> list[Token]:
    """Tokenize STN source text into a list of tokens.

    Handles:
    - Comments (//)
    - Structure tokens: ( )
    - Block literal  \\n[[[[\\n ... \\n]]]]\\n  (4-bracket, newline-delimited)
    - Backtick literal  `...`  → emitted as ATOM with value [content]
    - Regular literal  [...]   with \\] escape support (no bracket-depth nesting)
    - Numbers (integer and decimal, negative when - precedes digits)
    - SIGIL characters (1 char each)
    - Plain atoms
    """
    tokens: list[Token] = []
    i = 0
    length = len(text)
    line = 1
    col = 1
    preceded_by_ws = True   # stream start counts as whitespace

    while i < length:
        ch = text[i]

        # ── whitespace ────────────────────────────────────────────────────────
        if ch in " \t\r":
            i += 1
            col += 1
            preceded_by_ws = True
            continue

        if ch == "\n":
            i += 1
            line += 1
            col = 1
            preceded_by_ws = True
            continue

        # ── comment ───────────────────────────────────────────────────────────
        if ch == "/" and i + 1 < length and text[i + 1] == "/":
            while i < length and text[i] != "\n":
                i += 1
            preceded_by_ws = True
            continue

        # Capture preceding-whitespace flag for the upcoming token, then reset.
        _pws = preceded_by_ws
        preceded_by_ws = False

        # ── structure tokens ──────────────────────────────────────────────────
        if ch == "(":
            tokens.append(Token(TokenType.LPAREN, "(", line, col, _pws))
            i += 1
            col += 1
            continue

        if ch == ")":
            tokens.append(Token(TokenType.RPAREN, ")", line, col, _pws))
            i += 1
            col += 1
            continue

        # ── block literal  \n[[[[\n ... \n]]]]\n ─────────────────────────────
        # Requires: preceded by newline (or stream start) AND followed by newline.
        if (
            text[i : i + 4] == "[[[["
            and (i == 0 or text[i - 1] == "\n")
            and i + 4 < length
            and text[i + 4] == "\n"
        ):
            start_line, start_col = line, col
            # Find closing \n]]]]
            j = i + 5  # start of content (skip [[[[\n)
            end = text.find("\n]]]]", j)
            if end == -1:
                raise STNSyntaxError("Unclosed block literal '[[[[...]]]]'", line, col)
            # Value includes the [[[[ and ]]]] delimiters (same convention as [...])
            end_pos = end + 5  # points past \n]]]]
            if end_pos < length and text[end_pos] == "\n":
                end_pos += 1   # consume optional trailing newline
            raw = text[i:end_pos]
            value = text[i : end + 5]   # [[[[\n...\n]]]]
            for c in raw:
                if c == "\n":
                    line += 1
                    col = 1
                else:
                    col += 1
            tokens.append(Token(TokenType.ATOM, value, start_line, start_col, _pws))
            i = end_pos
            continue

        # ── backtick literal  `...` ──────────────────────────────────────────
        if ch == "`":
            start_line, start_col = line, col
            j = i + 1
            content: list[str] = []
            while j < length:
                if text[j] == "\\" and j + 1 < length and text[j + 1] == "`":
                    content.append("`")
                    j += 2
                elif text[j] == "`":
                    break
                else:
                    content.append(text[j])
                    j += 1
            if j >= length:
                raise STNSyntaxError("Unclosed backtick literal", line, col)
            # Advance line/col past the entire backtick span (opening + content + closing)
            for c in text[i : j + 1]:
                if c == "\n":
                    line += 1
                    col = 1
                else:
                    col += 1
            # Emit as ATOM with value wrapped in [...]
            value = "[" + "".join(content) + "]"
            tokens.append(Token(TokenType.ATOM, value, start_line, start_col, _pws))
            i = j + 1
            continue

        # ── regular literal  [...] ────────────────────────────────────────────
        # No bracket-depth counting; \] is the only escape inside.
        if ch == "[":
            start_line, start_col = line, col
            j = i + 1
            while j < length:
                if text[j] == "\\" and j + 1 < length and text[j + 1] == "]":
                    j += 2   # skip escaped ]
                elif text[j] == "]":
                    break
                else:
                    j += 1
            if j >= length:
                raise STNSyntaxError("Unclosed literal '['", line, col)
            value = text[i : j + 1]   # includes [ and ]
            for c in value:
                if c == "\n":
                    line += 1
                    col = 1
                else:
                    col += 1
            tokens.append(Token(TokenType.ATOM, value, start_line, start_col, _pws))
            i = j + 1
            continue

        # ── number ────────────────────────────────────────────────────────────
        if ch.isdigit() or (
            ch == "-" and i + 1 < length and text[i + 1].isdigit()
        ):
            start_line, start_col = line, col
            j = i
            if text[j] == "-":
                j += 1
            while j < length and text[j].isdigit():
                j += 1
            if (
                j < length
                and text[j] == "."
                and j + 1 < length
                and text[j + 1].isdigit()
            ):
                j += 1
                while j < length and text[j].isdigit():
                    j += 1
            value = text[i:j]
            col += j - i
            tokens.append(Token(TokenType.NUMBER, value, start_line, start_col, _pws))
            i = j
            continue

        # ── sigil (1 char each) ───────────────────────────────────────────────
        if ch in _SIGIL_CHARS:
            tokens.append(Token(TokenType.SIGIL, ch, line, col, _pws))
            i += 1
            col += 1
            continue

        # ── plain atom ────────────────────────────────────────────────────────
        start_line, start_col = line, col
        j = i
        while j < length and text[j] not in _ATOM_BREAK:
            j += 1
        if j == i:
            raise STNSyntaxError(f"Unexpected character {ch!r}", line, col)
        value = text[i:j]
        col += j - i
        tokens.append(Token(TokenType.ATOM, value, start_line, start_col, _pws))
        i = j

    return tokens
