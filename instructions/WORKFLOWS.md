# Workflow Patterns
## Multi-Agent AI Orchestration System

**Version:** 1.0.0  
**Related:** `PRD.md`, `AGENTS.md`, `PROMPTS.md`

---

## 1. Pattern: Parallel Research (Fan-Out)

**Use Case:** Gather information on multiple topics simultaneously.

**User Prompt:**
```
Research these three topics in parallel:
1. Best auth libraries for Node.js 2026
2. PostgreSQL connection pooling patterns
3. Docker multi-stage build optimization

Return a synthesized summary with recommendations.
```

**Internal Execution:**
```
Orchestrator (plan)
├──→ delegate_task(
│      role: researcher,
│      model: research,
│      task: "Research best auth libraries for Node.js 2026...",
│      timeout: 180s
│    )
├──→ delegate_task(
│      role: researcher,
│      model: research,
│      task: "Research PostgreSQL connection pooling patterns...",
│      timeout: 180s
│    )  [CONCURRENT]
└──→ delegate_task(
       role: researcher,
       model: research,
       task: "Research Docker multi-stage build optimization...",
       timeout: 180s
     )  [CONCURRENT]

←── All 3 complete
Orchestrator synthesizes results
```

**Expected Output:**
```markdown
## Research Summary

### 1. Auth Libraries for Node.js
**Top Pick:** `jose` (42KB, ESM-native, audited)
**Runner-up:** `jsonwebtoken` (89KB, mature)

### 2. PostgreSQL Connection Pooling
**Pattern:** Use `pg-pool` with max 20 connections per instance.
**Anti-pattern:** Creating new clients per request.

### 3. Docker Multi-Stage Builds
**Best Practice:** Separate `deps`, `build`, and `runtime` stages.
**Savings:** ~70% image size reduction.

**Sources:** [jose npm](...), [pg-pool docs](...), [Docker docs](...)
```

**Cost Estimate:** ~$0.05 (3 × research tasks)
**Time Estimate:** ~20s (parallel) vs ~60s (sequential)

---

## 2. Pattern: Build Pipeline (Nested Orchestration)

**Use Case:** Build a complete feature with planning, implementation, and verification.

**User Prompt:**
```
Build a user authentication module with:
- JWT token generation
- Password hashing with bcrypt
- Login/logout endpoints
- Unit tests

Use the Planner for architecture, then parallel Builders, then Executor for tests.
```

**Internal Execution:**
```
Orchestrator (plan)
├──→ Planner (plan, role=orch)
│      ├──→ Analyzes existing codebase
│      ├──→ Creates task DAG:
│      │      T1: JWT utility (independent)
│      │      T2: Bcrypt helper (independent)
│      │      T3: Endpoints (depends on T1, T2)
│      │      T4: Tests (depends on T3)
│      └──→ Returns plan
│
├──→ Builder-JWT (code, role=leaf)
│      └──→ write_file(src/auth/jwt.ts)
│
├──→ Builder-Bcrypt (code, role=leaf)  [CONCURRENT with JWT]
│      └──→ write_file(src/auth/bcrypt.ts)
│
├──→ Builder-Endpoints (code, role=leaf)  [WAITS for JWT + Bcrypt]
│      └──→ write_file(src/auth/endpoints.ts)
│
├──→ Builder-Tests (code, role=leaf)  [WAITS for Endpoints]
│      └──→ write_file(tests/auth.test.ts)
│
└──→ Executor (code, role=leaf)  [WAITS for all Builders]
       └──→ terminal_tool("npm test")
       └──→ Report: 4/4 passed

←── Orchestrator synthesizes final report
```

**Expected Output:**
```markdown
## ✅ Auth Module Built

### Files Created
- `src/auth/jwt.ts` (45 lines) — JWT generation & validation
- `src/auth/bcrypt.ts` (28 lines) — Password hashing
- `src/auth/endpoints.ts` (62 lines) — Login/logout routes
- `tests/auth.test.ts` (38 lines) — Unit tests

### Test Results
- **Total:** 4 tests
- **Passed:** 4 ✅
- **Failed:** 0
- **Duration:** 2.1s

### Next Steps
- Add refresh token rotation
- Add rate limiting middleware
```

**Cost Estimate:** ~$0.40 (1 plan + 4 builds + 1 execute)
**Time Estimate:** ~45s (parallel build) vs ~120s (sequential)

---

## 3. Pattern: Refactor & Modernize (Path-Scoped Parallelism)

**Use Case:** Update multiple independent files simultaneously.

**User Prompt:**
```
Refactor all utility files in src/utils/ to use ES modules instead of CommonJS.
```

