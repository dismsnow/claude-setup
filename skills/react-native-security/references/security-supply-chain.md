# Dependency and Build Supply Chain

**Impact: MEDIUM-HIGH** — dependencies and config plugins run code on developer machines and in CI.

**Classification:** ADOPT GOING FORWARD for new code. A credential committed to the repository is **SHIP-BLOCKING** — report it; the credential must be treated as compromised and rotated, which the owner sequences.

## The part people miss

In a React Native / Expo project, dependencies don't just ship code to users — **config plugins execute arbitrary Node code at build time**, on every developer machine and in CI, with the privileges of whoever runs the build. A malicious or compromised plugin can read environment variables (including your signing credentials and CI secrets), modify generated native code, and exfiltrate anything it finds.

So a dependency's blast radius is two things:

1. **Runtime** — code shipped inside your app.
2. **Build time** — code run in your build environment, with access to your secrets.

The second is usually the more valuable target, and it's the one that gets less scrutiny.

## Quick Commands

```bash
# Known vulnerabilities
npm audit --production
npx osv-scanner --lockfile=package-lock.json   # or yarn.lock / pnpm-lock.yaml

# What runs code at install time
npm query ":attr(scripts, [postinstall])" 2>/dev/null

# What config plugins execute at build time (each is build-time code you own)
npx expo config --type public | grep -A30 '"plugins"'

# Credentials accidentally committed
git grep -nE "(api[-_]?key|secret|password|token)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}" -- ':!*.lock'
git config --get remote.origin.url    # must not contain a token
```

## Evaluating a new dependency

Before adding one, especially one with native code or a config plugin:

| Check | Concern |
|---|---|
| Recent commits and releases | Unmaintained native modules block SDK upgrades and don't get security fixes |
| Download counts vs. name similarity to a popular package | Typosquatting |
| Does it ship a config plugin? | Build-time code execution — read what it does |
| Does it have install scripts? | Code execution at `npm install` |
| Transitive dependency count | Each one is more surface |
| Does it request permissions? | A library that adds a permission changes your store declarations |
| Does it duplicate something you have? | More surface for no benefit |

For anything security-relevant (crypto, auth, storage, networking), prefer well-maintained, widely-used libraries. **Never hand-roll cryptography** — use the platform's or a vetted library's primitives.

## Lockfile and version discipline

- **Commit the lockfile.** It's the record of exactly what was installed.
- **Use `npm ci`** (or the equivalent) in CI so builds install from the lockfile and cannot silently drift.
- **Review lockfile diffs.** An unexpected transitive change in an unrelated PR is worth a question.
- **Keep one version of each dependency** across a monorepo; duplicate versions mean one may be the unpatched one.
- **Update deliberately, on a schedule.** Both never-updating and blind-auto-updating are risks; the first accumulates known vulnerabilities, the second adopts compromised releases quickly.

## Patches and plugins are code you own

Patch-based native modifications (`patch-project`, patch-package, and similar) and custom config plugins are unreviewed code in your build:

- **Review every patch on creation and on every upgrade.** A patch that silently stops applying, or applies to different code after an SDK bump, is a correctness *and* security issue.
- **Each patch needs an owner and a reason**, recorded. An unexplained patch nobody understands never gets removed.
- **Config plugins should be as small as possible** and fail loudly rather than silently no-op — see `prebuild-config-plugin-authoring.md`.

## Deep Dive: credentials in repository config

A frequent, easy-to-miss leak is a credential embedded in git configuration rather than in code — most commonly a personal access token inside a remote URL:

```bash
git config --get remote.origin.url    # https://<token>@github.com/org/repo.git
```

This is dangerous because:

- It doesn't appear in code searches or secret scanners that only scan tracked files.
- It's printed by routine commands (`git remote -v`), so it leaks into shared terminal output, screenshots, and logs.
- It typically carries broad account-level scope.

Use a credential helper or SSH keys instead. If one is present, treat the token as compromised — printed once in a shared log is enough — and rotate it. Take care not to echo the remote while investigating.

## Common Pitfalls

- **Auditing runtime dependencies but not build-time plugins**, which have access to your secrets.
- **Adding a dependency for one small utility**, importing its whole tree.
- **Never running `npm audit`**, or running it and never acting.
- **`npm install` in CI instead of `npm ci`**, allowing drift from the lockfile.
- **Unreviewed patches** carried across SDK upgrades.
- **Hand-rolled crypto.**
- **A token in the git remote URL** — invisible to code scanners, visible in terminal output.
- **Auto-merging dependency updates** with no review window.

## Related

- `security-secrets-and-config.md` — build-time secret handling
- `security-ota-code-signing.md` — the update pipeline as supply chain
- `prebuild-config-plugin-authoring.md` in `react-native-best-practices` — writing plugins that fail loudly
- `bundle-library-size.md` in `react-native-best-practices` — the size side of dependency evaluation

---
Verified against: Expo SDK 54, React Native 0.81 (Aug 2026).
Tooling flags (`npm audit`, `osv-scanner`, `npm query`) change between versions — check `--help` before relying on a specific invocation.
