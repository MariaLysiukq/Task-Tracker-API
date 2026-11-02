Trigger: When the user asks to build a new feature, endpoint, or business logic.
Action: Do NOT write the entire feature at once.
You must implement the vertical slice strictly in the following order, waiting for the user to review and approve before moving to the next step:
Models & Migrations: Update SQLAlchemy models in app/models/ and generate the Alembic migration. Ask for review.
Schemas: Create the Pydantic schemas for requests/responses in app/schemas/. Ask for review.   Database Access: Write the database queries in app/repositories/. Ask for review.
Business Logic: Write the business rules in app/services/. Ask for review.
API Router: Wire the endpoint in app/api/ using the /api/v1 prefix. Ensure status codes (200, 201, 204) are correct. Ask for final review.
