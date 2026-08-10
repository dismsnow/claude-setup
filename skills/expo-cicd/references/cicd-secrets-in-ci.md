# Secrets and Credentials in CI

**This file answers "which store carries this value to the build".** Whether a value is safe to ship inside the app at all is a different question, owned by `react-native-security` — read that first if you are unsure. Everything shipped in the binary is readable by anyone with the app, and no CI configuration changes that.

## The headline rule

> **`EXPO_TOKEN` is the only secret your CI provider needs.**

Keystores, App Store Connect keys, Play service accounts and build-time API keys all live in EAS. If your GitHub or GitLab secret list is growing, something is in the wrong place.

## Where each value goes

| Value | Destination | How |
|---|---|---|
| EAS authentication | **CI provider secret** | `EXPO_TOKEN` |
| Build-time value the JS bundle needs (API base URL, public key) | **EAS environment variable** | `eas env:set --visibility plaintext` or `sensitive` |
| Build-time file (`google-services.json`, `GoogleService-Info.plist`, service account JSON) | **EAS file variable** | `eas env:set --type file` |
| Signing keystore / distribution certificate | **EAS-managed credentials** | `eas credentials` |
| Store API credentials (ASC key, Play service account) | **EAS**, referenced from the `submit` profile | upload once |
| A real secret the app needs at runtime (user tokens, private API keys) | **Your server** | never in the app |
| Anything you were about to hardcode "temporarily" | **Nowhere** | see `react-native-security` |

The last two rows matter most. A value that reaches the app's JavaScript is not a secret, no matter which store it passed through on the way. EAS "secret" visibility protects the value in logs and in the dashboard — it does not protect it once it is inlined into your bundle. Expo's own docs say so plainly: secrets "do not provide any additional security for values that you end up embedding in your application itself".

## `EXPO_TOKEN`

Create at **expo.dev → Account settings → Access tokens**.

| Token type | Use for |
|---|---|
| Personal access token | your own machine, quick experiments |
| **Robot user** (Organization → Access tokens) | **anything shared or long-lived** |

Prefer a Robot user for CI. A personal token can act on everything you own across every project; a Robot user is scoped to the organization's resources, cannot sign in to Expo products, and can be revoked without disrupting you. If someone leaves the team, you revoke a robot rather than auditing what a personal token could reach.

```sh
gh secret set EXPO_TOKEN                 # GitHub
# GitLab: Settings → CI/CD → Variables, marked Masked + Protected
```

`EXPO_TOKEN` takes precedence over any stored login, so a runner with it set is authenticated for every `eas` command without an interactive step.

## EAS environment variables

Three environments — `development`, `preview`, `production` — and three visibility levels:

| Visibility | Readable on the website | Readable via CLI | In build logs |
|---|---|---|---|
| `plaintext` | yes | yes | yes |
| `sensitive` | behind a toggle | yes | obfuscated |
| `secret` | **no** | **no** | obfuscated |

A build profile picks its environment with the `environment` field:

```json
{ "build": { "live": { "environment": "production" } } }
```

### Commands

```sh
eas env:set --name API_URL --value https://api.example.com \
  --environment production --visibility plaintext

eas env:set --name GOOGLE_MAPS_API_KEY --value "…" \
  --environment preview --environment production --visibility sensitive

eas env:set --name GOOGLE_SERVICES_JSON --type file --value ./google-services.json \
  --environment production --visibility secret

eas env:list production --include-sensitive
eas env:pull production --path .env.local       # populate a local dev env
eas env:exec production 'npx some-command'      # run a command with them loaded
eas env:delete production --variable-name OLD_KEY
```

`eas env:set` creates or updates — it replaced the older `eas env:create`, which is no longer in the CLI reference. The legacy `eas secret:*` commands still exist in older material; prefer `env:*`.

### File-type variables

A `--type file` variable is written to a path **outside the project directory** on the build runner, and the environment variable holds that path. So `google-services.json` never needs to be in your repository:

