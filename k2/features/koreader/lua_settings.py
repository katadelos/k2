"""Read literal Lua settings and edit individual fields without evaluating Lua."""

import re
from dataclasses import dataclass

_LONG_OPEN = re.compile(r"\[(=*)\[")
_NUMBER = re.compile(
    r"(?:0[xX][0-9a-fA-F]+(?:\.[0-9a-fA-F]*)?(?:[pP][+-]?[0-9]+)?|(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)"
)
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")
_RESERVED = {
    "and",
    "break",
    "do",
    "else",
    "elseif",
    "end",
    "for",
    "function",
    "goto",
    "if",
    "in",
    "local",
    "not",
    "or",
    "repeat",
    "return",
    "then",
    "until",
    "while",
}


class SettingsSyntaxError(ValueError):
    pass


@dataclass
class Value:
    value: object
    start: int
    end: int


@dataclass
class Field:
    key: object
    value: Value
    separator: bool


@dataclass
class Table:
    fields: list

    def field(self, key):
        found = [
            item
            for item in self.fields
            if type(item.key) is type(key) and item.key == key
        ]
        if len(found) > 1:
            raise SettingsSyntaxError("A settings field occurs more than once.")
        return found[0] if found else None


class _Parser:
    def __init__(self, text):
        if len(text) > 4 * 1024 * 1024:
            raise SettingsSyntaxError("The settings file is too large to edit safely.")
        self.text, self.position, self.count = text, 0, 0
        self.token = None

    def _long_string(self, start):
        match = _LONG_OPEN.match(self.text, start)
        if not match:
            return None
        begin = start + len(match.group(0))
        delimiter = "]" + match.group(1) + "]"
        end = self.text.find(delimiter, begin)
        if end < 0:
            raise SettingsSyntaxError("A Lua string or comment is unfinished.")
        value = self.text[begin:end]
        if value.startswith("\r\n"):
            value = value[2:]
        elif value.startswith(("\n", "\r")):
            value = value[1:]
        return value, end + len(delimiter)

    def _quoted_string(self, start: int) -> tuple[str, int]:
        quote, cursor = self.text[start], start + 1
        result: list[str] = []
        while cursor < len(self.text):
            char = self.text[cursor]
            cursor += 1
            if char == quote:
                return "".join(result), cursor
            if char in "\n\r":
                raise SettingsSyntaxError(
                    "A quoted Lua string contains an unescaped newline."
                )
            if char == "\\":
                if cursor >= len(self.text):
                    break
                char, cursor = self._escaped_character(cursor)
            result.append(char)
        raise SettingsSyntaxError("A quoted Lua string is unfinished.")

    def _escaped_character(self, cursor: int) -> tuple[str, int]:
        escapes = {
            "a": "\a",
            "b": "\b",
            "f": "\f",
            "n": "\n",
            "r": "\r",
            "t": "\t",
            "v": "\v",
        }
        char = self.text[cursor]
        cursor += 1
        if char in escapes:
            return escapes[char], cursor
        if char in "\\\"'":
            return char, cursor
        if char in "\r\n":
            if char == "\r" and self.text[cursor : cursor + 1] == "\n":
                cursor += 1
            return "\n", cursor
        if char == "z":
            while cursor < len(self.text) and self.text[cursor].isspace():
                cursor += 1
            return "", cursor
        if char == "x":
            code = self.text[cursor : cursor + 2]
            if not re.fullmatch(r"[0-9A-Fa-f]{2}", code):
                raise SettingsSyntaxError(
                    "A Lua string contains an unsupported escape."
                )
            return chr(int(code, 16)), cursor + 2
        if char in "0123456789":
            code = char
            while (
                len(code) < 3
                and cursor < len(self.text)
                and self.text[cursor] in "0123456789"
            ):
                code += self.text[cursor]
                cursor += 1
            if int(code) > 255:
                raise SettingsSyntaxError(
                    "A Lua string contains an invalid byte escape."
                )
            return chr(int(code)), cursor
        raise SettingsSyntaxError("A Lua string contains an unsupported escape.")

    def peek(self):
        if self.token is not None:
            return self.token
        while self.position < len(self.text):
            if self.text[self.position].isspace() or (
                self.position == 0 and self.text[self.position] == "\ufeff"
            ):
                self.position += 1
                continue
            if self.text.startswith("--", self.position):
                comment = self._long_string(self.position + 2)
                if comment:
                    self.position = comment[1]
                else:
                    newline = self.text.find("\n", self.position)
                    self.position = len(self.text) if newline < 0 else newline + 1
                continue
            break
        start = self.position
        self.count += 1
        if self.count > 200000:
            raise SettingsSyntaxError(
                "The settings file is too complex to edit safely."
            )
        if start == len(self.text):
            self.token = ("eof", None, start, start)
            return self.token
        char = self.text[start]
        value: str | float
        if char in "\"'":
            value, end = self._quoted_string(start)
            kind = "string"
        elif char == "[" and self._long_string(start) is not None:
            value, end = self._long_string(start)
            kind = "string"
        elif char in "{}[]=,;-":
            kind, value, end = char, char, start + 1
        else:
            number = _NUMBER.match(self.text, start)
            identifier = _IDENTIFIER.match(self.text, start)
            if number:
                literal = number.group(0)
                try:
                    value = (
                        float.fromhex(literal)
                        if literal.lower().startswith("0x")
                        else float(literal)
                    )
                except (ValueError, OverflowError) as error:
                    raise SettingsSyntaxError(
                        "A settings number cannot be parsed safely."
                    ) from error
                kind, end = "number", start + len(literal)
            elif identifier:
                kind, value, end = (
                    "identifier",
                    identifier.group(0),
                    start + len(identifier.group(0)),
                )
            else:
                raise SettingsSyntaxError(
                    "The settings contain executable or unsupported Lua syntax."
                )
        self.token = kind, value, start, end
        return self.token

    def take(self, kind=None):
        token = self.peek()
        if kind is not None and token[0] != kind:
            raise SettingsSyntaxError(
                "The settings contain executable or unsupported Lua syntax."
            )
        self.position, self.token = token[3], None
        return token

    def value(self, depth=0):
        if depth > 64:
            raise SettingsSyntaxError("The settings contain too many nested tables.")
        kind, data, start, end = self.peek()
        if kind == "{":
            self.take()
            fields, array_index = [], 1
            while self.peek()[0] != "}":
                key = None
                if self.peek()[0] == "[":
                    self.take()
                    index = self.value(depth + 1)
                    if not isinstance(index.value, (str, float, bool)):
                        raise SettingsSyntaxError(
                            "A settings table has an unsupported key."
                        )
                    key = index.value
                    self.take("]")
                    self.take("=")
                    item = self.value(depth + 1)
                elif self.peek()[0] == "identifier" and self.peek()[1] not in {
                    "true",
                    "false",
                    "nil",
                }:
                    key = self.take()[1]
                    if key in _RESERVED:
                        raise SettingsSyntaxError(
                            "A settings key uses a reserved Lua keyword."
                        )
                    self.take("=")
                    item = self.value(depth + 1)
                else:
                    key, array_index = float(array_index), array_index + 1
                    item = self.value(depth + 1)
                separator = self.peek()[0] in {",", ";"}
                if separator:
                    self.take()
                elif self.peek()[0] != "}":
                    raise SettingsSyntaxError(
                        "The settings contain a nonliteral expression."
                    )
                fields.append(Field(key, item, separator))
            end = self.take("}")[3]
            return Value(Table(fields), start, end)
        if kind in {"string", "number"}:
            self.take()
            return Value(data, start, end)
        if kind == "-":
            self.take()
            number = self.take("number")
            return Value(-number[1], start, number[3])
        if kind == "identifier" and data in {"true", "false", "nil"}:
            self.take()
            return Value({"true": True, "false": False, "nil": None}[data], start, end)
        raise SettingsSyntaxError(
            "The settings contain executable or nonliteral Lua values."
        )

    def document(self):
        if self.take("identifier")[1] != "return":
            raise SettingsSyntaxError("The settings are not a literal returned table.")
        result = self.value()
        if not isinstance(result.value, Table):
            raise SettingsSyntaxError("The settings are not a literal returned table.")
        if self.peek()[0] == ";":
            self.take()
        self.take("eof")
        return result


