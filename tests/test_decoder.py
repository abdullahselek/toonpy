"""Tests for decoder module."""

from toon_serializer.decoder import loads


def test_primitives():
    """Test decoding of basic primitive types."""
    toon_str = (
        "int: 42\n"
        "float: 3.14\n"
        "bool_true: true\n"
        "bool_false: false\n"
        "null_val: null\n"
        "simple_str: hello"
    )
    decoded = loads(toon_str)

    assert decoded["int"] == 42
    assert decoded["float"] == 3.14
    assert decoded["bool_true"] is True
    assert decoded["bool_false"] is False
    assert decoded["null_val"] is None
    assert decoded["simple_str"] == "hello"


def test_string_unquoting():
    """Test that quotes are removed and special chars are preserved."""
    toon_str = (
        'with_comma: "hello, world"\n'
        'with_colon: "key: value"\n'
        'empty: ""\n'
        'numeric_string: "123"'
    )
    decoded = loads(toon_str)

    assert decoded["with_comma"] == "hello, world"
    assert decoded["with_colon"] == "key: value"
    assert decoded["empty"] == ""
    assert decoded["numeric_string"] == "123"
    assert isinstance(decoded["numeric_string"], str)


def test_root_tabular_array():
    """Test parsing when the file is JUST a tabular array (no root dict)."""
    toon_str = "[2]{id,name}\n1,Alice\n2,Bob"
    expected = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]

    assert loads(toon_str) == expected


def test_root_tabular_array_with_colon():
    """Test regression fix: Header parsing with trailing colon."""
    toon_str = "[2]{id,name}:\n1,Ada\n2,Bob"
    expected = [{"id": 1, "name": "Ada"}, {"id": 2, "name": "Bob"}]

    assert loads(toon_str) == expected


def test_nested_tabular_array():
    """Test the key[N]{header}: syntax inside a dictionary."""
    toon_str = "meta: data\nusers[2]{id,role}:\n  10,admin\n  20,user"
    decoded = loads(toon_str)

    assert decoded["meta"] == "data"
    assert len(decoded["users"]) == 2
    assert decoded["users"][0] == {"id": 10, "role": "admin"}


def test_inline_csv_list():
    """Test inline array logic: '[N]: 1,2,3'."""
    toon_str = "[5]: 1, 2, 3, 4, 5"

    assert loads(toon_str) == [1, 2, 3, 4, 5]

    toon_nested = "data:\n  vals: [3]: 10, 20, 30"
    decoded = loads(toon_nested)

    assert decoded["data"]["vals"] == [10, 20, 30]


def test_standard_list_with_inline_dict():
    """Test list items that are dictionaries vs strings."""
    toon_str = "[3]:\n  - 1\n  - a: 1\n  - text"
    expected = [1, {"a": 1}, "text"]

    assert loads(toon_str) == expected


def test_adaptive_schema_fallback():
    """Test that V7 adaptive schema handles mixed types correctly."""
    toon_str = "[2]{val}\n100\nnot_a_number"
    expected = [{"val": 100}, {"val": "not_a_number"}]

    assert loads(toon_str) == expected


def test_empty_input():
    """Test resilience against empty strings."""
    assert loads("") is None


def test_complex_mixed_structure():
    """Test a mix of deep nesting, tabular arrays, and primitives."""
    toon_str = (
        "version: 1.0\n"
        "server:\n"
        "  config:\n"
        "    active: true\n"
        "    ports: [2]: 80, 443\n"
        "logs[2]{time,msg}:\n"
        "  10:00,start\n"
        "  10:01,stop"
    )
    decoded = loads(toon_str)

    assert decoded["version"] == 1.0
    assert decoded["server"]["config"]["active"] is True
    assert decoded["server"]["config"]["ports"] == [80, 443]
    assert decoded["logs"][1]["msg"] == "stop"


def test_numeric_edge_cases():
    """Negative numbers, floats, and fake numbers to test ValueError catches."""
    toon_str = (
        "negative: -50\n"
        "float: 12.34\n"
        "negative_float: -99.99\n"
        "ip_address: 192.168.1.1\n"
        "version: 2a\n"
        "dash_str: -option"
    )
    decoded = loads(toon_str)

    assert decoded["negative"] == -50
    assert decoded["float"] == 12.34
    assert decoded["negative_float"] == -99.99
    assert decoded["ip_address"] == "192.168.1.1"
    assert decoded["version"] == "2a"
    assert decoded["dash_str"] == "-option"


def test_tabular_adaptive_fallback_and_short_rows():
    """Covers tabular row shorter than headers."""
    toon_str = "[3]{col1,col2,col3}\n1, 2, 3\n4, 5\n7, eight, 9"
    decoded = loads(toon_str)

    assert decoded[1]["col1"] == 4
    assert decoded[1]["col2"] == 5
    assert decoded[1].get("col3") is None
    assert decoded[2]["col2"] == "eight"


def test_quoted_csv_paths():
    """Covers csv.reader usage in _parse_inline_csv_list and _parse_tabular_adaptive."""
    toon_str = 'inline: [2]: "a,b", c\ntable[1]{"col,1", col2}:\n  "val,1", val2'
    decoded = loads(toon_str)

    assert decoded["inline"] == ["a,b", "c"]
    assert decoded["table"][0]["col,1"] == "val,1"


def test_inline_dict_edge_cases():
    """Test the partitioning logic for inline dicts in lists."""
    toon_str = (
        "list[4]:\n"
        "  - simple_key: value\n"
        "  - empty_key:\n"
        "  - http://url\n"
        "  - 'quoted:key': val"
    )
    decoded = loads(toon_str).get("list")

    assert decoded[0] == {"simple_key": "value"}
    assert decoded[1] == {"empty_key": None}
    assert decoded[2] == "http://url"
    assert isinstance(decoded[3], str)


