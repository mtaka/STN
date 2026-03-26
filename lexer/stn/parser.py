"""STN parser — builds an AST from a token stream."""

from .errors import STNSyntaxError
from .nodes import Node
from .tokenizer import Token, TokenType


class _Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.pos = 0

    # ── public entry ─────────────────────────────────────────────────────────

    def parse(self) -> Node:
        root = Node()
        root.word_head = True   # stream start is a word boundary
        self._parse_body(root)
        if self.pos < len(self.tokens):
            t = self.tokens[self.pos]
            raise STNSyntaxError("Unexpected ')'", t.line, t.col)
        root.word_tail = True   # stream end is a word boundary
        return root

    # ── helpers ───────────────────────────────────────────────────────────────

    def _is_space_or_end(self, pos: int) -> bool:
        """True if pos is past the end, or the token at pos is RPAREN, or it
        was preceded by whitespace in the source (meaning the preceding item
        has a word boundary on its right side)."""
        if pos >= len(self.tokens):
            return True
        t = self.tokens[pos]
        return t.type == TokenType.RPAREN or t.preceded_by_ws

    # ── recursive body parser ─────────────────────────────────────────────────

    def _parse_body(self, node: Node) -> None:
        """Parse tokens into node.items until RPAREN or end of stream.

        Sets word_head / word_tail on every Token and Node placed in items.

        Rules
        -----
        word_head=True  ← this item is directly after whitespace, after '(',
                          or at stream start.
        word_tail=True  ← this item is directly before whitespace, before ')',
                          or at stream end.
        """
        # Right after '(' (or stream start for root) counts as a word boundary.
        prev_was_space = True

        while self.pos < len(self.tokens):
            token = self.tokens[self.pos]

            # ── end of this node ─────────────────────────────────────────────
            if token.type == TokenType.RPAREN:
                # Ensure the last item carries word_tail=True (it's before ')')
                if node.items:
                    node.items[-1].word_tail = True
                break

            # ── child node ───────────────────────────────────────────────────
            if token.type == TokenType.LPAREN:
                open_tok = token
                self.pos += 1
                child = Node()
                child.word_head = prev_was_space
                self._parse_body(child)
                if self.pos >= len(self.tokens):
                    raise STNSyntaxError(
                        "Unclosed '('", open_tok.line, open_tok.col
                    )
                self.pos += 1  # consume RPAREN
                # word_tail of child = is there a word boundary after its ')'?
                prev_was_space = self._is_space_or_end(self.pos)
                child.word_tail = prev_was_space
                node.items.append(child)
                continue

            # ── regular token (SIGIL / ATOM / NUMBER) ────────────────────────
            token.word_head = prev_was_space
            self.pos += 1
            prev_was_space = self._is_space_or_end(self.pos)
            token.word_tail = prev_was_space
            node.items.append(token)


def parse_tokens(tokens: list[Token]) -> Node:
    """Build an AST from a list of tokens."""
    return _Parser(tokens).parse()
