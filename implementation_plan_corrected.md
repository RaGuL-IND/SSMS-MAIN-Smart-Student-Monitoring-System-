# Implementation Plan: Company Management → Placement Cell Control Center
### (Corrected against verified schema — read this before executing)

## Why this version differs from the earlier draft

The original plan referenced `Drive.test_file` and `Drive.aptitude_test_link` as
database model attributes, and a `placement_status` field on students. **None of
these exist.** The real `Drive` model (confirmed from `blueprints/company.py`)
has exactly these fields:

```
drive_id, hr_email, company_name, position, package, time_period,
number_required, min_cgpa, domain_required, description, mode,
location, end_date, created_at
```

Test-round links (`aptitude_test_link`, `domain_test_link`, `coding_test_link`,
and their `*_duration` counterparts) exist **only as columns in
`data/company_drives.csv`** — the DB sync path in `company.py` never reads or
writes them. Treat them as CSV-only fields throughout this plan. Do not add
them to `models.py` — that's a schema migration with its own risk, out of
scope here.

There is also no `placement_status` field anywhere in `Student`. If "already
placed" filtering is wanted, it needs a real design decision first (see
Section 4) — don't invent the field silently.

## ⚠️ Critical constraint — read before touching student.py

`blueprints/student.py`'s `student_current_drives()` and its template
(`templates/student_current_drives.html`) key every test-taking route by
**positional row index** (`drive_index`), via Jinja's `loop.index0`. That
index also signs the HMAC proctor token and is the join key in
`test_results.csv`.

**Rule: never filter, sort, or reorder the drives DataFrame before passing
it to this template.** Any restriction on which drives a student sees must
be done by adding a boolean column (e.g. `is_assigned`) to each row and
hiding non-visible rows with `{% if row.is_assigned %}` around the `<tr>` in
the template — this leaves `loop.index0` counting every iteration exactly as
it does today, hidden or not. Reordering, `.sort_values()`, or dropping rows
before render **will silently corrupt exam results** by desynchronizing
`drive_index` from the row a student actually sees. If any change to this
route doesn't obviously preserve row order, stop and flag it rather than
proceeding.

---

## 1. Backend: `blueprints/api_CompanyManagement.py`

### Remove
- `POST ""` (create drive), `PUT /<int:drive_id>` (update), `DELETE /<int:drive_id>`
  — drives originate only from the Company Portal, never Admin.

### Add: sidecar helpers
```python
ASSIGNMENTS_JSON = os.path.join(BASE_DIR, "data", "drive_assignments.json")
# Format: { "<drive_id>": { "<register_number>": { "status": "approved"|"rejected",
#           "assigned_at": ..., "assigned_by": ... } } }

def load_assignments(): ...  # read JSON, {} if missing/corrupt
def save_assignments(assignments): ...  # write JSON
```
Use this exact filename and shape — it's what `student.py`'s gate (Section 3)
reads. Don't introduce a second file (`drive_allocations.json`) for the same
concept.

### Add: `GET /drives/<int:drive_id>/eligible-students`
Real, verified filters only:
- `CGPA >= drive.min_cgpa` (both fields confirmed real)
- Optional: `Department` match against `drive.domain_required` — confirm
  with the person building this whether domain_required is meant to match
  Student.Department exactly, or something looser (they're free-text
  strings on both sides, not a controlled vocabulary, so exact match may
  under-return results)
- Sort by `skill_index` descending (real field, confirmed via `models.py`)
- Do NOT add a `placement_status` filter — field doesn't exist (see Section 4)

Response includes each eligible student's current assignment status from
the sidecar (`pending` if no record yet).

### Add: `POST /drives/<int:drive_id>/assign`
Body: `{ register_number, status: "approved"|"rejected" }`. Writes to the
sidecar. This is the single source of truth the student-side gate reads.

### Add: `GET /available-tests`
Scans `data/tests/*.csv` (the directory `student.py`'s `read_test_file()`
already reads from) and returns filenames — this is genuinely new, no
existing route lists them, but it's a safe, read-only addition.

### Add: `POST /drives/<int:drive_id>/assign-test`
Body: `{ round: "aptitude"|"domain"|"coding", filename, duration }`. Writes
directly to `data/company_drives.csv`, setting `{round}_test_link` to
`internal:{filename}` and `{round}_duration` — matching exactly the format
`student.py`'s `start_test_round()` already expects. **CSV only — do not
attempt to write these fields to the `Drive` DB model, they don't exist
there.**

---

## 2. Backend: `blueprints/company.py`

### Modify `company_dashboard()`
Read `data/drive_assignments.json`, and for each of the HR's own drives
(filtered by `hr_email == session["company_email"]`, exactly as today),
attach the list of approved candidates. Read-only addition — no change to
`load_drives()`/`save_drives()`.