```json
{
  "expo": {
    "android": { "googleServicesFile": "$GOOGLE_SERVICES_JSON" }
  }
}
```

This is the fix for the very common pattern of committing `google-services.json` "because the build needs it". The build does need it; the repository does not.

### `env` in `eas.json` vs EAS environment variables

| | `eas.json` `env` | EAS environment variables |
|---|---|---|
| Stored | committed in the repo | on EAS servers |
| Scope | one build profile | an environment, across profiles |
| Secret-capable | **no** — it is in git | yes |
| Good for | `ENVIRONMENT=uat` and similar non-secret switches | anything you would not paste into a PR |

Both are visible to the config evaluation, and they can disagree. See [cicd-release-matrix.md](cicd-release-matrix.md) Part 2 — the resolution order is the source of the worst mapping bug in this whole skill.

## Signing credentials

The question that settles this: **can a machine that is not yours produce a signed build?** If the answer is no, CI cannot either.

| Approach | Where the keystore lives | Use when |
|---|---|---|
| **EAS-managed** (default) | EAS, generated and stored for you | almost always |
| Self-managed | `credentials.json` + local files | you have an existing keystore you must keep, or policy requires custody |

```sh
eas credentials                      # inspect, upload, or rotate
```

**A keystore that exists only in one person's working directory is not a credential strategy.** It is gitignored (correctly), undocumented, and unrecoverable if that machine dies — Android signing keys cannot be regenerated, and losing one means you cannot update the app on Play, ever. Migrating it into EAS-managed credentials is worth doing before any CI work, not after.

## Store submission credentials

**iOS** — an App Store Connect API key (`.p8`) is strongly preferred over an Apple ID and app-specific password: it does not carry a human's 2FA, and it does not break when someone changes their password.

```json
{
  "submit": {
    "live": {
      "ios": {
        "ascAppId": "1234567890",
        "appleTeamId": "AB12XYZ34S"
      }
    }
  }
}
```

Upload the `.p8` to EAS with `eas credentials` rather than referencing `ascApiKeyPath` in a repo — a `.p8` in version control is a full submission credential in plaintext.

For unattended iOS credential handling, EAS reads `EXPO_ASC_API_KEY_PATH`, `EXPO_ASC_KEY_ID`, `EXPO_ASC_ISSUER_ID`, `EXPO_APPLE_TEAM_ID`, `EXPO_APPLE_TEAM_TYPE`.

**Android** — a Play Console service account JSON, uploaded to EAS. Grant it only the release permissions it needs; a service account with full account access is a much larger blast radius than "can upload builds".

## Auditing an existing repo

Before wiring CI to a project that has been built by hand:

```sh
git config --get remote.origin.url            # a token in here? rotate it
git ls-files | grep -Ei 'google-services|GoogleService-Info|\.p8$|\.jks$|\.keystore$|service-account'
ls *.jks *.keystore 2>/dev/null                # loose credentials in the working tree
grep -rn "EXPO_PUBLIC_" --include=*.ts --include=*.tsx . | head
```

**Report what you find; do not silently fix it.** Rotating a key can break production, and rewriting history breaks everyone's clone. The owner needs to sequence it. That handling rule comes from `react-native-security` and applies here unchanged — the only thing this file adds is that some of these findings genuinely block CI and belong on the Level 1 checklist in [ADOPTION.md](../ADOPTION.md).

One finding is worth acting on immediately regardless: **a token embedded in `.git/config`'s remote URL**. It sits in plaintext, it is copied with the repo, it is read by anything that inspects the project, and CI has no use for it. Treat it as compromised, rotate it, and switch the remote to SSH or a credential helper.

## Related

- `react-native-security` — whether a value is a secret at all, and OTA code signing
- [cicd-release-matrix.md](cicd-release-matrix.md) — how `environment` and `env` resolve during a build
- [cicd-runner-recipes.md](cicd-runner-recipes.md) — where `EXPO_TOKEN` is consumed