"""Decoder module of toon_serializer."""

import csv
from collections.abc import Callable
from itertools import islice
from typing import Any

# Fast Primitives
_int = int
_float = float
_dict = dict
_zip = zip
_len = len


def _convert_bool(v: str) -> Any:
    """Convert a string true or false to a boolean."""
    return True if v == "true" else False


def _convert_str_unquote(v: str) -> str:
    """Remove surrounding quotes from a string if present."""
    if len(v) >= 2 and v.startswith('"') and v.endswith('"'):
        return v[1:-1]
    return v


def _convert_identity(v: str) -> str:
    """Return the input string as is, identity function."""
    return v


def _convert_null(v: str) -> None:
    """Return None if input is 'null', otherwise raise ValueError to trigger fallback."""
    if v == "null":
        return None
    raise ValueError(f"Expected null, got {v}")


class ToonDecoder:
    """ToonDecoder class that decodes TOON strings into Python objects.

    This class uses an adaptive schema strategy for tabular data to maximize performance.
    It iterates over the source string lazily to minimize memory usage.
    """

    __slots__ = ("_lines", "_pushback_line")

    def __init__(self, source: str):
        """Initialize the decoder with a TOON formatted string.

        Args:
            source (str): The TOON string to decode.

        """
        self._lines = iter(source.splitlines())
        self._pushback_line: tuple[str, int] | None = None

    def decode(self) -> Any:
        """Decode the full TOON string into a Python object.

        Returns:
            The decoded Python dictionary or list. Returns an empty dict if input is empty.

        """
        try:
            line, indent = self._next_line()
        except StopIteration:
            return {}

        # Root Array Check
        if line.startswith("["):
            idx_close = line.find("]")
            if idx_close != -1:
                # Tabular [N]{headers} or [N]{headers}:
                if "{" in line:
                    idx_brace_open = line.find("{", idx_close)
                    if idx_brace_open != -1:
                        # Explicitly find closing brace to handle trailing colons
                        idx_brace_close = line.rfind("}")
                        if idx_brace_close != -1:
                            count = _int(line[1:idx_close])
                            headers_str = line[idx_brace_open + 1 : idx_brace_close]
                            return self._parse_tabular_adaptive(headers_str, count)

                # Standard List
                idx_colon = line.find(":", idx_close)
                if idx_colon != -1:
                    val_part = line[idx_colon + 1 :].strip()
                    if val_part:
                        return self._parse_inline_csv_list(val_part)

                return self._parse_list_items(base_indent=-1)

        # Root Dict
        self._push_line(line, indent)
        return self._parse_block(base_indent=-1)

    def _next_line(self) -> tuple[str, int]:
        """Retrieve the next non empty line from the iterator.

        Returns:
            A tuple containing the stripped line string and its indentation level.

        Raises:
            StopIteration: If there are no more lines in the source.

        """
        if self._pushback_line:
            ret = self._pushback_line
            self._pushback_line = None
            return ret

        for line in self._lines:
            stripped = line.lstrip()
            if stripped:
                return stripped, _len(line) - _len(stripped)

        raise StopIteration

    def _push_line(self, line: str, indent: int) -> None:
        """Push a line back onto the stack to be reread by _next_line().

        Args:
            line (str): The line content.
            indent (int): The indentation level.

        """
        self._pushback_line = (line, indent)

    def _detect_type_and_convert(self, v: str) -> tuple[Any, Callable[[str], Any]]:
        """Analyze a string value to guess its type and returns the converted value.

        It passes along with the most appropriate conversion function for future use.

        Args:
            v (str): The raw string value.

        Returns:
            The converted value and the function used to convert it.

        """
        if not v:
            return None, _convert_identity

        if v == "true":
            return True, _convert_bool
        if v == "false":
            return False, _convert_bool
        if v == "null":
            return None, _convert_null

        if v.startswith('"'):
            val = v[1:-1] if v.endswith('"') else v
            return val, _convert_str_unquote

        c = ord(v[0])
        if 48 <= c <= 57 or c == 45:  # 0-9 or -
            try:
                return _int(v), _int
            except ValueError:
                try:
                    return _float(v), _float
                except ValueError:
                    return v, _convert_identity

        return v, _convert_identity

    def _parse_val_generic(self, v: str) -> Any:
        """Parse a single string value into a primitive type without inferring a schema.

        Args:
            v (str): The raw string value.

        Returns:
            The converted primitive value or the original string.

        """
        if not v:
            return None
        if v == "true":
            return True
        if v == "false":
            return False
        if v == "null":
            return None
        if v.startswith('"'):
            return v[1:-1] if v.endswith('"') else v

        c = ord(v[0])
        if 48 <= c <= 57 or c == 45:
            try:
                return _int(v)
            except ValueError:
                try:
                    return _float(v)
                except ValueError:
                    return v
        return v

    def _parse_inline_csv_list(self, csv_line: str) -> list[Any]:
        """Parse a single line of comma-separated values into a list.

        Args:
            csv_line (str): The CSV string.

        Returns:
            A list of parsed values.

        """
        if '"' in csv_line:
            parts = next(csv.reader([csv_line], skipinitialspace=True))
        else:
            parts = csv_line.split(",")
        return [self._parse_val_generic(p.strip()) for p in parts]

    def _parse_tabular_adaptive(self, header_str: str, count: int) -> list[dict[str, Any]]:
        """Parse a block of tabular data using adaptive schema learning.

        It inspects the first row to determine column types and generates specialized
        converters for subsequent rows to improve performance.

        Args:
            header_str (str): The comma-separated headers (e.g., "id,name").
            count (int): The number of rows to parse.

        Returns:
            A list of dictionaries representing the table.

        """
        if '"' in header_str:
            headers = next(csv.reader([header_str], skipinitialspace=True))
        else:
            headers = [h.strip() for h in header_str.split(",")]

        num_headers = len(headers)
        raw_lines = islice(self._lines, count)
        result = []
        result_append = result.append

        try:
            first_line = next(raw_lines)
        except StopIteration:
            return []

        first_line = first_line.lstrip()
        if '"' in first_line:
            parts = next(csv.reader([first_line], skipinitialspace=True))
        else:
            parts = first_line.split(",")

        converters = []
        first_row_values = []

        for p in parts:
            p = p.strip()
            val, func = self._detect_type_and_convert(p)
            first_row_values.append(val)
            converters.append(func)

        while len(converters) < num_headers:
            converters.append(_convert_identity)
            first_row_values.append(None)

        result_append(_dict(_zip(headers, first_row_values)))

        for line in raw_lines:
            line = line.lstrip()
            if '"' not in line:
                parts = line.split(",")
            else:
                parts = next(csv.reader([line], skipinitialspace=True))

            clean_values = []
            cv_append = clean_values.append

            for i in range(min(len(parts), num_headers)):
                p = parts[i].strip()
                if not p:
                    cv_append(None)
                    continue

                try:
                    cv_append(converters[i](p))
                except ValueError:
                    # Prediction failed (e.g. column was Int, now got String)
                    val = self._parse_val_generic(p)
                    cv_append(val)
                    # Downgrade converter to generic to avoid future exceptions
                    converters[i] = self._parse_val_generic

            result_append(_dict(_zip(headers, clean_values)))

        return result

    def _parse_list_items(self, base_indent: int) -> list[Any]:
        """Parse a standard TOON list block (lines starting with '-').

        Args:
            base_indent (int): The indentation level of the parent key.

        Returns:
            The parsed list of items.

        """
        res = []
        append = res.append
        parse = self._parse_val_generic

        while True:
            try:
                line, indent = self._next_line()
            except StopIteration:
                break

            if base_indent != -1 and indent <= base_indent:
                self._push_line(line, indent)
                break

            if line.startswith("- "):
                val_part = line[2:].strip()
                if val_part:
                    # Check for inline array syntax: "- [N]: val, val"
                    if val_part.startswith("[") and "]:" in val_part:
                        idx_close = val_part.find("]:")
                        # Ensure content inside brackets is a number (size)
                        if val_part[1:idx_close].isdigit():
                            content = val_part[idx_close + 2 :].strip()
                            append(self._parse_inline_csv_list(content))
                            continue

                    is_inline_dict = False
                    if ":" in val_part and not val_part.startswith('"'):
                        k_candidate, _, v_candidate = val_part.partition(":")
                        # Ensure it's a key-value pair
                        if not v_candidate or v_candidate.startswith(" "):
                            k = k_candidate.strip()
                            v = v_candidate.strip()
                            append({k: parse(v)})
                            is_inline_dict = True

                    if not is_inline_dict:
                        append(parse(val_part))
                else:
                    append(self._parse_block(indent))
            else:
                self._push_line(line, indent)
                break
        return res

    def _parse_block(self, base_indent: int) -> dict[str, Any]:
        """Parse a dictionary block based on indentation hierarchy.

        Args:
            base_indent (int): The indentation level of the parent block.

        Returns:
            The parsed dictionary.

        """
        res = {}
        parse = self._parse_val_generic

        while True:
            try:
                line, indent = self._next_line()
            except StopIteration:
                break

            if base_indent != -1 and indent <= base_indent:
                self._push_line(line, indent)
                break

            key_part, sep, val_part = line.partition(":")
            if not sep:
                continue

            key = key_part.strip()
            val = val_part.strip()

            # Handle Tabular Arrays inside Dict: key[N]{headers}
            if "]" in key and key.endswith("}"):
                idx_brack = key.find("[")
                if idx_brack != -1:
                    idx_brace = key.find("{", idx_brack)
                    if idx_brace != -1:
                        real_key = key[:idx_brack]
                        count = _int(key[idx_brack + 1 : key.find("]", idx_brack)])
                        idx_brace_close = key.rfind("}")
                        h_str = key[idx_brace + 1 : idx_brace_close]
                        res[real_key] = self._parse_tabular_adaptive(h_str, count)
                        continue

            if key.endswith("]") and "[" in key:
                idx_brack = key.rfind("[")
                if idx_brack != -1:
                    # Only strip if it is a size indicator like [5], not a key name like [id]
                    if key[idx_brack + 1 : -1].isdigit():
                        key = key[:idx_brack].strip()

            if val:
                if val.startswith("[") and val.endswith("]"):
                    if val == "[]":
                        res[key] = []
                    else:
                        # Standard array marker [N] (multiline follows)
                        res[key] = self._parse_list_items(indent)
                # Check for inline array: "key: [5]: 1,2,3"
                elif val.startswith("[") and "]:" in val:
                    idx_close = val.find("]:")
                    if idx_close != -1:
                        inline_content = val[idx_close + 2 :].strip()
                        if inline_content:
                            res[key] = self._parse_inline_csv_list(inline_content)
                        else:
                            res[key] = self._parse_list_items(indent)
                    else:
                        res[key] = parse(val)
                else:
                    res[key] = parse(val)
            else:
                try:
                    next_l, next_i = self._next_line()
                    self._push_line(next_l, next_i)
                    if next_l.startswith("- "):
                        res[key] = self._parse_list_items(indent)
                    else:
                        res[key] = self._parse_block(indent)
                except StopIteration:
                    res[key] = {}

        return res


def loads(toon_str: str) -> Any:
    """Deserialize a TOON formatted string into a Python object.

    Args:
        toon_str (str): The TOON string to decode.

    Returns:
        The decoded Python dictionary or list. Returns None if input is empty or None.

    """
    if not toon_str:
        return None
    return ToonDecoder(toon_str).decode()