**Internal Execution:**
```
Orchestrator (plan)
├──→ Search files: src/utils/*.js
│
├──→ Path Analysis (Hermes internal):
│      file1.js → file1.mjs (no overlap)
│      file2.js → file2.mjs (no overlap)
│      file3.js → file3.mjs (no overlap)
│      → All paths independent → PARALLEL SAFE
│
├──→ Builder-File1 (code)  [CONCURRENT]
│      └──→ patch(file1.js): module.exports → export default
│
├──→ Builder-File2 (code)  [CONCURRENT]
│      └──→ patch(file2.js): require → import
│
├──→ Builder-File3 (code)  [CONCURRENT]
│      └──→ patch(file3.js): module.exports → export default
│
└──→ Executor (code)
       └──→ terminal_tool("npm test")
       └──→ Report: All tests pass
```

**Path Overlap Detection:**
```python
# Hermes internal logic
file1_path = "src/utils/file1.js"
file2_path = "src/utils/file2.js"
file3_path = "src/utils/file3.js"

# No overlap → all 3 Builders run in parallel
# If file1 and file2 both write to "src/utils/index.js":
#   → Overlap detected → sequential queue
```

**Expected Output:**
```markdown
## ✅ Refactor Complete

### Files Modified
- `src/utils/file1.js` → `src/utils/file1.mjs`
- `src/utils/file2.js` → `src/utils/file2.mjs`
- `src/utils/file3.js` → `src/utils/file3.mjs`

### Changes Applied
- `module.exports` → `export default`
- `require()` → `import`
- `__dirname` → `import.meta.dirname`

### Verification
- **Lint:** ✅ Pass
- **Tests:** ✅ Pass (12/12)
- **Build:** ✅ Pass
```

**Cost Estimate:** ~$0.15 (1 search + 3 parallel patches + 1 execute)
**Time Estimate:** ~25s (parallel) vs ~70s (sequential)

---

## 4. Pattern: Debug & Fix (Diagnostic → Fix → Verify)

**Use Case:** Identify and fix a bug with systematic diagnosis.

**User Prompt:**
```
The login endpoint returns 500 errors. Find the bug and fix it.
```

**Internal Execution:**
```
Orchestrator (plan)
├──→ Researcher (research)
│      ├──→ read_file(src/auth/endpoints.ts)
│      ├──→ read_file(src/auth/jwt.ts)
│      ├──→ search_files("throw", "src/auth/")
│      └──→ Returns: "Possible null reference in jwt.ts line 34"
│
├──→ Builder (code)  [WAITS for Researcher]
│      ├──→ read_file(src/auth/jwt.ts)
│      ├──→ patch(jwt.ts): Add null check
│      └──→ Returns: "Fixed null reference, added test case"
│
└──→ Executor (code)  [WAITS for Builder]
       ├──→ terminal_tool("npm test")
       ├──→ terminal_tool("npm run test:auth")
       └──→ Report: "All auth tests pass, including new null check test"

←── Orchestrator presents diagnosis + fix
```

**Expected Output:**
```markdown
## 🐛 Bug Fixed: Login 500 Error

### Root Cause
Null reference in `src/auth/jwt.ts:34` — `payload.sub` was undefined when token was malformed.

### Fix Applied
```typescript
// Before
const userId = payload.sub;

// After
const userId = payload?.sub;
if (!userId) {
  throw new AuthError("INVALID_TOKEN", "Token missing subject claim");
}
```

### Test Added
- `tests/auth.test.ts`: "should reject token without sub claim"

### Verification
- **Before fix:** 1 failing test (500 error)
- **After fix:** 0 failing tests ✅
```

**Cost Estimate:** ~$0.20 (1 research + 1 build + 1 execute)
**Time Estimate:** ~30s

---

## 5. Pattern: Documentation Generation (Research → Draft → Review)

**Use Case:** Generate comprehensive documentation for a codebase.

**User Prompt:**
```
Generate API documentation for the entire src/ directory.
```

