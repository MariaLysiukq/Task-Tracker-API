"""Unit tests for the empty-line pre-commit hook in ``scripts/``."""

from pathlib import Path

import pytest

from scripts.check_empty_lines import find_empty_lines, main

ALLOWED_SOURCES = {
    "docstring_with_empty_lines": '''
def func():
    """Summary.

    Parameters
    ----------
    """
    return 1
''',
    "multiline_string_with_empty_lines": '''
def func():
    query = """
    SELECT *

    FROM users
    """
    return query
''',
    "multiline_fstring_with_empty_lines": '''
def func(name):
    text = f"""
    Hello

    {name}
    """
    return text
''',
    "comments_between_statements": """
def func():
    a = 1
    # explanation
    return a
""",
    "module_and_class_level_empty_lines": """
import os


class Service:

    attribute = 1

    def run(self):
        return os.sep


def other():
    return 2
""",
}

FORBIDDEN_SOURCES = {
    "between_statements": (
        """
def func():
    a = 1

    return a
""",
        [(4, "func")],
    ),
    "after_docstring": (
        '''
def func():
    """Summary."""

    return 1
''',
        [(4, "func")],
    ),
    "async_function": (
        """
async def handler():
    a = 1

    return a
""",
        [(4, "handler")],
    ),
    "method": (
        """
class Service:
    def run(self):
        a = 1

        return a
""",
        [(5, "run")],
    ),
    "nested_function_reported_once": (
        """
def outer():
    def inner():
        a = 1

        return a
    return inner
""",
        [(5, "inner")],
    ),
    "before_nested_function": (
        """
def outer():
    a = 1

    def inner():
        return a
    return inner
""",
        [(4, "outer")],
    ),
    "whitespace_only_line": (
        "def func():\n    a = 1\n    \n    return a\n",
        [(3, "func")],
    ),
}


@pytest.mark.parametrize("source", ALLOWED_SOURCES.values(), ids=ALLOWED_SOURCES.keys())
def test_allowed_sources_have_no_violations(source: str) -> None:
    """Accept empty lines inside string literals and outside function bodies."""
    assert find_empty_lines(source) == []


@pytest.mark.parametrize(
    ("source", "expected"),
    FORBIDDEN_SOURCES.values(),
    ids=FORBIDDEN_SOURCES.keys(),
)
def test_forbidden_sources_are_reported(source: str, expected: list[tuple[int, str]]) -> None:
    """Report each empty line between statements with the innermost function name."""
    assert find_empty_lines(source) == expected


def test_main_reports_violation_and_fails(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Return 1 and print the file location of the empty line."""
    source, _ = FORBIDDEN_SOURCES["between_statements"]
    path = tmp_path / "bad.py"
    path.write_text(source, encoding="utf-8")
    assert main([str(path)]) == 1
    assert f"{path}:4: empty line in function 'func'" in capsys.readouterr().out


def test_main_passes_clean_file(tmp_path: Path) -> None:
    """Return 0 when no file contains violations."""
    path = tmp_path / "good.py"
    path.write_text(ALLOWED_SOURCES["docstring_with_empty_lines"], encoding="utf-8")
    assert main([str(path)]) == 0


def test_main_fails_on_syntax_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Return 1 when a file cannot be parsed."""
    path = tmp_path / "broken.py"
    path.write_text("def func(:\n    pass\n", encoding="utf-8")
    assert main([str(path)]) == 1
    assert "cannot parse file" in capsys.readouterr().out
