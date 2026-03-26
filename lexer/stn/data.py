"""Data block parser for STN."""

import re

# New spec: dashes (1+), optional space, single @, then identifier
_SEPARATOR_RE = re.compile(r"^-+\s*@([a-zA-Z_][a-zA-Z0-9_]*)$")


def parse_data_block(text: str) -> dict[str, str]:
    """Parse a data block into a dict of named sections.

    *text* is the content **after** the data-block marker line.

    Returns a mapping of section identifiers to their content strings.
    If no separator lines are found the entire text is stored under ``_ALL``.
    Content before the first separator is stored under ``_PREV``.
    """
    lines = text.split("\n")
    sections: list[tuple[str, list[str]]] = []
    current_key: str | None = None
    current_lines: list[str] = []
    has_separators = False

    for line in lines:
        m = _SEPARATOR_RE.match(line)
        if m:
            has_separators = True
            # flush previous section
            if current_key is not None or current_lines:
                key = current_key if current_key is not None else "_PREV"
                sections.append((key, current_lines))
            current_key = m.group(1)
            current_lines = []
        else:
            current_lines.append(line)

    # flush last section
    if current_key is not None or current_lines:
        key = current_key if current_key is not None else "_PREV"
        sections.append((key, current_lines))

    # no separators at all → _ALL
    if not has_separators:
        content = text.rstrip("\n")
        if not content:
            return {}
        return {"_ALL": content}

    result: dict[str, str] = {}
    for key, content_lines in sections:
        value = "\n".join(content_lines).rstrip("\n")
        if key == "_PREV" and not value:
            continue
        result[key] = value
    return result
