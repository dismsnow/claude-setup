---
name: react-native-feedback-motion
description: >-
  How a React Native app tells the user something happened — toasts instead of
  blocking alerts, haptics that mean something, and motion that clarifies rather
  than decorates. Use when replacing Alert.alert for confirmations and success
  messages, adding a toast or snackbar, adding haptic feedback, animating list
  insert/remove, adding screen or element transitions, or respecting reduced
  motion. Trigger on "show a toast", "snackbar", "notification message",
  "Alert.alert", "confirmation message", "haptic", "vibrate", "buzz on tap",
  "animate this list", "fade in", "layout animation", "shared element
  transition", "reduce motion", or any review that finds success messages
  interrupting the user with a modal dialog.
---

# React Native Feedback & Motion

Feedback is how the app answers "did that work?". Motion is how it explains what
just changed. Both go wrong in the same way — by being applied uniformly instead
of proportionally.

---

## The one rule that matters most

**Match the weight of the feedback to the stakes of the event.**

`Alert.alert` is a blocking, OS-level modal. It stops everything, demands a tap,
and destroys the user's place in the flow. It exists for **decisions the user
must make**. It is not a way to say "saved".

An app with hundreds of `Alert.alert` calls has hundreds of interruptions, and
the ones that genuinely matter — "delete this permanently?" — no longer stand
out, because everything looks equally urgent.

### The feedback ladder

Work **down** from the lightest rung that does the job. Most events belong on
rungs 1–3.

| # | Rung | Use for | Cost to user |
| --- | --- | --- | --- |
| 1 | **Nothing** | The result is self-evident on screen | None |
| 2 | **Inline state change** | A toggle flips, a row updates, a count changes | None |
| 3 | **Haptic only** | Confirming a gesture the eye is already tracking | None |
| 4 | **Toast** | Success, non-blocking errors, undoable actions | Glanceable |
| 5 | **Inline banner** | Persistent conditions — offline, degraded mode | Occupies space |
| 6 | **Blocking dialog** | Irreversible decisions needing explicit consent | Stops everything |

**The test:** *if the user ignored this message entirely, what would go wrong?*
Nothing → rung 1 or 2. They'd miss a useful confirmation → rung 4. They'd lose
data or money → rung 6.

```tsx
// Wrong — a modal to report success. The user must tap to continue for no reason.
Alert.alert('Success', 'Task saved successfully');
```

```tsx
// Right — glanceable, non-blocking, disappears on its own
toast.success('Task saved');
```

```tsx
// Wrong — a toast for something irreversible. It can be missed entirely.
toast('Deleting record…');
```

```tsx
// Right — a decision needs a decision UI
Alert.alert('Delete record?', 'This cannot be undone.', [
  { text: 'Cancel', style: 'cancel' },
  { text: 'Delete', style: 'destructive', onPress: confirmDelete },
]);
```

### Better than confirming: make it undoable

A toast with **Undo** beats a confirmation dialog for anything reversible. It
costs the user nothing on the happy path — which is almost every path — and
still protects the mistake case.

```tsx
toast.success('Task deleted', {
  action: { label: 'Undo', onClick: () => restoreTask(id) },
});
```

Reserve blocking confirmation for what genuinely cannot be undone.

---

## Toasts

### Stack selection

| Project | Package | Adds a `.so`? |
| --- | --- | --- |
| **Any React Native app** (recommended) | `sonner-native` | **No** — pure JS |
| Want native OS toast/alert UI | `burnt` | No, but needs the `expo` package |

**`sonner-native` is the default.** It is pure JavaScript built on Reanimated, so
it adds no native binary and does not affect Android 16 KB alignment. Its peer
dependencies — `react-native-reanimated`, `react-native-gesture-handler`,
`react-native-safe-area-context`, `react-native-svg`, `react-native-screens` —
are already present in most apps, so in practice it is a zero-native-cost addition.

`burnt` renders true native toasts, which look more platform-authentic, but it is
built on the Expo Modules API and therefore requires the `expo` package even in a
bare project — the opposite of what most people expect.

```bash
npx expo install sonner-native      # Expo
npm i sonner-native                 # bare RN (peers must already be installed)
```

### Setup

`<Toaster />` goes once at the app root, **inside** the gesture handler and safe
area providers:

```tsx
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { Toaster } from 'sonner-native';

export default function RootLayout() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        {/* app tree */}
        <Toaster position="top-center" richColors />
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
```

### Usage

```tsx
import { toast } from 'sonner-native';

toast.success('Saved');
toast.error("Couldn't sync — tap to retry", { action: { label: 'Retry', onClick: retry } });
toast.warning('Working offline');

// Ties the toast to a promise's lifecycle — no manual state
toast.promise(saveTask(task), {
  loading: 'Saving…',
  success: 'Saved',
  error: "Couldn't save",
});
```

`toast.promise` is the one to reach for on any async action: it handles all three
states without the screen tracking a `isSaving` flag purely for messaging.

### Rules

