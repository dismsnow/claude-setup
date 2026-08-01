# WebView Hardening

**Impact: HIGH** — a WebView runs remote code inside your app's process.

**Classification:** ADOPT GOING FORWARD for new code. A WebView loading untrusted content with file access or an unguarded message bridge is **SHIP-BLOCKING** — report it.

## Quick Pattern

**Incorrect (unrestricted):**

```tsx
<WebView
  source={{ uri: userSuppliedUrl }}
  allowFileAccess
  allowUniversalAccessFromFileURLs
  onMessage={(e) => handleCommand(JSON.parse(e.nativeEvent.data))}
/>
```

Any page that ends up loaded — via redirect, injected link, or a compromised third party — can read local files and issue commands to your native handler.

**Correct (contained):**

```tsx
<WebView
  source={{ uri: 'https://app.example.com/help' }}
  originWhitelist={['https://app.example.com']}
  // Defaults are the safe values — do not enable these.
  allowFileAccess={false}
  allowFileAccessFromFileURLs={false}
  allowUniversalAccessFromFileURLs={false}
  javaScriptCanOpenWindowsAutomatically={false}
  setSupportMultipleWindows={false}
  onShouldStartLoadWithRequest={(req) => req.url.startsWith('https://app.example.com')}
  onMessage={(e) => {
    // Treat every message as hostile input.
    const msg = parseMessage(e.nativeEvent.data); // validates shape; returns null if invalid
    if (!msg) return;
    handleCommand(msg);
  }}
/>
```

## The threat model

A WebView is a browser with your app's privileges and none of a browser's UI cues. The risks, in order:

1. **Navigation drift.** A page you trust redirects somewhere you don't. `originWhitelist` alone does not stop every case — `onShouldStartLoadWithRequest` lets you reject per navigation.
2. **The message bridge.** `onMessage` / `postMessage` is an RPC channel from web content into native code. Whatever it can call, remote JavaScript can call.
3. **Local file access.** With file access enabled, page JavaScript can read the app's data directory — including any plaintext local database (`security-token-storage.md`).
4. **Credential exposure.** Tokens injected into the page, or placed in the URL, are visible to the page and its network requests.

## Settings that matter

| Setting | Safe value | Why |
|---|---|---|
| `originWhitelist` | Explicit HTTPS origins | Never `['*']` |
| `allowFileAccess` | `false` | Blocks reading app-local files |
| `allowFileAccessFromFileURLs` | `false` | Blocks `file://` reading other files |
| `allowUniversalAccessFromFileURLs` | `false` | Blocks `file://` reaching any origin — the worst combination |
| `onShouldStartLoadWithRequest` | Allow-list check | Per-navigation control |
| `javaScriptEnabled` | `false` if the content doesn't need it | Removes the whole class |
| `setSupportMultipleWindows` | `false` unless needed | Prevents popup-driven navigation |
| `mixedContentMode` | Never `'always'` | Prevents HTTP content on an HTTPS page |
| `incognito` / cache | Consider `true` for auth flows | Avoids leaving session data behind |

## Deep Dive: the message bridge is an API

Anything reachable via `onMessage` is effectively a public API exposed to whatever page is loaded. Design it accordingly:

- **Validate every message** — shape, type, and allowed action. Never `JSON.parse` and dispatch on an arbitrary `type` field.
- **Expose the narrowest possible surface.** A `closeModal` message is fine. A generic `callNative(method, args)` handler is a remote-code-execution primitive.
- **Never expose token retrieval or storage access** over the bridge.
- **Check the origin** where the platform provides it, and re-verify with `onShouldStartLoadWithRequest` so only your origin is ever loaded.

`injectedJavaScript` runs in the page context — so anything you inject is readable by the page. Never inject a token, and be aware that injected code is subject to the page's own scripts.

## Deep Dive: never render untrusted HTML

Loading remote HTML from user content, an email body, or an API response into a privileged WebView means executing someone else's script with your app's WebView privileges.

If you must display rich remote content:

- Render it in a WebView with `javaScriptEnabled={false}`, no bridge, and no file access, **or**
- Sanitize server-side and render with native components instead.

An in-app browser component is the right tool for opening arbitrary external URLs — it's designed for untrusted content and keeps it outside your app's WebView context.

## Common Pitfalls

- **`originWhitelist={['*']}`** — the most common and most consequential misconfiguration.
- **Enabling file access** for one local-file feature, opening local-database reads.
- **A generic bridge handler** that dispatches arbitrary native calls by name.
- **Tokens in the WebView URL**, which land in server logs, history, and referrers.
- **Injecting a token via `injectedJavaScript`**, handing it to the page.
- **Assuming HTTPS is sufficient.** It protects transport, not the page's behaviour.
- **Using a WebView to open external links** rather than an in-app browser.

## Related

- `security-deep-links.md` — the other untrusted-URL entry point
- `security-token-storage.md` — what file access exposes
- `security-network-tls.md` — transport-level settings

---
Verified against: `react-native-webview` prop names as of Aug 2026, Expo SDK 54.
Prop names and defaults vary by WebView library version — verify against the installed package's types.
