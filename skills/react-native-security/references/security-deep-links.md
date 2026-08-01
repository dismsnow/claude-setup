# Deep Links and Push Payloads as Untrusted Input

**Impact: HIGH** — a link is attacker-controlled input that navigates straight into your app.

**Classification:** ADOPT GOING FORWARD for new code. A deep link that performs a privileged action from link parameters alone is **SHIP-BLOCKING** — report it.

## Quick Pattern

**Incorrect (trusts the link):**

```tsx
// myapp://invoice/approve?id=4821
function ApproveInvoice() {
  const { id } = useLocalSearchParams();
  useEffect(() => {
    approveInvoice(id); // acts on an attacker-supplied id, with no check
  }, [id]);
}
```

Any app or web page can open `myapp://invoice/approve?id=<anything>`. This turns a link into an unauthenticated command.

**Correct (validate, authorize, and require intent):**

```tsx
function ApproveInvoice() {
  const { id } = useLocalSearchParams();
  const invoiceId = typeof id === 'string' && /^\d+$/.test(id) ? id : null;

  if (!invoiceId) return <InvalidLink />;
  // The screen loads data; the server authorizes; the user confirms.
  return <InvoiceApprovalScreen invoiceId={invoiceId} />;
}
```

Three separate requirements:

1. **Validate the shape** — never pass a raw param into a query, a file path, or a URL.
2. **Authorize server-side** — the server decides whether *this user* may act on *this record*. A link proves nothing about authorization.
3. **Require explicit intent** for anything destructive or privileged. A link should navigate, not execute.

## Custom schemes are not exclusive

Any app can register `myapp://`. On Android, multiple apps claiming the same scheme produce a chooser; on iOS the resolution is undefined for duplicates. So a custom scheme:

- **cannot** authenticate the sender,
- **cannot** guarantee your app receives its own links,
- **can** be registered by a malicious app to intercept them.

This matters most for OAuth-style flows: a code or token delivered to a custom scheme can land in another app. Prefer verified links.

| Mechanism | Hijackable? | Notes |
|---|---|---|
| Custom scheme (`myapp://`) | **Yes** | Convenient; no ownership proof |
| Android App Links (`autoVerify`) | No | Verified via a file on your HTTPS domain |
| iOS Universal Links | No | Verified via an association file on your domain |

Verified links require domain ownership, which is exactly the property that makes them trustworthy. Use them for anything sensitive, and keep the custom scheme only as a development or fallback path.

## Push payloads have the same shape

A push notification's data payload is also input that arrives from outside and often drives navigation. Validate it the same way. Additionally:

- Don't put sensitive content in the notification body — it renders on the lock screen.
- Don't trust a payload-supplied ID as authorization; re-fetch and let the server authorize.
- Treat a payload field used to build a URL or path as hostile (see path traversal below).

## Deep Dive: Android component exposure

A deep link entry point implies an exported Android component. Two things to check:

- **Don't export more than you need.** A component with an intent filter is reachable by other apps. Anything not intended as an entry point should not be exported.
- **Don't accept privileged intents from anywhere.** If another app can send an intent that triggers an action, that action needs the same validation and authorization as a link.

Also validate any param that becomes a path or URL:

```ts
// Path traversal / open redirect via link params
const target = params.next;                 // "../../etc/passwd" or "https://evil.example"
if (!ALLOWED_ROUTES.includes(target)) return <InvalidLink />;
```

Allow-list, don't sanitize. A denylist of bad patterns is always incomplete.

## Step-by-step for a new link

1. Decide whether the route may be triggered by an untrusted party. If not, it shouldn't be linkable.
2. Validate every parameter's type and shape at the entry point.
3. Confirm the server authorizes the action for the current user — independently of the link.
4. Require a confirmation step for destructive or privileged actions.
5. Use verified links (App Links / Universal Links) for anything sensitive.
6. Test with a hostile link: wrong types, missing params, traversal strings, IDs belonging to another user.

## Common Pitfalls

- **Executing on mount** from link params — the core mistake.
- **Trusting an ID because the link "came from our email".** You cannot verify that.
- **Custom scheme for OAuth redirects**, allowing another app to intercept the code.
- **Reusing link params in file paths or URLs** without an allow-list.
- **Sensitive data in push bodies**, visible on the lock screen.
- **Over-exporting Android components** so internal screens become externally reachable.

## Related

- `security-webview.md` — the other place untrusted URLs land
- `security-permissions.md` — Android component and manifest configuration
- `ts-runtime-validation-boundaries.md` in `typescript-performance` — the validation pattern
- `prebuild-config-plugin-authoring.md` in `react-native-best-practices` — editing the manifest correctly

---
Verified against: Expo SDK 54, React Native 0.81 (Aug 2026).
App Links / Universal Links setup requirements change with platform versions — verify against current platform docs.
