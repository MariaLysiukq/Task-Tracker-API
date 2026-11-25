Trigger: When the user asks to write tests for a feature, or immediately after a feature is completed.
Action: Do NOT write trivial tests that are guaranteed to pass.
Write integration tests in tests/integration/ for the endpoint.
The tests MUST check for the expected successful response AND all applicable error states defined in the project: 401 (unauthenticated), 403 (unauthorized/no rights), 404 (not found), 409 (conflict), and 422 (invalid data).
Write unit tests in tests/unit/ for complex business rules in services and helpers.
Automatically execute pytest in the terminal to verify the tests actually run. Read the output. If tests fail unexpectedly, debug them before presenting the final result.
