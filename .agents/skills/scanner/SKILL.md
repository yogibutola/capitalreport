---
name: angular-security-scanner
description: >
  Scan modern Angular (v14+) source code for security vulnerabilities. Use this
  skill whenever the user wants to audit, review, or check Angular code for
  security issues — even if they only say "check my Angular code", "is this safe?",
  "review for security", or "find bugs in my Angular app". Covers XSS via DomSanitizer,
  improper innerHTML binding, route guard bypasses, sensitive data in Signals/state,
  and insecure storage. Produces a structured report with severity ratings and
  fix guidance. Trigger even if the user only uploads or pastes a snippet.
---

# Modern Angular Security Scanner

Systematically scans modern Angular (v14+) code for security vulnerabilities, rates
their severity, and provides actionable remediation guidance.

---

## Workflow

### Step 1 — Collect the code

If the user has uploaded files, read them from `/mnt/user-data/uploads/`. For pasted
snippets, work directly from the conversation. If a directory is given, read every `.ts` and `.html` file that contains Angular patterns (look for `@Component`, `signal`, `inject`, `DomSanitizer`, `[innerHTML]`, etc.).

For large codebases, process files in logical groups (components, services, guards) and aggregate findings at the end.

### Step 2 — Run the vulnerability checklist

Work through **all categories** in the [Vulnerability Checklist](#vulnerability-checklist)
below. For each finding, record:

- **ID** — sequential number (V-01, V-02 …)
- **Category** — from the checklist
- **Severity** — Critical / High / Medium / Low / Informational
- **File & line** — exact location (or "snippet" if no filename given)
- **Vulnerable code** — the exact offending excerpt (keep it short)
- **Description** — why it is dangerous
- **Remediation** — concrete fix, ideally with a corrected code example

### Step 3 — Produce the report

Output a structured Markdown report using the [Report Template](#report-template).
Always include an executive summary with a count per severity level, even if no
findings exist. End with a prioritized fix list.

---

## Vulnerability Checklist

Work through every category. Skip none — if a category has no findings, note "None
found" internally and move on (do not clutter the report with empty sections).

### 1. DomSanitizer Misuse (CRITICAL)

Angular's `DomSanitizer` is used to intentionally bypass security checks. If user input reaches these methods without proper backend sanitization, it leads directly to XSS.

Look for:
- `bypassSecurityTrustHtml(userInput)`
- `bypassSecurityTrustScript(userInput)`
- `bypassSecurityTrustStyle(userInput)`
- `bypassSecurityTrustUrl(userInput)`
- `bypassSecurityTrustResourceUrl(userInput)`

Remediation: Never use `bypassSecurityTrustHtml` on untrusted data. Use Angular's default interpolation `{{ }}` which auto-escapes, or ensure data is sanitized server-side before bypassing.

---

### 2. innerHTML Binding (HIGH)

Binding to `[innerHTML]` allows rendering raw HTML. While Angular strips out `<script>` tags automatically, it does not strip all dangerous vectors (like `<img src=x onerror=alert(1)>`).

Look for:
- `[innerHTML]="userInput"`
- `[outerHTML]="userInput"`
- Using `Renderer2.setProperty(el, 'innerHTML', userInput)`

Remediation: Ensure inputs are strictly validated or passed through a robust sanitizer (like DOMPurify) before being bound to `innerHTML`.

---

### 3. Direct DOM Manipulation (MEDIUM)

Angular explicitly warns against direct DOM manipulation because it bypasses the framework's built-in XSS protections.

Look for:
- `ElementRef.nativeElement.innerHTML = userInput`
- Using `document.getElementById` or `document.querySelector` to set values directly.
- Over-reliance on `Renderer2` to dynamically build executable strings.

Remediation: Use Angular's templating engine (interpolation `{{ }}`, property binding `[prop]`, and control flow `@if` / `@for`) instead of direct DOM manipulation.

---

### 4. Route Guard Bypasses (MEDIUM-HIGH)

Modern Angular relies on functional route guards (`canActivate`, `canMatch`). Flaws here can expose restricted areas.

Look for:
- Functional guards that read auth state directly from `localStorage` without validating the JWT signature.
- Guards that return `true` immediately if an API fails, instead of defaulting to a deny/redirect state.
- Parent routes with missing guards, assuming child routes are protected (or vice versa).

---

### 5. Sensitive Data Exposure in State/Signals (MEDIUM)

Angular DevTools and browser extensions can easily inspect the component tree and state management tools (Signals, NgRx, BehaviorSubjects).

Look for:
- Storing plaintext passwords, API keys, or full credit card details in a `signal()`.
- Services that hold onto PII indefinitely without clearing it on logout.
- `console.log()` calls that dump entire user or auth objects into the browser console.

---

### 6. CSRF (Cross-Site Request Forgery) (HIGH)

Angular's `HttpClient` has built-in CSRF protection (`HttpClientXsrfModule`), but it must be configured and respected by the backend.

Look for:
- State-changing requests (`POST`, `PUT`, `DELETE`) made without ensuring a CSRF token is attached.
- `withCredentials: true` being used universally without strict CORS policies on the backend.
- Custom interceptors that inadvertently strip out the `X-XSRF-TOKEN` header.

---

### 7. Insecure Storage (MEDIUM)

Storing sensitive authentication artifacts in easily accessible client-side storage.

Look for:
- `localStorage.setItem('token', jwt)` — susceptible to theft via XSS.
- `sessionStorage` containing sensitive session state.

Remediation: Auth tokens (JWTs/session IDs) should ideally be stored in `HttpOnly`, `Secure`, `SameSite` cookies set by the backend, not in `localStorage`.

---

### 8. Outdated Dependencies (LOW-MEDIUM)

Using heavily outdated versions of Angular or vulnerable third-party libraries (like older versions of RxJS or Zone.js).

Look for:
- Flag if the Angular version is out of LTS (Long Term Support).
- Highlight specific libraries known for prototype pollution or RCE if found in `package.json`.

---

## Report Template

```
# Angular Security Scan Report

**Scanned:** <file(s) or "pasted snippet">
**Date:** <today>
**Scanner:** Antigravity Angular Security Skill

---

## Executive Summary

| Severity     | Count |
|-------------|-------|
| Critical    |       |
| High        |       |
| Medium      |       |
| Low         |       |
| Information |       |
| **Total**   |       |

<1–3 sentence plain-English summary of the most important findings.>

---

## Findings

### V-01 — <Short Title> [SEVERITY]

| Field | Value |
|---|---|
| **Category** | <checklist category> |
| **File / Line** | `filename.ts:42` |
| **Severity** | Critical / High / Medium / Low |

**Vulnerable code:**
\```typescript
// offending snippet here
\```

**Why it's dangerous:**
<plain explanation, 2–4 sentences>

**Remediation:**
\```typescript
// corrected code here
\```

---
<repeat for each finding>

---

## Prioritized Fix List

1. [V-XX] Fix first (Critical/High) — one-line description
2. …

```

---

## Severity Rating Guide

| Rating | Criteria |
|---|---|
| **Critical** | `DomSanitizer` bypasses leading directly to XSS. |
| **High** | Improper `[innerHTML]` binding, CSRF vulnerabilities, missing route guards on admin sections. |
| **Medium** | Direct DOM manipulation, sensitive data in `localStorage` or Signals, minor auth bypasses. |
| **Low** | Missing security headers (if verifiable), defense-in-depth gaps. |
| **Informational** | Deviations from Angular style guide, use of outdated (but not immediately exploitable) dependencies. |
