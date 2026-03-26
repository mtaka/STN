# STN Lexer

Lexer for STN (Structured Text Notation) — tokenizes and parses STN source text
into an AST of `Node` objects ready for higher-level interpretation.

日本語 README → [README-ja.md](README-ja.md)

## Installation

```
pip install -e .
```

## Usage

```python
from stn import parse

result = parse(text)
result.ast    # root Node
result.data   # data block → dict[str, str]
```

## What the Lexer produces

### ParseResult

| Field | Type | Description |
|-------|------|-------------|
| `ast` | `Node` | Root node containing all parsed items |
| `data` | `dict[str, str]` | Named sections from the data block |

### Node

```python
class Node:
    items: list[Token | Node]  # ordered content
    word_head: bool            # True if '(' was at a word boundary (preceded by space / stream start)
    word_tail: bool            # True if ')' was at a word boundary (followed by space / stream end)

    @property
    def children(self) -> list[Node]: ...  # child Nodes only
```

### Token

```python
class Token:
    type: TokenType   # SIGIL | ATOM | NUMBER
    value: str
    line: int
    col: int
    word_head: bool   # preceded by whitespace, '(', or stream start
    word_tail: bool   # followed by whitespace, ')', or stream end
```

The `word_head` / `word_tail` flags let a higher layer (e.g. STN_Core) detect
*gluing* — whether two adjacent tokens are fused (no space between them):

```
%Person  →  SIGIL(%, head=T, tail=F)  ATOM(Person, head=F, tail=T)
@@joe    →  SIGIL(@, head=T, tail=F)  SIGIL(@, head=F, tail=F)  ATOM(joe, head=F, tail=T)
:name    →  SIGIL(:, head=T, tail=F)  ATOM(name, head=F, tail=T)
```

## Example

Input:

```
@@joe (:name [Joe Smith] :age 36)
@joe.name
```

After `parse(text)`:

```
root Node
└── items:
    ├── SIGIL(@, head=T, tail=F)
    ├── SIGIL(@, head=F, tail=F)
    ├── ATOM(joe, head=F, tail=T)
    └── Node(head=T, tail=T)
        └── items:
            ├── SIGIL(:, head=T, tail=F)
            ├── ATOM(name, head=F, tail=T)
            ├── ATOM([Joe Smith], head=T, tail=T)
            ├── SIGIL(:, head=T, tail=F)
            ├── ATOM(age, head=F, tail=T)
            └── NUMBER(36, head=T, tail=T)
    ├── SIGIL(@, head=T, tail=F)
    ├── ATOM(joe, head=F, tail=F)
    ├── SIGIL(., head=F, tail=F)
    └── ATOM(name, head=F, tail=T)
```

## Syntax

### Tokens

| Token | Description |
|-------|-------------|
| `( ... )` | Node — nested structure |
| `ATOM` | Unquoted identifier (letters, digits, `_`, etc.) |
| `NUMBER` | Integer or decimal (`42`, `3.14`, `-5`) |
| `SIGIL` | Any single character from the SIGIL set (see below) |

### SIGIL characters (one token each)

```
; , : . = + - * / % ! ? @ # $ ^ & ~ ` | \ < > { } ' "
```

Note: `_` (underscore) is **not** a SIGIL — it is part of atoms (`__reserved__` is a valid ATOM).

### Literals (emitted as ATOM)

| Syntax | Description |
|--------|-------------|
| `[...]` | Regular literal — `\]` escapes a literal `]` inside |
| `` `...` `` | Backtick literal — emitted as `[content]`; `` \` `` escapes a backtick |
| `\n[[[[\n...\n]]]]\n` | Block literal — 4-bracket, newline-delimited; any `]` allowed inside |

### Comments

```
// line comment
```

### Data block

```
====data====
---- @section1
content of section 1
---- @section2
content of section 2
```

- Marker: `====data====` (case-insensitive, 4+ `=` on each side)
- Section separator: `-+\s*@name`
- Accessed via `result.data["section1"]`
- Without sections: entire content stored under `_ALL`

## Design notes

The Lexer is intentionally **interpretation-free**:

- `;` is a plain SIGIL token — chunk splitting is the caller's responsibility
- `:name` is `SIGIL(:)` + `ATOM(name)` — key detection is the caller's responsibility
- `%Type` is `SIGIL(%)` + `ATOM(Type)` — type instantiation is the caller's responsibility

Semantic interpretation (variables, types, getters, setters) belongs to a
higher layer such as **STN_Core**.

## Testing

```
python -m pytest tests/ -v
```
