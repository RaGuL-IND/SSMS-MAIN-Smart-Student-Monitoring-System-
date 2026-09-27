# SSMS Login Flow Analysis

## Current Architecture

### Frontend (React + TypeScript)
**Entry Point:** `Frontend/src/main.tsx`
- Renders `LoginPage` component from `files/src/types/LoginPage.tsx`
- Component displays: 3 role tabs (Student, Company, Admin) + unified login form

**Login Component:** `Frontend/files/src/types/LoginPage.tsx`
- Collects: role, identifier (register no / email / username), password
- Calls API: `login()` from `src/api/auth.ts`
- API endpoint: `POST /api/auth/login`

**API Handler:** `Frontend/src/api/auth.ts`
```typescript
API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ""  // Defaults to empty = relative paths
POST /api/auth/login
```

---

### Backend (Flask + SQLAlchemy)
**Main App:** `app_new.py`
```
Route /  or /login          → Serves React dist/index.html (if built) OR main_portal.html
Route /admin                → admin_bp (OLD HTML-based routes)
Route /student              → student_bp (OLD HTML-based routes)
Route /company              → company_bp (OLD HTML-based routes)
Route /api/auth/*           → api_auth_bp (NEW JSON API for React)
```

**New API Endpoint:** `blueprints/api_auth.py`
```
POST /api/auth/login         → Routes by role (admin/student/company)
GET  /api/auth/me            → Check session status
POST /api/auth/logout        → Clear session
```

**Login Logic per Role:**

1. **Admin:** `_login_admin(username, password)`
   - Uses: `verify_admin()` from `utils.py`
   - Sets: `session["role"] = "admin"`, `session["admin_user"] = username`
   - Returns: `{"success": true, "redirectUrl": "/admin/dashboard"}`

2. **Student:** `_login_student(register_number, password)`
   - Queries: `Student` model from `models.py`
   - Matches: `Student.register_number` + `Student.password` (plain text vs DEFAULT_STUDENT_PASSWORD = "helloeveryone")
   - Sets: `session["role"] = "student"`, `session["student_reg_no"] = register_number`
   - Returns: `{"success": true, "redirectUrl": "/student/dashboard", "mustResetPassword": true/false}`

3. **Company:** `_login_company(email, password)`
   - Queries: `CompanyHR` model from `models.py`
   - Matches: `CompanyHR.email` + password hash check with `check_password_hash()`
   - Sets: `session["role"] = "company"`, `session["company_email"]`, `session["company_name"]`, `session["hr_name"]`
   - Returns: `{"success": true, "redirectUrl": "/company/dashboard"}`

---

## Suspected Issues

### ❌ Problem 1: Session Keys May Not Match
The `@login_required` or role decorators in existing blueprints may be looking for different session keys than what the API sets.

**Action:** Check `auth_decorators.py` and see what session keys the decorators expect:
```python
# Example — find these actual checks in auth_decorators.py:
def student_required(f):
    # Does it check for session["student_reg_no"] or session["student_id"] or something else?
```

### ❌ Problem 2: React App Not Bundling Correctly
The build may have failed silently or not included the LoginPage component.

**Check:**
- Does `Frontend/dist/index.html` exist? ✅ YES
- Does `Frontend/dist/assets/` have JS/CSS files? ✅ YES (seen in terminal output)

### ❌ Problem 3: API Request Failing
The React fetch might be hitting an error. Check:
- Is `/api/auth/login` being called?
- Is the response being parsed correctly?
- Is the redirectUrl being followed?

### ❌ Problem 4: Old Flask Routes Still Active
If someone visits `/admin/login`, `/student/login`, or `/company/login` directly, they get the old HTML templates.

**Current behavior:**
```
GET  /admin/login          → admin_bp.login() → render_template("login.html")  ← OLD HTML
GET  /student/login        → ??? (need to check student_bp)
GET  /company/login        → ??? (need to check company_bp)
```

**These OLD routes should NOT exist anymore or should redirect to React app.**

---

## Complete Login Flow (Intended)

```
1. User navigates to http://localhost:5000/
   ↓
2. app_new.py route "/" serves Frontend/dist/index.html
   ↓
3. React app loads LoginPage component
   ↓
4. User selects role (Student/Company/Admin)
   ↓
5. User enters credentials → clicks LOGIN
   ↓
6. LoginPage.handleSubmit() calls login() function
   ↓
7. Fetch POST to /api/auth/login with:
   {
     "role": "student|company|admin",
     "identifier": "register_no|email|username",
     "password": "...",
     "remember": true|false
   }
   ↓
8. api_auth_bp routes to _login_admin/student/company()
   ↓
9. If credentials valid:
   - Sets session["role"]
   - Sets role-specific session keys
   - Returns: {"success": true, "redirectUrl": "/student/dashboard"}
   ↓
10. React receives response → window.location.href = redirectUrl
   ↓
11. Browser navigates to /student/dashboard (or /admin/dashboard, etc.)
   ↓
12. Old Flask route (e.g., student_bp.dashboard()) renders template
   ↓
13. User sees dashboard
```

---

## What Might Be Going Wrong

### Scenario A: React fetch error not caught
If the API returns an error (e.g., 401, 500), the React component should display an error message. But if there's a server error or CORS issue, the fetch might fail completely.

**Check:** Open browser DevTools → Network tab → POST /api/auth/login → see response

### Scenario B: Old routes interfering
If the React app is trying to redirect to `/student/login` instead of `/student/dashboard`, it hits the old Flask login page.

**Check:** In api_auth_bp, are the redirectUrl values correct? Should be `/student/dashboard`, not `/student/login`.

### Scenario C: Session keys mismatch
API sets `session["student_reg_no"]`, but the dashboard route checks for `session["student_id"]` → throws 401 → redirects to login → shows old login.html

**Check:** Run decorator checks against session keys set by the API.

---

## Recommended Fixes

### Fix 1: Redirect old routes to React
In `blueprints/admin.py`, `student.py`, `company.py`, change the login routes:

```python
@admin_bp.route("/", methods=["GET"])
@admin_bp.route("/login", methods=["GET"])
def login():
    if "admin_user" in session:
        return redirect(url_for("admin.dashboard"))
    # Don't render login.html — redirect to React app
    return redirect("/")  # or return render_template() for old form if you want to support both
```

### Fix 2: Remove `/login` routes from blueprints entirely
Delete the login route from each blueprint and let the React app handle all login UX.

### Fix 3: Verify session keys in decorators
Make sure `auth_decorators.py` checks for the EXACT keys that `api_auth_bp` sets.

### Fix 4: Test API directly
```bash
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"role":"admin","identifier":"admin_username","password":"admin_password"}'
```

Should return:
```json
{"success": true, "redirectUrl": "/admin/dashboard"}
```

---

## Session Verification

**Current session keys set by api_auth_bp:**
- Admin: `session["role"]="admin"`, `session["admin_user"]=username`
- Student: `session["role"]="student"`, `session["student_reg_no"]=register_number`
- Company: `session["role"]="company"`, `session["company_email"]=email`, `session["company_name"]=company_name`, `session["hr_name"]=hr_name`

**Need to verify:** Do the decorators in `auth_decorators.py` check these exact keys?

---

## File Structure
- Frontend React: `/Frontend/src/` (dev), `/Frontend/dist/` (built)
- Backend API: `/blueprints/api_auth.py` (NEW JSON API)
- Backend UI: `/blueprints/admin.py`, `/student.py`, `/company.py` (OLD HTML routes)
- Shared: `/models.py` (SQLAlchemy), `/utils.py`, `/auth_decorators.py`

