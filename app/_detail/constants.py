"""Business limits shared by schemas, services and tests."""

EMAIL_MAX_LENGTH = 320
USER_FULL_NAME_MAX_LENGTH = 100
PASSWORD_HASH_MAX_LENGTH = 255
PROJECT_NAME_MAX_LENGTH = 100
TASK_TITLE_MAX_LENGTH = 150
COMMENT_BODY_MAX_LENGTH = 2000
PAGE_LIMIT_DEFAULT = 20
PAGE_LIMIT_MAX = 100
DESCRIPTION_MAX_LENGTH = 5000
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128
# RFC 7518 §3.2: an HS256 key must be at least as long as the hash output (32 bytes).
JWT_SECRET_MIN_LENGTH = 32
# Per client IP, separately for login and for registration.
AUTH_RATE_LIMIT_REQUESTS = 5
AUTH_RATE_LIMIT_WINDOW_SECONDS = 60
# Upper bound on clients tracked by one limiter, so memory cannot grow without limit.
RATE_LIMIT_MAX_TRACKED_KEYS = 10_000