**Internal Execution:**
```
Orchestrator (plan)
├──→ Planner (plan)
│      ├──→ Scans src/ structure
│      ├──→ Identifies modules: auth, users, orders, payments
│      └──→ Returns: "Generate docs for 4 modules in parallel"
│
├──→ Researcher-Auth (research)  [CONCURRENT]
│      └──→ Extract JSDoc + types from src/auth/
│
├──→ Researcher-Users (research)  [CONCURRENT]
│      └──→ Extract JSDoc + types from src/users/
│
├──→ Researcher-Orders (research)  [CONCURRENT]
│      └──→ Extract JSDoc + types from src/orders/
│
├──→ Researcher-Payments (research)  [CONCURRENT]
│      └──→ Extract JSDoc + types from src/payments/
│
├──→ Builder-Docs (code)  [WAITS for all Researchers]
│      ├──→ write_file(docs/api.md)
│      ├──→ write_file(docs/auth.md)
│      ├──→ write_file(docs/users.md)
│      └──→ write_file(docs/orders.md)
│      └──→ write_file(docs/payments.md)
│
└──→ Executor (code)
       └──→ terminal_tool("npx markdownlint docs/*.md")
       └──→ Report: "No lint errors"

←── Orchestrator presents doc index
```

**Expected Output:**
```markdown
## 📚 API Documentation Generated

### Files Created
- `docs/api.md` — Overview and getting started
- `docs/auth.md` — Authentication endpoints
- `docs/users.md` — User management endpoints
- `docs/orders.md` — Order processing endpoints
- `docs/payments.md` — Payment handling endpoints

### Statistics
- **Total endpoints documented:** 24
- **Code examples:** 18
- **Type definitions:** 42

### Quality Checks
- **Markdown lint:** ✅ Pass
- **Link validation:** ✅ All internal links valid
```

**Cost Estimate:** ~$0.60 (1 plan + 4 research + 1 build + 1 execute)
**Time Estimate:** ~60s (parallel research) vs ~180s (sequential)

---

## 6. Pattern: Dependency Update (Research → Plan → Execute)

**Use Case:** Update all npm dependencies safely.

**User Prompt:**
```
Update all dependencies to their latest versions and verify nothing breaks.
```

**Internal Execution:**
```
Orchestrator (plan)
├──→ Researcher (research)
│      ├──→ terminal_tool("npm outdated --json")
│      ├──→ web_search("breaking changes express 5")
│      ├──→ web_search("breaking changes typescript 5.6")
│      └──→ Returns: "3 major updates with breaking changes flagged"
│
├──→ Planner (plan)  [WAITS for Researcher]
│      ├──→ Analyzes breaking changes
│      ├──→ Creates migration plan per package
│      └──→ Returns: "Update in order: types → core → frameworks"
│
├──→ Executor-Update (code)  [WAITS for Planner]
│      ├──→ terminal_tool("npm update")
│      ├──→ terminal_tool("npm audit fix")
│      └──→ Returns: "Updated 12 packages, 0 vulnerabilities"
│
└──→ Executor-Verify (code)  [WAITS for Update]
       ├──→ terminal_tool("npm run build")
       ├──→ terminal_tool("npm test")
       └──→ Report: "Build pass, 2 tests failed (expected breaking changes)"

←── Orchestrator presents update report + failed test analysis
```

**Expected Output:**
```markdown
## 📦 Dependency Update Report

### Updated Packages
| Package | Old | New | Breaking Changes |
|---|---|---|---|
| express | 4.18.0 | 5.0.0 | Yes (router changes) |
| typescript | 5.5.0 | 5.6.0 | No |
| jest | 29.0.0 | 30.0.0 | Yes (snapshot format) |

### Test Results
- **Before update:** 45/45 pass
- **After update:** 43/45 pass
- **Failures:**
  1. `router.test.ts` — Express 5 route matching change
  2. `snapshot.test.ts` — Jest 30 snapshot format

### Recommended Actions
1. Fix router test (Builder task)
2. Update snapshots (Executor task: `npm test -- -u`)
```

**Cost Estimate:** ~$0.30 (1 research + 1 plan + 2 execute)
**Time Estimate:** ~90s (includes npm install time)

---

## 7. Workflow Selection Guide

| User Intent | Pattern | Agents Spawned | Models Used |
|---|---|---|---|
| "Find info about X, Y, Z" | Parallel Research | 1-3 Researchers | research |
| "Build feature X" | Build Pipeline | 1 Planner + 2-4 Builders + 1 Executor | plan, code |
| "Update all files like X" | Refactor & Modernize | 2-5 Builders + 1 Executor | code |
| "Fix the bug" | Debug & Fix | 1 Researcher + 1 Builder + 1 Executor | research, code |
| "Write docs" | Documentation Generation | 1 Planner + 2-4 Researchers + 1 Builder | plan, research, code |
| "Update dependencies" | Dependency Update | 1 Researcher + 1 Planner + 2 Executors | research, plan, code |

---

## 8. Change Log

| Version | Date | Changes |
|---|---|---|
| 1.0.0 | 2026-07-31 | Initial workflow patterns: 6 canonical workflows |
