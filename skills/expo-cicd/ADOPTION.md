# Adopting CI/CD on an Existing Expo App

A staged path from "builds happen on one laptop" to "releases are automated". **Each level is independently valuable and independently shippable.** You can stop at any of them and be better off than before.

Most solo developers and small teams should stop at **Level 3**. Levels 4 and 4-OTA add real capability, but they also add the ability to break things at scale.

## The ladder

| Level | Name | What you gain | What it costs |
|---|---|---|---|
| **0** | Undocumented | — | — |
| **1** | Reproducible by hand | The build survives you being unavailable | 1–2 h, no secrets |
| **2** | PR gate | Broken code stops before review | ~1 h, free CI minutes |
| **3** | Automated internal distribution | Testers always have the latest build | ~2 h, EAS minutes per merge |
| **4** | Automated release | Release day is 30 minutes, not a day | ~4 h + credential setup |
| **4-OTA** | Hotfix without a store review | Same-day JS fixes | ~1 day + a full client re-build |

Two rules that make the ladder work:

- **Never skip Level 1.** Levels 2–4 automate the Level 1 commands. Automating a command nobody has written down produces a pipeline nobody can debug — when it fails at 6pm before a release, there is no known-good manual path to fall back to.
- **4-OTA is not "Level 5".** It is a branch off Level 4 with its own preconditions, and it is the only level that can break apps already installed on users' phones. Treat it as a separate project.

---

## Level 0 → 1: Reproducible by hand

**Goal:** someone who is not you can clone the repo and produce a UAT build without asking you a single question.

### Artifacts added

| Artifact | Why |
|---|---|
| A correct `eas.json` — every profile fills every column of the release matrix | The pipeline is a thin wrapper around these profiles. Wrong here, wrong everywhere. |
| `.nvmrc` + `"engines": { "node": ... }` in `package.json` | CI must use the Node version you use. Unpinned Node is the most common first-CI failure. |
| **One** lockfile, committed | Two lockfiles means CI and your laptop can install different trees. Pick npm or yarn, delete the other. |
| `.easignore` | See the warning below — this file has a footgun. |
| A real `projectId` in `extra.eas.projectId` | Without it `eas build` cannot run at all. Verify: `npx expo config --type public \| grep projectId` |
| A git remote that does not contain a token | See "prerequisites" below. |
| `RELEASE.md` — a ten-line table: environment → profile → channel → command → who can run it | This is the document Levels 2–4 automate. |

### The `.easignore` footgun

`.easignore` **replaces** `.gitignore` for the upload archive — the EAS CLI prioritises it over `.gitignore` rather than merging them. A naive three-line `.easignore` therefore starts uploading `node_modules`, build output, and any keystore sitting in your working tree.

Always start it as a copy of `.gitignore`, then add exclusions:

```bash
# .easignore — start by copying your entire .gitignore, then add:

# Native directories: EAS regenerates these with prebuild
/android
/ios

# Not needed to build
/docs
/coverage
/e2e
*.md
```

It supports `!` negation, which is the supported way to upload a file that is gitignored but needed by the build.

### Security prerequisites — report, do not silently fix

Some things must be resolved before CI touches a repo, but they are **not** CI work and should not be quietly rewritten. Handling is `react-native-security`'s territory: report with evidence and let the owner sequence the fix, because rotating a key can break production and rewriting history can break everyone's clone.

Check for these before Level 2:

| Finding | Why it blocks CI | Action |
|---|---|---|
| A token embedded in `.git/config`'s remote URL (`https://ghp_…@github.com/…`) | It is on disk in plaintext, it will be read by anything that inspects the repo, and CI does not need it | Treat as compromised: rotate it, then switch the remote to SSH or a credential helper |
| `google-services.json` / `GoogleService-Info.plist` committed | Should be an EAS file-type variable, not a repo file | Move to EAS; see [cicd-secrets-in-ci.md](references/cicd-secrets-in-ci.md) |
| A signing keystore that exists only in someone's working tree | CI cannot sign, and neither can anyone else if that laptop dies | Move to EAS-managed credentials, or document custody explicitly |
| A hardcoded API key in a source file | Ships readable in the bundle regardless of CI | `react-native-security` — this is not a CI problem |

**Ready for Level 2 when:** a colleague can clone and run `eas build -p android --profile uat` successfully, without asking you anything.

---

## Level 1 → 2: The PR gate

**Goal:** broken code stops before a human reviews it.

The defining property of this level: **it touches no EAS resources and needs no secrets.** It is free, it is fast, and it cannot break anything. There is no reason to delay it.

### Artifact added

One workflow file that runs on every pull request:

```
install → typecheck → lint → test → expo-doctor
```

Full YAML for all three CI platforms: [cicd-runner-recipes.md](references/cicd-runner-recipes.md).

### Bootstrapping a gate in a repo with no tests

Most real projects arrive here with no jest config and possibly no eslint config. Do not let that postpone the gate — add it with what exists and let it grow:

| Repo has | Start the gate with |
|---|---|
| TypeScript only | `tsc --noEmit` + `npx expo-doctor` |
| + eslint config | add `eslint .` |
| + any tests | add `jest --ci --passWithNoTests` |

