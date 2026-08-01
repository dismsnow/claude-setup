# Logs, Crash Reports, and Data Leaks

**Impact: MEDIUM-HIGH** — correctly-stored secrets routinely escape through telemetry.

**Classification:** ADOPT GOING FORWARD for new code. Tokens or PII being sent to a third-party crash/analytics service is **SHIP-BLOCKING** — report it, since it may carry disclosure obligations.

## The core fact

**`console.log` is not removed from release builds by default.** Statements remain in the shipped bundle and their output is readable on a connected device. A `console.log(response)` that helped during development ships as a token disclosure.

Worse, crash and analytics SDKs capture breadcrumbs automatically — often including console output, network metadata, and state snapshots — and transmit them to a third party where they persist in someone else's database.

## Quick Pattern

**Incorrect:**

```ts
console.log('Auth response:', response);        // token in the log
console.log('User:', user);                     // PII in the log
Sentry.setContext('session', { token });        // token sent to a third party
fetch(`/api/items?token=${token}`);             // token in URL: server logs, referrers
```

**Correct:**

```ts
if (__DEV__) console.log('Auth ok for user id:', user.id); // dev only, no secret
Sentry.setUser({ id: user.id });                            // identifier, not PII
fetch('/api/items', { headers: { Authorization: `Bearer ${token}` } }); // header, not URL
```

## Step 1: Strip console output from release builds

```js
// babel.config.js
module.exports = function (api) {
  api.cache(true);
  return {
    presets: ['babel-preset-expo'],
    env: {
      production: {
        plugins: ['transform-remove-console'],
      },
    },
  };
};
```

This removes `console.*` calls from production bundles — a size win as well as a disclosure fix. Keep `console.error` if your crash reporter depends on it, by configuring the plugin's `exclude` option.

Guarding with `__DEV__` is the complementary habit: it makes intent explicit and lets the bundler drop the branch.

## Step 2: Decide what telemetry may carry

| Data | Send to third-party telemetry? |
|---|---|
| User ID / account ID | Yes — needed to correlate |
| Screen name, app version, OS | Yes |
| Auth tokens, refresh tokens, keys | **Never** |
| Passwords, PINs | **Never** |
| Email, phone, full name, address | Only with a lawful basis and a scrubbing policy |
| Full API request/response bodies | **No** — they contain everything above |
| Location coordinates | Only if the feature requires it and it's disclosed |

The default configuration of many SDKs is more inclusive than this table. Configure explicitly rather than accepting defaults.

## Step 3: Redact at the boundary

Put redaction in one place — the error reporter's hook — so it can't be forgotten at a call site:

```ts
const SENSITIVE = /(authorization|token|password|secret|refresh|cookie)/i;

function redact(obj: Record<string, unknown>) {
  return Object.fromEntries(
    Object.entries(obj).map(([k, v]) => [k, SENSITIVE.test(k) ? '[redacted]' : v])
  );
}

Sentry.init({
  beforeSend(event) {
    if (event.request?.headers) event.request.headers = redact(event.request.headers);
    return event;
  },
});
```

A key-name pattern catches the common cases. It is not complete — a token inside a free-text error message won't match — which is why not logging the value in the first place matters more than redaction.

## Deep Dive: the less obvious channels

- **Tokens in URLs.** Query strings land in server access logs, proxy logs, and analytics. Use headers.
- **Error messages that embed the request.** `throw new Error(\`Failed: ${JSON.stringify(config)}\`)` ships the auth header into the crash report.
- **Redux/state-snapshot middleware** in crash reporters, which serializes the entire store — including tokens held in state.
- **Screenshots attached to bug reports**, capturing on-screen personal data.
- **Verbose network logging interceptors** left enabled in release.
- **Unhandled promise rejections** printing whole response objects.

## Common Pitfalls

- **Assuming release builds strip `console.log`.** They don't without the plugin.
- **Logging the whole response object** during debugging and shipping it.
- **Accepting a crash SDK's default capture settings.**
- **Tokens in query strings**, the most persistent of these leaks.
- **Relying on redaction alone.** It's a safety net, not the control.
- **Sending PII to telemetry with no lawful basis or retention policy** — a compliance problem, not just a security one.

## Related

- `security-secrets-and-config.md` — secrets in the bundle, the other disclosure path
- `security-token-storage.md` — storing the token correctly, then logging it
- `security-permissions.md` — declaring what data you collect
- `bundle-analyze-js.md` in `react-native-best-practices` — console stripping is also a size win

---
Verified against: Expo SDK 54, React Native 0.81, `babel-preset-expo` (Aug 2026).
`babel-plugin-transform-remove-console` is a separate dependency — confirm it's installed before relying on the config above.
