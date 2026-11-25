Task Tracker API
Objective: to develop an API for a task tracker featuring projects, participants, assignees and comments.

Mandatory functionality
Registration, login and personal profile in accordance with the joint technical specifications. Creating a project designates the author as its owner; other participants have the role of ‘member’ within that project.
POST/GET /projects, GET/PATCH/DELETE /projects/{id}. Users can only view projects of which they are members; only the owner can edit or delete a project.

Only the owner can add and remove participants via /projects/{id}/members using the ID of an already registered user. Duplicates are not permitted; the owner cannot remove themselves without deleting the project.

Tasks: POST/GET /projects/{id}/tasks, GET/PATCH/DELETE /tasks/{id}. Fields: title (1–150 characters), description, status (todo/in_progress/done), priority (low/medium/high), assignee_id or null, due_at or null.
Each participant can create, view, edit and delete tasks in their project. Only the current participant can be the assignee. When a participant is deleted, their tasks remain with `assignee_id = null`.
List of tasks: filters by `status`, `priority`, `assignee_id` and overdue status; pagination and sorting by `created_at`/`id`. Overdue task: `due_at` < current time and `status` != `done`; time values are in the timezone, stored in UTC.

Comments: POST/GET `/tasks/{id}/comments`; PATCH/DELETE `/comments/{id}` only for the author, who remains a member. Non-members cannot view the project, tasks or comments.
Data and rules

Entities: User, Project, Membership, Task, Comment. The project/user pair is unique. Deleting a project cascades the deletion of memberships, tasks and comments. Deleting the owner’s account when they have their own projects returns a 409; the projects must be deleted first. Permission checks are performed for every access to a nested resource.