def parse_settings(text):
    return _Parser(text).document()


def _truthy(value):
    return value is not None and value is not False


def plugin_flags(text):
    root = parse_settings(text)
    field = root.value.field("plugins_disabled")
    disabled = set()
    if field and field.value.value is not None:
        if not isinstance(field.value.value, Table):
            raise SettingsSyntaxError(
                "The disabled-plugin setting is not a literal table."
            )
        for entry in field.value.value.fields:
            if not isinstance(entry.key, str):
                raise SettingsSyntaxError(
                    "The disabled-plugin setting contains a non-text key."
                )
            field.value.value.field(entry.key)
            if _truthy(entry.value.value):
                disabled.add(entry.key)
    external = root.value.field("plugins_disable_external")
    paths = root.value.field("extra_plugin_paths")
    extra_paths = []
    if paths and paths.value.value is not None:
        value = paths.value.value
        if isinstance(value, str):
            extra_paths = [value]
        elif isinstance(value, Table) and all(
            isinstance(item.key, float) and isinstance(item.value.value, str)
            for item in value.fields
        ):
            extra_paths = [item.value.value for item in value.fields]
        else:
            raise SettingsSyntaxError(
                "The extra-plugin paths are not a literal list of paths."
            )
    return {
        "disabled": disabled,
        "externalDisabled": bool(external and external.value.value is True),
        "extraPluginPaths": extra_paths,
    }


def _quote(value):
    return (
        '"'
        + value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        + '"'
    )


def _append_field(text, table, key, literal):
    edits = [
        (
            table.end - 1,
            table.end - 1,
            "\n    [" + _quote(key) + "] = " + literal + ",\n",
        )
    ]
    if table.value.fields and not table.value.fields[-1].separator:
        position = table.value.fields[-1].value.end
        edits.append((position, position, ","))
    for start, end, replacement in sorted(edits, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text


def set_plugin_flag(text, plugin_id, enabled):
    """Change one plugins_disabled entry, leaving all other source text intact."""
    # Validate the entire document, including the target table's key semantics.
    plugin_flags(text)
    root = parse_settings(text)
    disabled = root.value.field("plugins_disabled")
    if not disabled or disabled.value.value is None:
        if enabled:
            return text
        literal = "{ [" + _quote(plugin_id) + "] = true, }"
        if disabled:
            return text[: disabled.value.start] + literal + text[disabled.value.end :]
        return _append_field(text, root, "plugins_disabled", literal)
    entry = disabled.value.value.field(plugin_id)
    if entry:
        # nil removes the effective Lua table key and preserves adjacent comments.
        value = "nil" if enabled else "true"
        return text[: entry.value.start] + value + text[entry.value.end :]
    if enabled:
        return text
    return _append_field(text, disabled.value, plugin_id, "true")
