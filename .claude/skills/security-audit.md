Trigger: When the user asks to check the project for security holes, run a security audit, or review it for typical vulnerabilities.
Rule: Do not change anything until the user has seen the report.

STAGE 1 — AUDIT. Go through the list. For each item write: problem found / no problem / not applicable, the file and line, and the severity (critical / medium / minor).
2. Real API keys in frontend code.
3. Row Level Security disabled in the database, or access to other users' records is otherwise not restricted.
4. Access rights checked only on the frontend, not on the server.
5. No rate limiting on endpoints.
6. SQL queries built by string concatenation instead of parameters.
7. No validation of incoming data on the server.
8. User text inserted into a page as raw HTML.
9. Passwords stored in plain text or with a weak hash.
10. Auth tokens stored in localStorage.
11. Admin or service pages available without authorization.
12. CORS set to `*`.
13. Email not confirmed on registration.
14. Predictable IDs (1, 2, 3) with no check that the object belongs to the current user.
15. Update endpoints write the whole request body to the database.
16. Webhooks accepted without signature verification.
17. Stack traces and detailed error messages returned in production.
18. Outdated dependencies with known vulnerabilities.
19. No password strength check and no check against breach databases.
20. File uploads without checks on type, size and name.

STAGE 2 — PLAN. Sort the findings by severity and show the proposed fix for each. Wait for the user's "go".

STAGE 3 — EDITS. Fix one item at a time, each as a separate commit with a clear message. After each edit, check that the application starts and the main scripts and tests pass (see "Check commands" in AGENTS.md).

STAGE 4 — WHAT CANNOT BE FIXED IN CODE. Write a separate list. Example: keys that already leaked into git must be revoked and reissued by hand; name exactly which keys and where this is done.

Important: do not report a problem you have not seen in the code. If you did not find something or could not check it, say so.
