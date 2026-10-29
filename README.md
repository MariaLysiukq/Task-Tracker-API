<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&height=180&color=0:1e3a8a,100:0ea5e9&text=Task%20Tracker%20API&fontColor=ffffff&fontSize=44&fontAlignY=35&animation=fadeIn" alt="Task Tracker API" width="100%" />

<a href="https://github.com/MariaLysiukq/Task-Tracker-API">
  <img src="https://readme-typing-svg.demolab.com?font=Fira+Code&size=18&duration=3000&pause=800&color=0EA5E9&center=true&vCenter=true&width=600&lines=Projects%2C+members%2C+tasks+and+comments;Async+FastAPI+%2B+SQLAlchemy+%2B+PostgreSQL;JWT+auth+with+role-based+access" alt="Typing animation" />
</a>

[![CI](https://github.com/MariaLysiukq/Task-Tracker-API/actions/workflows/ci.yml/badge.svg)](https://github.com/MariaLysiukq/Task-Tracker-API/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Neon-4169E1?logo=postgresql&logoColor=white)
![Ruff](https://img.shields.io/badge/lint-ruff-D7FF64?logo=ruff&logoColor=black)
![mypy](https://img.shields.io/badge/types-mypy%20strict-2A6DB2)

</div>

A REST API for team task tracking. Users create projects, invite members, assign tasks
with status, priority and due dates, and discuss them in comments. Every nested
resource is permission-checked, so teams never see each other's data.

<!-- Screenshot: Swagger UI overview (save as docs/screenshots/swagger.png) -->
<p align="center">
  <img src="docs/screenshots/swagger.png" alt="Swagger UI with all endpoints" width="800" />
</p>

## Contents

- [Features](#features)
- [Tech stack](#tech-stack)
- [Getting started](#getting-started)
- [Usage](#usage)
- [API overview](#api-overview)
- [Testing and quality](#testing-and-quality)
- [Project structure](#project-structure)
- [Contributing](#contributing)
- [License](#license)
- [Authors and acknowledgements](#authors-and-acknowledgements)

## Features

- Registration, login (JWT bearer token) and personal profile
- Projects with an `owner` and `member` roles; only the owner edits, deletes and manages members
- Tasks with `status` (todo / in_progress / done), `priority` (low / medium / high), assignee and `due_at`
- Filters by `status`, `priority`, `assignee_id` and `overdue`; sorting by `created_at` or `id`
- Pagination on every list: `limit` (1-100, default 20) and `offset`
- Comments editable and deletable only by their author
- Cascading deletes; removed members' tasks stay with `assignee_id = null`
- Passwords stored as Argon2 hashes; all timestamps are timezone-aware UTC

## Tech stack

| Layer      | Tools                                                  |
|------------|--------------------------------------------------------|
| Web        | FastAPI, Pydantic v2, Uvicorn                          |
| Database   | PostgreSQL (Neon), SQLAlchemy 2.0 async, asyncpg       |
| Migrations | Alembic                                                |
| Security   | PyJWT, pwdlib (Argon2)                                 |
| Quality    | pytest, Ruff, mypy --strict, Gitleaks, pre-commit      |
| Delivery   | Docker, Docker Compose, GitHub Actions                 |

## Getting started

### Prerequisites

- Python 3.12
- A PostgreSQL database
- Docker (optional, for containers and the local test database)

### Installation

```bash
git clone https://github.com/MariaLysiukq/Task-Tracker-API.git
cd Task-Tracker-API
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

### Configuration

Copy the template and fill in your own values.

```bash
cp .env.example .env
```

| Variable             | Description                                       | Default |
|----------------------|---------------------------------------------------|---------|
| `DATABASE_URL`       | Async URL, `postgresql+asyncpg://...?ssl=require` | -       |
| `JWT_SECRET`         | Secret key used to sign tokens                    | -       |
| `JWT_ALGORITHM`      | Token signing algorithm                           | `HS256` |
| `JWT_EXPIRE_MINUTES` | Token lifetime in minutes                         | `30`    |
| `TEST_DATABASE_URL`  | Separate database for tests (optional)            | SQLite in memory |

### Run locally

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

### Run with Docker

```bash
docker compose up --build
```

The container applies migrations on start. The API is available at
<http://localhost:8000>, interactive docs at <http://localhost:8000/docs>.

## Usage

A short session with `curl`:

```bash
# 1. Register
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "ann@example.com", "password": "strongpass1", "full_name": "Ann"}'

# 2. Log in and keep the token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "ann@example.com", "password": "strongpass1"}' | jq -r .access_token)

# 3. Create a project
curl -X POST http://localhost:8000/api/v1/projects \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name": "Website relaunch"}'

# 4. List overdue high-priority tasks
curl "http://localhost:8000/api/v1/projects/1/tasks?priority=high&overdue=true&limit=10" \
  -H "Authorization: Bearer $TOKEN"
```

<!-- Screenshot: a request and response in Swagger UI (save as docs/screenshots/request.png) -->
<p align="center">
  <img src="docs/screenshots/request.png" alt="Creating a task in Swagger UI" width="800" />
</p>

## API overview

All routes use the `/api/v1` prefix and, except registration and login, require
`Authorization: Bearer <token>`.

<details>
<summary><b>Endpoints</b></summary>

| Method                | Path                                  | Access          |
|-----------------------|---------------------------------------|-----------------|
| POST                  | `/auth/register`                      | Public          |
| POST                  | `/auth/login`                         | Public          |
| GET / PATCH / DELETE  | `/users/me`                           | Self            |
| POST / GET            | `/projects`                           | Any user / members |
| GET                   | `/projects/{id}`                      | Members         |
| PATCH / DELETE        | `/projects/{id}`                      | Owner           |
| GET                   | `/projects/{id}/members`              | Members         |
| POST                  | `/projects/{id}/members`              | Owner           |
| DELETE                | `/projects/{id}/members/{user_id}`    | Owner           |
| POST / GET            | `/projects/{id}/tasks`                | Members         |
| GET / PATCH / DELETE  | `/tasks/{id}`                         | Members         |
| POST / GET            | `/tasks/{id}/comments`                | Members         |
| PATCH / DELETE        | `/comments/{id}`                      | Author (member) |

</details>

<details>
<summary><b>Status codes</b></summary>

| Code | Meaning                                                          |
|------|------------------------------------------------------------------|
| 201  | Resource created                                                 |
| 200  | Read or update succeeded                                         |
| 204  | Resource deleted                                                 |
| 401  | Missing or invalid token                                         |
| 403  | Authenticated, but not allowed (for example a member editing a project) |
| 404  | Not found, or not visible to you                                 |
| 409  | Conflict (duplicate email or member, owner deleting account with projects) |
| 422  | Invalid input                                                    |

</details>

## Testing and quality

Tests use in-memory SQLite by default and never touch the main database.
To run them against PostgreSQL, start the local test container:

```bash
docker compose --profile test up -d test-db
pytest --cov                     # uses TEST_DATABASE_URL if set
pre-commit run --all-files       # Ruff, mypy --strict, Gitleaks, empty-line check
```
CI runs the same hooks, the test suite (coverage gate 80%) and a Docker build on every push.

## Project structure

```text
app/
├── api/v1/         # Routers (HTTP layer)
├── services/       # Business rules
├── repositories/   # Database queries
├── models/         # SQLAlchemy models
├── schemas/        # Pydantic schemas
├── core/           # Config, database, security, errors
└── _detail/        # Constants and helpers
alembic/            # Migrations
scripts/            # Custom pre-commit hooks
tests/
├── unit/
└── integration/
```

## Contributing

1. Create a branch from `main`.
2. Make the change and add tests.
3. Make sure `pre-commit run --all-files` and `pytest` pass.
4. Open a pull request with a short description of the change.

Bug reports and ideas are welcome in [Issues](https://github.com/MariaLysiukq/Task-Tracker-API/issues).

## Authors and acknowledgements

- **Maria Lysiuk** - [@MariaLysiukq](https://github.com/MariaLysiukq)

Built as the final project of the Python Backend course. AI assistance during
development is documented in [`docs/ai-log.md`](docs/ai-log.md).

<img src="https://capsule-render.vercel.app/api?type=waving&height=100&color=0:0ea5e9,100:1e3a8a&section=footer" alt="" width="100%" />