def test_indentation_termination():
    """Test for the 'break' conditions in loops when indentation decreases."""
    toon_str = "level1:\n  level2:\n    val: 1\n  back_to_2: 2\nback_to_1: 1"
    decoded = loads(toon_str)

    assert decoded["level1"]["level2"]["val"] == 1
    assert decoded["level1"]["back_to_2"] == 2
    assert decoded["back_to_1"] == 1


def test_malformed_lines_and_empty_blocks():
    """Test for partition failure, stop iteration, empty inputs."""
    toon_str = (
        "key_with_no_separator\nvalid: 1\n\n   \nempty_list: []\nempty_inline_list: [0]:"
    )
    decoded = loads(toon_str)

    assert decoded.get("key_with_no_separator") is None
    assert decoded["valid"] == 1
    assert decoded["empty_list"] == []
    assert decoded["empty_inline_list"] == []


def test_tabular_short_header_row_filling():
    """Test case for the loop in tabular init."""
    toon_str = "[1]{a,b,c}\n1"
    decoded = loads(toon_str)

    assert decoded[0]["a"] == 1
    assert decoded[0]["b"] is None
    assert decoded[0]["c"] is None


def test_stop_iteration_in_loops():
    """Test case for StopIteration inside _parse_block and _parse_list_items loops."""
    toon_str = "outer:\n  inner:"
    decoded = loads(toon_str)

    assert decoded["outer"]["inner"] == {}

    toon_str_list = "list[2]:\n  - 1"
    decoded_list = loads(toon_str_list)

    assert decoded_list["list"] == [1]


def test_scientific_notation():
    """Test parsing of scientific notation which often bypasses standard float/int regex."""
    toon_str = "small: 1.5e-10\nlarge: 2.5E+10\nint_scientific: 1e5"
    decoded = loads(toon_str)

    assert decoded["small"] == 1.5e-10
    assert decoded["large"] == 2.5e10
    assert decoded["int_scientific"] == 100000.0  # Usually parses as float


def test_tabular_primitive_conversion():
    """Test that tabular rows convert true/false/null, not just numbers/strings."""
    toon_str = "[2]{is_valid,result,nothing}\ntrue, 42, null\nfalse, 0, undefined"
    decoded = loads(toon_str)

    assert decoded[0]["is_valid"] is True
    assert decoded[0]["result"] == 42
    assert decoded[0]["nothing"] is None

    assert decoded[1]["is_valid"] is False
    assert decoded[1]["result"] == 0
    assert decoded[1]["nothing"] == "undefined"


def test_keys_mimicking_syntax():
    """Test keys containing brackets/braces that shouldn't trigger array parsing."""
    toon_str = "key[with_brackets]: value\nkey{with_braces}: value\nnormal: 1"
    decoded = loads(toon_str)

    assert decoded["key[with_brackets]"] == "value"
    assert decoded["key{with_braces}"] == "value"
    assert decoded["normal"] == 1


def test_whitespace_preservation_in_values():
    """Test that internal whitespace in values is preserved, while surrounding is stripped."""
    toon_str = "sentence: This is a sentence.\npadded:    internal   spaces   "
    decoded = loads(toon_str)

    assert decoded["sentence"] == "This is a sentence."
    assert decoded["padded"].strip() == "internal   spaces"


def test_inline_list_trailing_comma():
    """Test resilience against trailing commas in inline CSV lists."""
    toon_str = "[3]: 10, 20, 30,"
    decoded = loads(toon_str)

    assert len(decoded) >= 3
    assert decoded[0] == 10


def test_root_list_of_lists():
    """Test a list where items are themselves inline lists (nested structure)."""
    toon_str = "matrix[2]:\n  - [2]: 1, 0\n  - [2]: 0, 1"
    decoded = loads(toon_str)

    assert decoded["matrix"][0] == [1, 0]
    assert decoded["matrix"][1] == [0, 1]


def test_comment_like_strings():
    """Test that hash symbols are treated as strings unless specific comment logic exists."""
    toon_str = "color: #FF0000\nhashtag: #nofilter"
    decoded = loads(toon_str)

    assert decoded["color"] == "#FF0000"
    assert decoded["hashtag"] == "#nofilter"


def test_tabular_edge_cases():
    """Test tabular parsing resilience."""
    toon_str = "[2]{a,b,c}\n1, 2, 3\n10,,30"
    decoded = loads(toon_str)

    assert decoded[1]["a"] == 10
    assert decoded[1]["b"] is None
    assert decoded[1]["c"] == 30

    empty_table = "[5]{a,b}"

    assert loads(empty_table) == []


def test_multiline_list_items():
    """Test list items defined as nested blocks."""
    toon_str = "items[2]:\n  - \n    id: 1\n    val: A\n  - \n    id: 2\n    val: B"
    decoded = loads(toon_str)

    assert len(decoded["items"]) == 2
    assert decoded["items"][0] == {"id": 1, "val": "A"}
    assert decoded["items"][1] == {"id": 2, "val": "B"}


def test_tabular_ambiguous_first_row_types():
    """Test that _detect_type_and_convert handles values that look like numbers."""
    toon_str = "[2]{version,flag}\n1.2.3, -flag\n1.2.4, -verbose"
    decoded = loads(toon_str)

    assert decoded[0]["version"] == "1.2.3"
    assert decoded[0]["flag"] == "-flag"
    assert decoded[1]["version"] == "1.2.4"