- **Don't toast what the screen already shows.** If a row visibly disappears, a
  "Deleted" toast is redundant — unless it carries Undo.
- **One toast per action.** Not one per retry attempt in a loop.
- **Errors get an action** whenever retry is possible.
- **Keep them short** — a toast is glanceable. Long copy belongs inline.
- **Never put a required decision in a toast.** It auto-dismisses; the user can
  miss it entirely.

---

## Haptics

### The rule

**If you cannot say in one sentence what a haptic communicates, delete it.**

Haptics are a channel with very low bandwidth. Used sparingly they confirm,
warn, and mark boundaries without the user looking. Used on every tap they become
noise, drain battery, and get the app's vibration turned off in system settings —
losing the ones that mattered.

### Stack selection

| Project | Package | Adds a `.so`? |
| --- | --- | --- |
| **Expo** | `expo-haptics` | **No** |
| **Bare RN** (preferred) | `npx install-expo-modules` → `expo-haptics` | **No** |
| **Bare RN, Expo-free** | `react-native-haptic-feedback` or `react-native-haptics` | Varies — check |

```bash
npx expo install expo-haptics
```

### API

| Call | Meaning |
| --- | --- |
| `impactAsync(Light \| Medium \| Heavy \| Rigid \| Soft)` | Physical collision — a snap, a boundary |
| `notificationAsync(Success \| Warning \| Error)` | Outcome of an operation |
| `selectionAsync()` | Selection changed — picker tick, segment switch |
| `performAndroidHapticsAsync(type)` | Android-native effects; **no `VIBRATE` permission needed** |

Prefer `performAndroidHapticsAsync` on Android where available — it avoids
requesting the `VIBRATE` permission entirely.

### Mapping events to haptics

| Event | Haptic |
| --- | --- |
| Toggle, segment change, picker tick | `selectionAsync()` |
| Pull-to-refresh triggers | `impactAsync(Light)` |
| Drag snaps to a target | `impactAsync(Medium)` |
| Scroll hits the end of a list | `impactAsync(Soft)` |
| Save / sync succeeded | `notificationAsync(Success)` |
| Validation failed | `notificationAsync(Error)` |
| Destructive action confirmed | `notificationAsync(Warning)` |
| **Every button press** | **Nothing.** This is the mistake |

### Haptics are never the only feedback

They silently do nothing when:

- iOS **Low Power Mode** is on (detect with `expo-battery` if it matters)
- The user disabled system haptics
- The camera or dictation is active on iOS
- The Android device has no haptic hardware, or poor-quality vibration

Anything communicated **only** by a buzz is invisible to a meaningful share of
users. Always pair with a visual change.

### Wrap it in one file

One module means haptics can be globally disabled, respect reduced motion, and
have their library swapped without touching call sites.

```ts
// feedback/haptics.ts
import * as Haptics from 'expo-haptics';
import { Platform } from 'react-native';

let enabled = true;                       // driven by a user setting
export function setHapticsEnabled(v: boolean) { enabled = v; }

// Haptics must never break a user flow, so failures are swallowed deliberately.
const safe = (fn: () => Promise<void>) => {
  if (!enabled || Platform.OS === 'web') return;
  fn().catch(() => {});
};

export const haptics = {
  selection: () => safe(() => Haptics.selectionAsync()),
  impact:    (s: Haptics.ImpactFeedbackStyle = Haptics.ImpactFeedbackStyle.Light) =>
    safe(() => Haptics.impactAsync(s)),
  success:   () => safe(() => Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success)),
  warning:   () => safe(() => Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning)),
  error:     () => safe(() => Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error)),
};
```

Swapping to `react-native-haptic-feedback` later is then a change to this file
alone. Expose `setHapticsEnabled` in settings — some users find haptics
unpleasant, and taking the app's word for it is not accessible design.

---

## Motion

Motion should answer *where did that come from* or *what just changed*. If it
answers neither, it is decoration and it costs frames.

Defer to `react-native-skills` → `animation-gpu-properties` for the underlying
rule: **animate `transform` and `opacity` only.** Animating `width`, `height`,
`top` or `margin` triggers layout on every frame.

### Reanimated 4 layout animations

The highest value-per-line motion in React Native. Items entering and leaving a
list are the single most jarring un-animated transition.

```tsx
import Animated, { FadeIn, FadeOut, LinearTransition } from 'react-native-reanimated';

<Animated.View
  entering={FadeIn.duration(200)}
  exiting={FadeOut.duration(150)}
  layout={LinearTransition.springify()}   // siblings slide instead of jumping
>
  <TaskRow task={task} />
</Animated.View>
```

`layout` is what makes the *other* rows move smoothly when one is inserted or
removed. Without it they teleport.

Keep exits faster than entrances (~150 ms vs ~200 ms) — a slow exit feels
unresponsive because the user has already moved on.

### Durations

