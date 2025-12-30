# toonpy: Token Oriented Object Notation for Python

ToonPy is a high performance Python serializer/deserializer for TOON (Token Oriented Object Notation).

TOON is a human readable data format designed to minimize token usage for LLMs by removing redundant syntax (braces, quotes, repeated keys) while maintaining structure. It excels at compressing list of dictionaries into Tabular Arrays, often reducing payload sizes by 30-50% compared to JSON.

## Features

- 📉 Token Efficient Replaces repetitive JSON keys with compact CSV-like headers.
- 🧠 Adaptive Schema The decoder "learns" column types from the first row to parse massive tables instantly.
- ⚡ Fast Primitives Optimized integer, float, and boolean parsing.
- csv-compatible Handles complex string escaping and quoting automatically.
- Lazy Decoding Iterates over lines lazily, efficient for large datasets.

## Installation

```bash
pip install toonpy
```


## Usage

ToonPyy mimics the standard Python json API with loads and dumps.

1. Encoding Data (Serialization)

ToonPy automatically detects Uniform Lists of Dictionaries and compresses them into a tabular format.

Input

```python
import toonpy

data = {
    "model": "gpt-4",
    "parameters": {
        "temperature": 0.7,
        "stream": True
    },
    "messages": [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Explain quantum physics."},
        {"role": "assistant", "content": "Quantum physics studies..."}
    ]
}

toon_str = toonpy.dumps(data)
print(toon_str)
```

Output:

```yaml
model: gpt-4
parameters:
  temperature: 0.7
  stream: true
messages[3]{role,content}:
  system,"You are a helpful assistant."
  user,"Explain quantum physics."
  assistant,"Quantum physics studies..."
```

2. Decoding Data (Deserialization)

The decoder handles primitives, standard lists, and adaptive tabular arrays seamlessly.

```python
import toonpy

toon_str = """
version: 1.0
users[2]{id,name,is_active}:
  1,Alice,true
  2,Bob,false
tags[3]: python, rust, go
"""

data = toonpy.loads(toon_str)

print(data["users"][0]) 
# {'id': 1, 'name': 'Alice', 'is_active': True}

print(data["tags"])
# ['python', 'rust', 'go']
```

## Performance Notes

- Encoder recursively checks for "uniformity" in lists. If a list contains mixed types, it gracefully falls back to a standard bulleted list.
- Decoder uses a Pushback Iterator to parse line-by-line without loading the entire string into memory.
- Adaptive Parsing when decoding tables, ToonPy inspects the first row to generate a specialized converter function (e.g., "Column 1 is int, Column 2 is string"), speeding up parsing for the remaining rows.

## Contributing

1. Fork the repository.
2. Create a feature branch.
3. Add tests.
4. Submit a Pull Request.