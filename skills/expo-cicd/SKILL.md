---
name: expo-cicd
description: CI/CD and release automation for Expo / React Native apps on EAS — EAS Workflows vs GitHub Actions vs GitLab CI, eas.json build and submit profiles, mapping profiles to update channels and store tracks, appVersionSource and autoIncrement, OTA update vs new native build, what runs on PR vs merge vs tag, EXPO_TOKEN and credentials in CI. Use when a project has no CI, when automating Expo builds, store submissions or OTA releases, or when designing a release process.
license: MIT
metadata:
  tags: expo, eas, ci, cd, release, eas-build, eas-update, eas-submit, github-actions, gitlab-ci, ota, versioning
---

# Expo CI/CD

## Overview

**CI/CD for an Expo app is a mapping problem, not a scripting problem.**

The pipeline's entire job is to call `eas build`, `eas submit` or `eas update` with the right profile at the right moment. The scripts are short and nearly identical across projects. Almost every real failure is a wrong *mapping* — a `production` build listening on the `uat` channel, a store profile with no `autoIncrement`, a CI runner that resolves `ENVIRONMENT` differently than your laptop does — not a broken script.

So the work is: fill in the release matrix, then write the twelve lines of YAML that execute it. This skill is ordered that way. If you are reaching for YAML first, you are starting in the wrong place.

## When to Use

- A project has no CI and you are deciding what to build first
- Automating Expo builds, store submissions, or OTA updates
- Designing or fixing a release process (which branch produces which artifact)
- Choosing between EAS Workflows, GitHub Actions and GitLab CI
- A build works locally but produces the wrong artifact in CI
- Deciding whether a change can ship as an OTA update or needs a new binary

## When NOT to Use

This skill is for **Expo / CNG projects** — an `app.json` or `app.config.*` plus an `expo` dependency. Route elsewhere for:

| Question | Skill |
|---|---|
| "Build an iOS simulator artifact / Android emulator APK for this PR" | `github-actions` |
| "Download the artifact from that workflow run" | `github-actions` |
| "Is this value safe to put in the app? Where does this API key belong?" | `react-native-security` |
| "Sign my OTA updates / handle the code-signing key" | `react-native-security` |
| "Which build should I benchmark / profile?" | `react-native-best-practices` |
| "Why did my hand-edited `android/` file disappear?" | `react-native-best-practices` |

One disambiguation worth stating: the `github-actions` skill's composite actions call `xcodebuild` and `gradle` directly against `ios/` and `android/`. **They target bare React Native CLI projects and will not work in a CNG project** without an `expo prebuild` step first — in a CNG project those directories are generated, gitignored, and absent from a fresh checkout.

## Start Here

| Situation | Go to |
|---|---|
| Project has no CI at all | [ADOPTION.md][adoption] — the Level 0→4 ladder |
| Brand-new app, nothing written yet | [NEW-PROJECT-DAY-1.md][day1] — CI before the feature code |
| A pipeline exists and does the wrong thing | The Problem → Reference table at the bottom |

## Decisions You Make Once

Six decisions, made per project at setup. Get these right and the YAML is mechanical.

| # | Decision | The question that actually settles it | Reference |
|---|---|---|---|
| 1 | **Which CI platform** | Where does the repo live? EAS Workflows git triggers are GitHub-only. | [runner-recipes][recipes] |
| 2 | **`appVersionSource`** | Do you ever build a *release* locally in Xcode/Android Studio? No → `remote`. | [release-matrix][matrix] |
| 3 | **Who holds signing credentials** | Can a machine that is not yours produce a signed build? If not, CI can't either. | [secrets-in-ci][secrets] |
| 4 | **Where build-time env resolves** | What does `npx expo config --type public` print *on the runner*? | [release-matrix][matrix] |
| 5 | **Where each secret lives** | Is it needed *by the build*, or *by the running app*? | [secrets-in-ci][secrets] |
| 6 | **Is OTA even wired?** | A 3-question gate, not a choice. Most projects fail it without knowing. | [ota-vs-build][ota] |

**Decision 4 is the one that silently ruins releases.** When `app.config.js` branches on `process.env.ENVIRONMENT` to pick the bundle identifier, app name, scheme or push-provider app id, the value is resolved *at config-evaluation time* — and `eas.json` `env`, EAS environment variables, and the CI job's own environment do not resolve identically. If the runner sees a different value than your laptop, a UAT bundle identifier ships to production and nobody notices until the store rejects it. Verify by printing the resolved config on the runner, not by reading the config file.

## Decisions You Make Every Release

| # | Decision | How to decide |
|---|---|---|
| 7 | **OTA update or new native build?** | **The fingerprint decides, not a person.** Same fingerprint → update is allowed. Different → new build, no exceptions. [ota-vs-build][ota] |
| 8 | **Which profile → which channel and track** | Consult the matrix; don't reason it out each time. [release-matrix][matrix] |
| 9 | **What runs on PR vs merge vs tag** | The trigger ladder below. |
| 10 | **Who is allowed to reach a store** | An explicit human gate — `require-approval`, a tag-only trigger, or manual dispatch. |

On #7: a human deciding "that was only a JS change" is precisely how a bundle ships that calls a native module the installed binary does not contain. The app crashes on launch, for every user who received the update, and the fix is a store release. Let the tool decide.

## The Release Matrix

The core artifact of this skill. One row per build profile. Fill it in before writing any YAML — most pipeline bugs are visible as an inconsistent row.

