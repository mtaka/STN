"""AST node definitions for STN."""


class Node:
    """AST node.

    Attributes:
        items:     Ordered list of Token and child Node objects.
        word_head: True if the opening '(' (or stream start for root) is a word
                   head — preceded by whitespace, '(', or stream start.
        word_tail: True if the closing ')' (or stream end for root) is a word
                   tail — followed by whitespace, ')', or stream end.
    """

    __slots__ = ("items", "word_head", "word_tail")

    def __init__(self) -> None:
        self.items: list = []
        self.word_head: bool = False
        self.word_tail: bool = False

    @property
    def children(self) -> "list[Node]":
        """Child Node objects in items order."""
        return [item for item in self.items if isinstance(item, Node)]

    def __repr__(self) -> str:
        return (
            f"Node(items={self.items!r}, "
            f"head={self.word_head}, tail={self.word_tail})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Node):
            return NotImplemented
        return (
            self.items == other.items
            and self.word_head == other.word_head
            and self.word_tail == other.word_tail
        )
