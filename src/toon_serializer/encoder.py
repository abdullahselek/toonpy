"""Encoder module of toon_serializer."""

from typing import Any


class ToonEncoder:
    """Encoder that encodes given data format to TOON string."""

    def encode(self, data: None | dict | list) -> str:
        """Public entry point for encoding data to TOON format.

        Args:
            data (None | dict | list): Data in JSON format.

        Returns:
            String in TOON format.

        """
        return self._recursive_encode(data, indent_level=0)

    def _recursive_encode(self, data: None | dict | list, indent_level: int) -> str:
        """Encode given data recursiverly."""
        indent = "  " * indent_level

        if data is None:
            return "null"

        if isinstance(data, (str, int, float, bool)):
            return self._format_primitive(data)

        if isinstance(data, list):
            if not data:
                return "[]"

            if self._is_uniform_dict_list(data):
                return self._encode_tabular_list(data, indent)

            return self._encode_standard_list(data, indent_level)

        if isinstance(data, dict):
            if not data:
                return "{}"
            return self._encode_dict(data, indent_level, indent)

    def _encode_tabular_list(self, data: list[dict[str, Any]], indent: str) -> str:
        """Encode a list of uniform dictionaries as a CSV like table."""
        if not data:
            return "[]"

        headers = list(data[0].keys())
        header_str = ",".join(headers)
        count = len(data)

        lines = [f"[{count}]{{{header_str}}}:"]

        for item in data:
            row_values = []
            for h in headers:
                val = item.get(h)
                row_values.append(self._format_primitive(val))
            lines.append(f"{indent}  {','.join(row_values)}")

        return "\n".join(lines)

    def _encode_standard_list(
        self, data: list[Any], indent_level: int, indent: str = " "
    ) -> str:
        """Encode a mixed or non uniform list."""
        header = f"[{len(data)}]:"
        lines = []
        for item in data:
            val_str = self._recursive_encode(item, indent_level + 1)
            lines.append(f"{val_str.lstrip()}")
        items = ",".join(lines)
        return header + indent + items

    def _encode_dict(self, data: dict[str, Any], indent_level: int, indent: str) -> str:
        """Encode a dictionary."""
        lines = []
        for key, value in data.items():
            if isinstance(value, list) and self._is_uniform_dict_list(value):
                headers = list(value[0].keys())
                header_str = ",".join(headers)
                count = len(value)

                lines.append(f"{indent}{key}[{count}]{{{header_str}}}:")
                for item in value:
                    row_values = [self._format_primitive(item.get(h)) for h in headers]
                    lines.append(f"{indent}  {','.join(row_values)}")
            elif isinstance(value, (str, int, float, bool, type(None))):
                lines.append(f"{indent}{key}: {self._format_primitive(value)}")
            else:
                encoded_val = self._recursive_encode(value, indent_level + 1)
                if encoded_val.startswith("["):  # Array
                    lines.append(f"{key}{encoded_val}")
                else:  # Nested Object
                    lines.append(f"{indent}{key}:\n{encoded_val}")

        return "\n".join(lines)

    def _is_uniform_dict_list(self, lst: list[Any]) -> bool:
        """Check if list contains only dicts with identical keys."""
        if not lst or not isinstance(lst[0], dict):
            return False
        first_keys = set(lst[0].keys())
        for item in lst[1:]:
            if not isinstance(item, dict) or set(item.keys()) != first_keys:
                return False
        return True

    def _format_primitive(self, val: Any) -> str:
        """Format primitives, minimizing quotes."""
        if val is None:
            return "null"
        if isinstance(val, bool):
            return "true" if val else "false"

        s_val = str(val)
        if (
            any(c in s_val for c in [",", "\n", ":", "[", "]", "{", "}"])
            or s_val.strip() == ""
        ):
            return f'"{s_val}"'
        return s_val


def dumps(data: Any) -> str:
    """Encode given data in any data type and return string in TOON format.

    Args:
        data (Any): Data to be encoded to TOON.

    Returns:
        String in TOON format.

    """
    return ToonEncoder().encode(data)