`--passWithNoTests` matters: the gate is green on day one and stays honest as tests appear. A gate that fails because there are no tests gets disabled within a week.

### The 5-minute rule

If the gate takes longer than about five minutes, people start merging around it and it stops being a gate. Cache the package manager's store, run the checks in one job rather than four, and keep anything slow (E2E, builds) off the PR trigger.

**Ready for Level 3 when:** the gate is green, runs in under five minutes, and nobody has merged around it for two weeks.

---

## Level 2 → 3: Automated internal distribution

**Goal:** testers always have the latest build, and you never hand-build a UAT artifact again.

### Artifact added

A workflow triggered by merges to your integration branch:

```sh
eas build --platform all --profile uat --non-interactive --no-wait
```

`--non-interactive` suppresses prompts that would hang the runner. `--no-wait` exits as soon as the build is queued, so you are not paying CI minutes to watch EAS work.

Add a notification step — a Slack message or a PR comment with the build link. A build nobody is told about is a build nobody installs.

### The one secret

`EXPO_TOKEN`, and nothing else. Store credentials, keystores and service accounts stay in EAS. See [cicd-secrets-in-ci.md](references/cicd-secrets-in-ci.md).

### Watch for version drift

This is the level where versioning problems become visible, because builds now happen without a person watching. If two store builds collide on the same build number, or CI and your laptop disagree about the current version, fix it here before Level 4 — [cicd-release-matrix.md](references/cicd-release-matrix.md).

**Ready for Level 4 when:** CI has produced every internal build for roughly two weeks, and no version numbers have drifted.

**Most teams should stop here.** Everything above this line saves time on every single day. Level 4 saves time on release day, which for many apps is once a month.

---

## Level 3 → 4: Automated release

**Goal:** release day takes thirty minutes and does not involve remembering anything.

### Artifact added

A tag-triggered pipeline with a human in the middle:

```
tag v* → eas build --profile live (both platforms) → human approval → eas submit
```

### Three safety defaults

| Default | Why |
|---|---|
| Trigger on a **tag**, never on merge to `main` | Tagging is a deliberate act. Merging is not. |
| An explicit **approval step** before submit | Store submission is the one step you cannot undo |
| `"releaseStatus": "draft"` on Android; TestFlight-only on iOS first | The artifact reaches the store but does not reach users until you promote it |

### Fill in the submit profiles properly

Leave a platform's `submit` block **out entirely** rather than filling it with placeholders. A missing block fails immediately with a clear message. `"ascAppId": "YOUR_ASC_APP_ID"` fails deep inside the submission with a confusing one — and placeholder values have a habit of surviving into the release that needed them.

**Ready to consider 4-OTA when:** release day takes under thirty minutes and has needed no manual intervention for two consecutive releases.

---

## Level 4 → 4-OTA: Shipping a fix without a store review

**This is a branch, not a step.** It is the only level that can break already-installed apps.

### Preconditions — all four, before any OTA automation

1. `updates.url` configured in the app config
2. `runtimeVersion` set to a policy, `fingerprint` for CNG projects
3. Updates actually **enabled in the shipped binary** — verify, don't assume
4. **Code signing** configured — `react-native-security`

Preconditions 1–3 are the ones projects fail without knowing: `expo-updates` can be installed, listed as a plugin, and have channels configured in `eas.json`, while updates are disabled in the native config. In that state `eas update` publishes successfully and reaches nobody. The diagnostic is in [cicd-ota-vs-build.md](references/cicd-ota-vs-build.md).

### Artifact added

A fingerprint-gated update job, a staged rollout, and a **documented, rehearsed rollback**. Do not automate publishing until you have rolled one back on purpose.

### The real cost

Adding `runtimeVersion` and `updates.url` to an app that already has users means the next build is a *new runtime* — every installed client needs the store update before OTA reaches them. That is why [NEW-PROJECT-DAY-1.md](NEW-PROJECT-DAY-1.md) configures it on day one, when it costs nothing.

**Ready when:** you have actually needed a same-day fix and could not ship one. Until then this is speculative work with a real downside.

---

## Ordering multiple projects

When several apps need this, do them in an order that compounds.

| Do this first | Why |
|---|---|
| A **throwaway or low-stakes app** | Rehearse Levels 1–3 where a mistake costs nothing. You will get the Node version, the lockfile and the `.easignore` wrong the first time. Do that somewhere safe. |
| Your **most mature GitHub-hosted app** | The real pilot. Pick the one whose `eas.json` is already closest to correct — the pipeline should mostly *wrap* what exists rather than rebuild it. |
| Any app that is a **copy of the pilot** | Nearly verbatim port. This is where the pilot pays for itself. |
| The **awkward one** — different VCS host, oldest SDK, self-managed credentials | Do it deliberately, second-to-last, as the exercise that proves the recipes generalise. Never make this the pilot: its pattern transfers to nothing. |
| **Duplicate repos** | Delete or archive the duplicate *before* adding CI, or two pipelines will fight over one remote. |

Choosing the pilot, concretely: prefer GitHub (it keeps all platform options open), prefer the best existing `eas.json`, and prefer an app that has a near-clone in the portfolio so the payoff is two apps rather than one. Explicitly *do not* pilot on the project with the most problems — the hardest project is not the best first one.