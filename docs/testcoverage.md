# Test Coverage Guide

## Overview

The test suite uses [pytest](https://docs.pytest.org/) with [pytest-cov](https://pytest-cov.readthedocs.io/) and covers all modules in the `sharklocal` package. Branch coverage is enabled, meaning both sides of every conditional must be exercised.

Current coverage: <br/>
[![codecov](https://codecov.io/gh/sharkiqlibs/sharklocal/graph/badge.svg?token=kLonrWzpxx)](https://codecov.io/gh/sharkiqlibs/sharklocal)

---

## Running the Tests

### Install dev dependencies

```bash
pip install -e ".[dev]"
```

This installs `pytest`, `pytest-asyncio`, and `pytest-cov` alongside the library and its runtime dependencies (`aiohttp`, `aiomqtt`, `PyYAML`).

### Run all tests with coverage

```bash
python3 -m pytest --cov=sharklocal --cov-report=term-missing
```

The `--cov-report=term-missing` flag prints a per-file summary with the exact line numbers and branch transitions that are not covered.

### Run a single test file

```bash
python3 -m pytest tests/test_client.py -v
```

### Run a single test by name

```bash
python3 -m pytest -k "test_request_status_timeout_raises_command_error" -v
```

### Run without coverage (faster)

```bash
python3 -m pytest
```

---

## Coverage Threshold

The minimum required coverage is **95%**, enforced by `pyproject.toml`:

```toml
[tool.coverage.report]
fail_under = 95
```

`pytest` will exit with a non-zero status code if total coverage falls below this threshold, causing CI to fail. Do not lower this value.

---

## Test Configuration

All configuration lives in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"     # all async test functions run automatically as coroutines
testpaths = ["tests"]     # only the tests/ directory is collected

[tool.coverage.run]
source = ["sharklocal"]   # measure coverage only for library code
branch = true             # require both sides of every branch to be exercised
```

`asyncio_mode = "auto"` means you do **not** need to decorate async tests with `@pytest.mark.asyncio` — they are detected and run automatically.

---

## Test File Layout

Each source module has a corresponding test file:

| Source | Test file |
|---|---|
| `sharklocal/client.py` | `tests/test_client.py` |
| `sharklocal/mqtt_client.py` | `tests/test_mqtt_client.py` |
| `sharklocal/rest_client.py` | `tests/test_rest_client.py` |
| `sharklocal/models.py` | `tests/test_models.py` |
| `sharklocal/exceptions.py` | `tests/test_exceptions.py` |
| `sharklocal/protobuf.py` | `tests/test_protobuf.py` |
| `sharklocal/mappings/` | `tests/test_mappings_base.py`, `tests/test_mappings_loader.py` |
| `sharklocal/__main__.py` | `tests/test_main.py` |

Shared fixtures (mock mappings, sample API responses) live in `tests/conftest.py`.

---

## Writing New Tests

### Naming and structure

- Test functions must start with `test_`.
- Place tests in the file that corresponds to the module under test.
- Group related tests under a comment block, for example:

```python
# ---------------------------------------------------------------------------
# _request_status() — timeout behaviour
# ---------------------------------------------------------------------------

async def test_request_status_timeout_raises_command_error(mqtt_mapping):
    ...
```

### Async tests

Any test that awaits a coroutine must be declared `async`. Because `asyncio_mode = "auto"` is set, no decorator is needed:

```python
async def test_my_async_behaviour():
    result = await some_coroutine()
    assert result == expected
```

### Using fixtures

The shared fixtures in `conftest.py` provide ready-made mapping objects:

```python
def test_something(rest_mapping):
    # rest_mapping is a RESTMappingConfig pre-loaded with sharkiq_v1 defaults
    assert "get_status" in rest_mapping.actions

async def test_something_mqtt(mqtt_mapping):
    client = MQTTVacuumClient("192.168.1.1", mqtt_mapping)
    ...
```

### Mocking external I/O

All tests that touch network transports must mock the underlying clients. Use `unittest.mock.patch` and `AsyncMock` rather than hitting a real device:

```python
from unittest.mock import AsyncMock, patch

async def test_call_publishes_command(mqtt_mapping):
    mock_inner = AsyncMock()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_inner)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("aiomqtt.Client", return_value=mock_ctx):
        result = await MQTTVacuumClient("host", mqtt_mapping).call("start_cleaning")

    assert result is True
    mock_inner.publish.assert_awaited_once()
```

For REST clients, patch `aiohttp.ClientSession` at the point it is imported:

```python
with patch("sharklocal.rest_client.aiohttp.ClientSession") as mock_session:
    ...
```

### Covering both sides of a branch

Because branch coverage is enabled, every `if` / `elif` / `else` needs at least one test that takes the True path and one that takes the False path. If you add a conditional to the library, add a matching test for each branch.

For a condition like:

```python
if action not in mapping.actions:
    raise ActionNotSupportedError(...)
```

You need two test cases: one where `action` is in the mapping (success path) and one where it is not (error path).

### Marking genuinely unreachable code

Occasionally a line is logically unreachable but required for defensive correctness, or it cannot be executed by the coverage tool due to a Python version limitation (e.g., `async for` exit branches in Python 3.9). In these cases, annotate with `# pragma: no cover` rather than writing a contrived test:

```python
raise SomeError("This path is logically unreachable")  # pragma: no cover
```

Use this sparingly. Prefer real tests over pragmas wherever possible.

---

## Known Coverage Limitations (Python 3.9)

Two partial branch gaps remain in `mqtt_client.py` (`168->175` and `201->exit`) that reflect a Python 3.9 coverage tool limitation — the `async for` loop exit branch is not tracked correctly by coverage.py 6.x on Python 3.9, even though the code paths are genuinely exercised by tests. These gaps disappear when running under Python 3.11+.

The library's minimum supported runtime is Python 3.11 (`requires-python = ">=3.11"` in `pyproject.toml`). If your local Python is 3.11 or later, you will see 100% branch coverage.
