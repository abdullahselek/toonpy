"""Tests for encoder module."""

import pytest

from toon_serializer.encoder import ToonEncoder, dumps


@pytest.fixture
def encoder():
    """Fixture for ToonEncoder."""
    return ToonEncoder()


@pytest.mark.parametrize(
    "input_val, expected",
    [
        (None, "null"),
        (True, "true"),
        (False, "false"),
        (123, "123"),
        (3.14, "3.14"),
        ("simple", "simple"),
    ],
)
def test_primitives(encoder, input_val, expected):
    """Test basic primitive types that don't require quoting."""
    assert encoder.encode(input_val) == expected


@pytest.mark.parametrize(
    "input_str, expected",
    [
        ("", '""'),
        ("hello,world", '"hello,world"'),
        ("line1\nline2", '"line1\nline2"'),
        ("key:value", '"key:value"'),
        ("[bracket]", '"[bracket]"'),
        ("{brace}", '"{brace}"'),
        ("  ", '"  "'),
    ],
)
def test_string_quoting_rules(encoder, input_str, expected):
    """Test strings that trigger the auto-quoting logic."""
    assert encoder.encode(input_str) == expected


def test_empty_structures(encoder):
    """Test empty lists and dictionaries."""
    assert encoder.encode([]) == "[]"
    assert encoder.encode({}) == "{}"


def test_basic_dict(encoder):
    """Test basic dictionary."""
    data = {"id": 123456, "name": "Joe", "tags": ["tester", "user"], "active": False}
    expected = "id: 123456\nname: Joe\ntags[2]: tester,user\nactive: false"

    assert encoder.encode(data) == expected


def test_tabular_list_optimization_root(encoder):
    """Test a list of uniform objects at the root level."""
    data = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
    expected = "[2]{id,name}:\n  1,Alice\n  2,Bob"

    assert encoder.encode(data) == expected


def test_tabular_list_inside_dict(encoder):
    """Test tabular optimization when nested inside a dictionary."""
    data = {"users": [{"id": 1, "role": "admin"}, {"id": 2, "role": "user"}]}
    expected = "users[2]{id,role}:\n  1,admin\n  2,user"

    assert encoder.encode(data) == expected


def test_tabular_list_multi_uniform_dict(encoder):
    """Test tabular list that contains multiple uniform dicts."""
    data = [{"sku": "A1", "qty": 2, "price": 9.99}, {"sku": "B2", "qty": 1, "price": 14.5}]
    expected = "[2]{sku,qty,price}:\n  A1,2,9.99\n  B2,1,14.5"

    assert encoder.encode(data) == expected


def test_mixed_list_fallback(encoder):
    """Test a list that is not uniform."""
    data = [1, "two", True]
    expected = "[3]: 1,two,true"

    assert encoder.encode(data) == expected


def test_nested_dictionaries(encoder):
    """Test standard nested dictionary encoding."""
    data = {"server": {"config": {"port": 80}}}
    expected = "server:\n  config:\n    port: 80"

    assert encoder.encode(data) == expected


def test_complex_structure(encoder):
    """Test a mix of primitives, dicts, and tabular arrays."""
    data = {
        "version": 1.0,
        "meta": {"active": True},
        "logs": [{"time": "10:00", "msg": "start"}, {"time": "10:01", "msg": "end"}],
    }

    result = encoder.encode(data)

    assert "version: 1.0" in result
    assert "meta:\n  active: true" in result
    assert "logs[2]{time,msg}:" in result
    assert '"10:00",start' in result or 'start,"10:00"' in result


def test_dumps_wrapper():
    """Ensure the module-level helper function works."""
    data = {"a": 1}

    assert dumps(data) == "a: 1"
