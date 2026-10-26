Trigger: When the user asks to fix linting errors, or when a pre-commit hook fails during execution.Action:Run pre-commit run --all-files to identify errors.   
Automatically fix Ruff linting and formatting errors.   
Check the custom AST/tokenize local hook in scripts/ to ensure there are absolutely no empty lines between instructions in function bodies (unless it's a docstring or multiline string).   
Fix any typing issues flagged by mypy --strict.   
NEVER alter the core business logic while fixing these hooks.