| Profile | `distribution` | `channel` | `environment` | Submit track | Trigger | Version bump |
|---|---|---|---|---|---|---|
| `development` | `internal` | — | `development` | never | manual | none |
| `uat` | `internal` | `uat` | `preview` | never | merge → `develop` | none |
| `uat-store` | `store` | `uat` | `preview` | `internal` | manual | `versionCode` / `buildNumber` |
| `live` | `store` | `production` | `production` | `production`, `draft` | tag `v*` | `versionCode` / `buildNumber` |

Read a row left to right as one sentence: *"a `live` build is store-distributed, listens on the `production` update channel, resolves `production` environment variables, submits to the production track as a draft, is triggered only by a version tag, and increments the native build number."* If a row does not read as a coherent sentence, the profile is wrong.

The two mismatches to check first: a store profile whose `channel` does not match its `environment`, and a store profile with no `autoIncrement` (two store builds in a row will collide on the same build number).

## The Trigger Ladder

Organizing rule: **free things on every PR, EAS-minute things on merge, irreversible things behind a human.**

| Trigger | Runs | Cost |
|---|---|---|
| PR opened / updated | install → `typecheck` → `lint` → `test` → `expo-doctor` → fingerprint diff vs base | CI minutes only; target < 5 min |
| Merge to `develop` | `eas build --profile uat` both platforms, notify testers | EAS build minutes |
| Merge to `main` | fingerprint check → unchanged: `eas update`; changed: **stop and report** | cheap |
| Tag `v*` | `eas build --profile live` → human approval → `eas submit` | EAS minutes + a person |
| Nightly cron | `expo-doctor`, dependency audit, fingerprint drift vs last release | cheap |

**Anti-pattern: auto-submitting to a production track on merge to `main`.** Store submission is the one step you cannot undo. It gets a human, or a tag that a human pushes.

## Quick Reference

1. Fill in the release matrix above — every profile, every column.
2. Make the project reproducible by hand first (one lockfile, pinned Node, real `projectId`, a `RELEASE.md`). See [ADOPTION.md][adoption] Level 1.
3. Add the PR gate. No EAS involvement, no secrets, runs on every PR. Level 2.
4. Add `EXPO_TOKEN` as the **only** CI secret; everything else lives in EAS. See [secrets-in-ci][secrets].
5. Automate internal builds on merge — `eas build --profile uat --non-interactive --no-wait`. Level 3.
6. Only then automate store releases, behind a tag and a human approval. Level 4.

## References

| File | Description |
|------|-------------|
| [ADOPTION.md][adoption] | The Level 0→4 maturity ladder for retrofitting CI onto an existing app |
| [NEW-PROJECT-DAY-1.md][day1] | Ordered bootstrap so a new app starts with CI already wired |
| [cicd-runner-recipes.md][recipes] | EAS Workflows, GitHub Actions and GitLab CI — the same pipeline in three dialects, plus the repo-readiness blockers that stop a first run |
| [cicd-release-matrix.md][matrix] | Profile → channel → environment → track → trigger mapping, and version management (`appVersionSource`, `autoIncrement`) |
| [cicd-secrets-in-ci.md][secrets] | Where every secret lives: repo secret, EAS environment variable, EAS file variable, your server, or nowhere. Signing and store credentials. |
| [cicd-ota-vs-build.md][ota] | The OTA precondition gate, the fingerprint decision, staged rollout and rollback |

## Problem → Reference Mapping

| Problem | Start with |
|---------|------------|
| No CI at all; where do I start? | [ADOPTION.md][adoption] |
| Starting a new Expo app today | [NEW-PROJECT-DAY-1.md][day1] |
| EAS Workflows or GitHub Actions? | [cicd-runner-recipes.md][recipes] |
| Repo is on GitLab | [cicd-runner-recipes.md][recipes] |
| First CI run fails at install | [cicd-runner-recipes.md][recipes] — repo readiness |
| Build number collided / version drift | [cicd-release-matrix.md][matrix] |
| CI produced the wrong bundle identifier | [cicd-release-matrix.md][matrix] — env resolution |
| Where do I put this key so CI can use it? | [cicd-secrets-in-ci.md][secrets] |
| `eas submit` fails on credentials | [cicd-secrets-in-ci.md][secrets] |
| Can this change ship as an OTA update? | [cicd-ota-vs-build.md][ota] |
| An update needs to be rolled back | [cicd-ota-vs-build.md][ota] |

## Related Skills

- **`react-native-security`** — owns *is this a secret at all* and OTA code signing. This skill owns *which CI store carries a secret to the build*. Read it before deciding a value is safe to ship.
- **`react-native-best-practices`** — owns CNG / prebuild mechanics, config plugins, and *which artifact to benchmark*. This skill owns profile lifecycle and mapping. The overlap is `eas.json` fields; the seam is measurement vs. release.
- **`github-actions`** — bare RN CLI simulator/emulator artifacts and `gh` artifact retrieval. Not Expo, not releases.
- **`upgrading-react-native`** — SDK and RN version upgrades. This skill only adds the nightly `expo-doctor` job that surfaces drift.

---
Verified against EAS CLI v21.7.0 and Expo docs, August 2026. EAS schema and job types change — re-check `docs.expo.dev/eas/json` and `docs.expo.dev/eas/workflows/pre-packaged-jobs` before relying on a specific field.

[adoption]: ADOPTION.md
[day1]: NEW-PROJECT-DAY-1.md
[recipes]: references/cicd-runner-recipes.md
[matrix]: references/cicd-release-matrix.md
[secrets]: references/cicd-secrets-in-ci.md
[ota]: references/cicd-ota-vs-build.md