---

## 3. Backend: `blueprints/student.py`

### Modify `student_current_drives()`
Add an `is_assigned` boolean per row from `drive_assignments.json`, matched
by `drive_id` (present in `load_company_drives()`'s output) and
`session["student_reg_no"]`. **Preserve row order and count exactly as
today** — see the constraint at the top of this document. Pass an
`any_assigned` boolean to the template alongside `drives`, so the "no
drives available" message still shows correctly when every row is hidden.

### Modify `templates/student_current_drives.html`
Wrap the existing `<tr>...</tr>` block in `{% if row.is_assigned %}`.
Replace the `{% if drives.empty %}` empty-state check with
`{% if not any_assigned %}`. No other changes — the `loop.index0`-based
`url_for()` call stays untouched.

---

## 4. Explicitly deferred — do not implement without a separate decision

- **`placement_status` (Unplaced/Available/Placed)** — no such field exists.
  Implementing this means either (a) adding a new column to `Student` (a
  real schema migration, needs its own review), or (b) deriving it as a
  proxy from `drive_assignments.json` (e.g. "already approved for another
  drive with an overlapping timeline" — approximate, not a real placement
  record). Do not silently pick one; ask first.
- **Batch filter** — `Student.Batch` is real and could be added to the
  eligible-students filter trivially. Low risk, fine to include if wanted,
  but wasn't in the original ask — confirm before adding UI for it.

---

## 5. Frontend

### `src/api/CompanyManagement.ts`
- Remove `createDrive`, `updateDrive`, `deleteDrive`.
- Add: `getEligibleStudents(driveId)`, `assignStudent(driveId, regNo, status)`,
  `getAvailableTests()`, `assignTest(driveId, round, filename, duration)`.
- Match the REAL response shapes from Section 1 — don't invent field names
  before the backend exists; write the backend routes first, then the
  matching TS interfaces from their actual JSON output.

### `src/pages/CompanyManagement.tsx`
- Remove the Add Drive button, Edit (pencil) and Delete (trash) row actions.
- Keep View, Approve/Reject-the-drive-itself (the HR submission gate,
  separate concept from candidate assignment).
- Drive detail modal gains a new section: eligible students list, ranked,
  each with Approve/Reject buttons calling `assignStudent`. Show
  `selected count / drive.required` so the admin can see allocation
  progress against seats needed.
- Add a test-assignment dropdown (populated from `getAvailableTests()`) per
  round, calling `assignTest` on selection.

### `DriveFormModal.tsx`
Delete — no longer used once create/edit are removed from Admin.

---

## Guardrails for whoever executes this (Antigravity or otherwise)

This codebase has a documented history of a few specific failure modes —
watch for these while implementing:

1. **Duplicate/stale files.** Before editing any blueprint or page file,
   confirm there's exactly one copy in the project (`Get-ChildItem -Recurse
   -Filter "<filename>"` in PowerShell) — this project has repeatedly ended
   up with two versions of the same file (e.g. `api_student.py` vs
   `api_students.py`) where edits landed in the wrong one.
2. **Full-file replace, not partial patches**, when a file is being
   substantially restructured (like `CompanyManagement.tsx` here) — partial
   `str_replace`-style edits have caused import-path drift in this project
   before.
3. **Restart Flask after every backend change** — config/route changes
   need a process restart, not just a file save.
4. **`npm run build` after every frontend change**, and read the full
   output — this project's build has caught missing-file and wrong-import
   bugs before that would otherwise show as a silent blank page.
5. **Session/cookie behavior**: if any new route needs `@admin_required` or
   `@company_required`, confirm it checks the exact session keys already
   established (`session["admin_user"]`, `session["company_email"]`,
   `session["student_reg_no"]`) — this project hit a real bug earlier from
   a session-key mismatch between login and route protection.

## Verification Plan

1. Confirm `/api/company/drives` still returns correctly with Add/Edit/Delete
   removed (no regression to existing View functionality).
2. Call `eligible-students` for a real drive, confirm CGPA filtering and
   skill_index ordering are correct against known data.
3. Approve one student via `assign`, confirm `data/drive_assignments.json`
   is created/updated correctly.
4. **Log in as that student and confirm the drive now appears** — this is
   the one that must not be skipped.
5. **Have that student complete a full 3-round test end to end**, then
   check `test_results.csv` — confirm `drive_index` matches the correct
   drive. This is the test that catches a `loop.index0` regression; a
   passing UI does not guarantee this is correct.
6. Assign a test file via `assign-test`, confirm `company_drives.csv` gets
   the right `{round}_test_link` / `{round}_duration` values, and that an
   approved student can actually start that round.
