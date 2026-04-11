"""STN Core — structural evaluation engine for STN AST."""

from .document import Document
from .environment import Environment
from .evaluator import evaluate
from .values import (
    Empty,
    Value,
    VBool,
    VDate,
    VEntity,
    VEnum,
    VList,
    VNumber,
    VText,
    _Empty,
)
from .typedef import TypeDef, MemberDef
from .sobject import SObject, SEntry
from .errors import STNCoreError
from .repl import STNRepl
from .locator import locate_value, locate_document

__all__ = [
    "evaluate",
    "Document",
    "Environment",
    "Empty",
    "Value",
    "VBool",
    "VDate",
    "VEntity",
    "VEnum",
    "VList",
    "VNumber",
    "VText",
    "TypeDef",
    "MemberDef",
    "SObject",
    "SEntry",
    "STNCoreError",
    "STNRepl",
    "locate_value",
    "locate_document",
]