| Motion | Duration |
| --- | --- |
| Micro (press, toggle, ripple) | 100–150 ms |
| Standard (fade, slide, list item) | 200–300 ms |
| Large (screen transition, sheet) | 300–400 ms |
| Anything over 400 ms | Almost certainly too slow |

### Shared Element Transitions — not production-ready

Reanimated 4 supports them on Fabric from 4.2, but **behind the
`ENABLE_SHARED_ELEMENT_TRANSITIONS` feature flag, and upstream still labels the
feature experimental and not recommended for production.** Enabling the flag also
changes the behaviour of ordinary Layout Animations across the whole app.

Do not reach for it for a normal product screen. If continuity between screens
matters, get most of the effect with a matched `entering` animation on the
destination plus a consistent element position.

### Reduced motion is not optional

Users with vestibular disorders can be made physically unwell by motion. The OS
exposes the setting; honour it.

```ts
// feedback/useReduceMotion.ts
import { useEffect, useState } from 'react';
import { AccessibilityInfo } from 'react-native';

export function useReduceMotion() {
  const [reduce, setReduce] = useState(false);
  useEffect(() => {
    AccessibilityInfo.isReduceMotionEnabled().then(setReduce);
    const sub = AccessibilityInfo.addEventListener('reduceMotionChanged', setReduce);
    return () => sub.remove();
  }, []);
  return reduce;
}
```

Reduced motion means **remove movement, not feedback**. Cross-fade instead of
sliding; keep duration near zero rather than removing the state change entirely —
the user still needs to know something happened.

```tsx
const reduceMotion = useReduceMotion();

<Animated.View
  entering={reduceMotion ? FadeIn.duration(0) : SlideInRight.duration(250)}
  layout={reduceMotion ? undefined : LinearTransition.springify()}
/>
```

Reanimated also exposes `ReduceMotion.System` on animation builders to defer to
the OS setting directly.

### Press feedback

Every tappable element needs a visible response within ~100 ms, or the app reads
as broken on a slow network.

```tsx
<Pressable
  style={({ pressed }) => [styles.card, pressed && { opacity: 0.7 }]}
  android_ripple={{ color: 'rgba(0,0,0,0.1)' }}
  hitSlop={8}                        // small targets are the top tap-accuracy complaint
  accessibilityRole="button"
>
```

For gesture-driven press states on the UI thread, see `react-native-skills` →
`animation-gesture-detector-press`.

---

## Putting it together

One save action, using each channel for what it's good at:

```tsx
async function handleSave() {
  haptics.selection();                              // acknowledges the tap
  setSubmitting(true);                              // inline: button state

  try {
    await toast.promise(saveTask(task), {           // toast: outcome
      loading: 'Saving…',
      success: 'Saved',
      error: "Couldn't save",
    });
    haptics.success();                              // haptic: confirms without looking
  } catch {
    haptics.error();
  } finally {
    setSubmitting(false);
  }
}
```

No blocking dialog anywhere — because nothing here is a decision.

---

## Common pitfalls

- **`Alert.alert` for success messages.** The single biggest offender. Toast it.
- **A confirmation dialog for a reversible action.** Use undo instead.
- **A toast for something irreversible.** It can be missed; use a dialog.
- **Haptics on every button press.** Noise. Users disable them system-wide,
  losing the meaningful ones.
- **Haptic as the only feedback.** Invisible under Low Power Mode, disabled
  settings, or weak hardware.
- **Not wrapping haptics** — no way to disable them, and swapping library means
  touching every call site.
- **Animating `width`/`height`/`margin`.** Layout every frame. Use transform.
- **Missing `layout` on list items** — neighbours teleport when one is removed.
- **Exit animations as slow as entrances.** Feels sluggish.
- **Animations over 400 ms.** The user is waiting on the animation, not the data.
- **Enabling `ENABLE_SHARED_ELEMENT_TRANSITIONS` in production.** Experimental,
  and it changes Layout Animation behaviour app-wide.
- **Ignoring reduced motion.** An accessibility failure with physical consequences.
- **Removing feedback entirely under reduced motion** — the user still needs to
  know the state changed.
- **No press feedback**, or tap targets under 44×44 pt with no `hitSlop`.

---

## Pre-ship checklist

- [ ] No `Alert.alert` used purely to report success.
- [ ] Every remaining blocking dialog guards something **irreversible**.
- [ ] Reversible destructive actions offer **undo** instead of confirmation.
- [ ] `<Toaster />` mounted once at root, inside gesture + safe-area providers.
- [ ] Error toasts carry a retry action where retry is possible.
- [ ] Haptics routed through **one wrapper**, user-disableable.
- [ ] No haptic fires on ordinary button presses.
- [ ] Nothing is communicated by haptic **alone**.
- [ ] List items have `entering` / `exiting` / `layout`.
- [ ] Only `transform` and `opacity` animated.
- [ ] Durations within the table; exits faster than entrances.
- [ ] Reduced motion honoured — movement removed, feedback kept.
- [ ] Shared Element Transitions **not** enabled in production.
- [ ] Every tappable has visible press feedback and an adequate hit target.
