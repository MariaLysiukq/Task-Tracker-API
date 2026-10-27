"""Pre-commit hook that forbids empty lines between statements in function bodies.

Empty lines inside string literals (docstrings, multiline strings, f-strings and
t-strings) are allowed. Each offending line is reported once, attributed to the
innermost function that contains it.
"""

import ast
import io
import sys
import tokenize
from collections.abc import Sequence
from pathlib import Path

PREFIXED_STRING_TOKENS = (
    (getattr(tokenize, "FSTRING_START", None), getattr(tokenize, "FSTRING_END", None)),
    (getattr(tokenize, "TSTRING_START", None), getattr(tokenize, "TSTRING_END", None)),
)


def collect_string_lines(source: str) -> set[int]:
    """Collect line numbers covered by string literals.

    Parameters
    ----------
    source : str
        Python source code.

    Returns
    -------
    set[int]
        1-based line numbers that belong to any string literal.

    Raises
    ------
    tokenize.TokenError
        If the source cannot be tokenized.
    """
    string_lines: set[int] = set()
    open_prefixed_strings: list[int] = []
    start_types = {start for start, _ in PREFIXED_STRING_TOKENS if start is not None}
    end_types = {end for _, end in PREFIXED_STRING_TOKENS if end is not None}
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.STRING:
            string_lines.update(range(token.start[0], token.end[0] + 1))
        elif token.type in start_types:
            open_prefixed_strings.append(token.start[0])
        elif token.type in end_types and open_prefixed_strings:
            string_lines.update(range(open_prefixed_strings.pop(), token.end[0] + 1))
    return string_lines


def statement_start_line(statement: ast.stmt) -> int:
    """Return the first line of a statement, including its decorators.

    Parameters
    ----------
    statement : ast.stmt
        Statement node.

    Returns
    -------
    int
        1-based line number where the statement begins.
    """
    decorators = getattr(statement, "decorator_list", [])
    return min([statement.lineno, *(decorator.lineno for decorator in decorators)])


def find_empty_lines(source: str) -> list[tuple[int, str]]:
    """Find forbidden empty lines inside function bodies.

    Parameters
    ----------
    source : str
        Python source code.

    Returns
    -------
    list[tuple[int, str]]
        Sorted pairs of 1-based line number and innermost function name.

    Raises
    ------
    SyntaxError
        If the source is not valid Python.
    tokenize.TokenError
        If the source cannot be tokenized.
    """
    tree = ast.parse(source)
    string_lines = collect_string_lines(source)
    lines = source.splitlines()
    violations: dict[int, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        last_line = node.end_lineno or node.body[-1].lineno
        for line_number in range(statement_start_line(node.body[0]), last_line + 1):
            if line_number in string_lines or lines[line_number - 1].strip():
                continue
            violations[line_number] = node.name
    return sorted(violations.items())


def main(filenames: Sequence[str]) -> int:
    """Check files and print every forbidden empty line.

    Parameters
    ----------
    filenames : Sequence[str]
        Paths of Python files to check.

    Returns
    -------
    int
        0 if all files are clean, 1 otherwise.
    """
    exit_code = 0
    for filename in filenames:
        source = Path(filename).read_text(encoding="utf-8")
        try:
            violations = find_empty_lines(source)
        except (SyntaxError, tokenize.TokenError) as error:
            print(f"{filename}: cannot parse file: {error}")
            exit_code = 1
            continue
        for line_number, function_name in violations:
            print(f"{filename}:{line_number}: empty line in function '{function_name}'")
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
