---
name: react-native-keyboard-ux
description: >-
  Keyboard handling and form UX for React Native — making inputs stay visible,
  move in sync with the keyboard, and behave the same on iOS and Android using
  react-native-keyboard-controller. Use whenever the keyboard covers an input,
  a form jumps or lags when the keyboard opens, KeyboardAvoidingView "works on
  iOS but not Android" (or vice versa), a sticky footer button is hidden while
  typing, or a screen needs Prev/Next/Done navigation across fields. Trigger on
  "keyboard covers my input", "keyboard hides the button", "form scrolls
  wrong", "KeyboardAvoidingView not working", "keyboard-aware scroll view",
  "adjustResize", "adjustPan", "input accessory", or any multi-field form,
  login, signup, checkout or data-entry screen. Also covers the surrounding
  form UX: focus handoff between fields, autofill, validation timing, and
  submit button states.
---

# React Native Keyboard & Form UX

The keyboard is the single most-used piece of UI in any data-entry app, and the
built-in tools for it are the weakest part of React Native. Almost every
"the form feels broken" bug traces back to one root cause.

---

## The one rule that matters most

**Move *with* the keyboard, not *after* it.**

React Native's built-in `KeyboardAvoidingView` listens to `keyboardDidShow` —
an event that fires **after** the keyboard has finished animating. By the time
your layout reacts, the animation is over. The content can only ever jump into
place late. No amount of `behavior` tuning fixes this, because the timing is
wrong at the source.

`react-native-keyboard-controller` subscribes to the platform's *animation*
callbacks instead — `WindowInsetsAnimationCallback` on Android and
`keyboardLayoutGuide` on iOS — so your layout is driven frame-by-frame by the
keyboard's actual position. That is the whole difference, and it is why the
library exists.

Everything else in this document follows from it.

---

## Stack selection

Check the project first:

```bash
node -p "require('./package.json').dependencies.expo ? 'expo' : 'bare'"
node -p "require('./package.json').dependencies['react-native']"
ls -d ios android 2>/dev/null   # present => bare or already prebuilt
```

| Project | Install | Adds a `.so`? |
| --- | --- | --- |
| **Expo** (managed or prebuilt) | `npx expo install react-native-keyboard-controller` | **No** |
| **Bare React Native** | `npm i react-native-keyboard-controller && npx pod-install` | **No** |

The library is Kotlin + Obj-C built on Reanimated primitives — it adds **no new
native binary**, so it does not change your Android 16 KB alignment surface. It
is a plain React Native library with autolinking; nothing about it is
Expo-specific.

**It does not run in Expo Go.** Native code means a dev build:
`eas build` a dev client once, or `npx expo prebuild && npx expo run:ios|android`.

### Version floors — check these before installing

| Library version | Requires |
| --- | --- |
| `1.18.0+` | React Native `0.81+` |
| `1.16.0+` | React Native `0.77+` |
| `1.13.0+` | React Native `0.75+` |
| `1.12.0+` | React Native `0.74+` |

Also required:
- **`react-native-reanimated` ≥ 3.0.0** (Reanimated 4 is fine)
- **`react-native-screens` ≥ 3.14** — older versions use deprecated Android APIs
  that conflict with it

Fabric / New Architecture has been supported since `1.2.0`. Pinning below the
floor for your RN version is the most common cause of "it installed but does
nothing".

### Setup

Wrap the app root **once**, above navigation:

```tsx
// app/_layout.tsx (Expo Router) or App.tsx
import { KeyboardProvider } from 'react-native-keyboard-controller';

export default function RootLayout() {
  return (
    <KeyboardProvider>
      {/* navigator / app tree */}
    </KeyboardProvider>
  );
}
```

If you see the keyboard flash briefly at app launch, disable preloading:

```tsx
<KeyboardProvider preload={false}>
```

---

## Which component to use

This is the decision most people get wrong. Pick by *what should move*, not by
what the screen is called.

| Component | Use when | What it does |
| --- | --- | --- |
| **`KeyboardAvoidingView`** | Standard forms, chat | Adjusts height/position/padding, in sync |
| **`KeyboardAwareScrollView`** | Scrollable forms with several inputs | Scrolls the focused `TextInput` into view automatically |
| **`KeyboardStickyView`** | A footer CTA that must ride above the keyboard | Translates vertically only — does **not** resize |
| **`KeyboardToolbar`** | Multi-field forms | Native Prev / Next / Done bar wired to focus |
| **`OverKeyboardView`** | Menus, pickers shown while typing | Renders above the keyboard *without* dismissing it |
| **`KeyboardExtender`** | Quick-action row attached to the keyboard | Renders inside the keyboard area |
| **`KeyboardBackgroundView`** | Blending UI into the keyboard's backdrop | Mirrors system keyboard background |

Drop-in replacement — the import changes, the API doesn't:

```diff
- import { KeyboardAvoidingView } from 'react-native';
+ import { KeyboardAvoidingView } from 'react-native-keyboard-controller';
```

**Delete the `behavior` and `keyboardVerticalOffset` props while you're there.**
Those exist to paper over the built-in component's platform inconsistency. The
replacement behaves identically on both platforms without them, and a stale
`keyboardVerticalOffset` will actively fight the correct layout.

---

## Migration recipes

### Recipe 1 — `KeyboardAvoidingView` with platform branching

The classic shape, and the reason it's fragile: two behaviors, a magic offset,
and different results per device.

```tsx
// Before — platform-branched, jumps late
<KeyboardAvoidingView
  behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
  keyboardVerticalOffset={Platform.OS === 'ios' ? 64 : 0}
  style={{ flex: 1 }}
>
  <ScrollView>{fields}</ScrollView>
</KeyboardAvoidingView>
```

```tsx
// After — one path, moves in sync
import { KeyboardAwareScrollView } from 'react-native-keyboard-controller';

<KeyboardAwareScrollView
  bottomOffset={24}                 // breathing room under the focused field
  contentContainerStyle={{ padding: 16 }}
  keyboardShouldPersistTaps="handled"
>
  {fields}
</KeyboardAwareScrollView>
```

`bottomOffset` is the one number worth tuning: the gap kept between the focused
input and the top of the keyboard. It replaces `keyboardVerticalOffset` and means
the same thing on both platforms.

### Recipe 2 — a manual Android keyboard-height hook

If a project has a hook that measures keyboard height and pads a ScrollView,
it is working around `android:windowSoftInputMode="adjustPan"` — the window pans
to reveal the focused input but never resizes, so content underneath becomes
unreachable. Such a hook is always built on `keyboardDidShow`, so it is always late.

```tsx
// Before — measures after the animation, Android-only, pads manually
const keyboardHeight = useKeyboardHeight();
<ScrollView contentContainerStyle={{ paddingBottom: keyboardHeight + 24 }}>
```

Replace the whole hook with `KeyboardAwareScrollView` (Recipe 1). If you need the
raw value for a custom animation, take it from the animated source instead:

```tsx
import { useKeyboardHandler } from 'react-native-keyboard-controller';
import { useSharedValue } from 'react-native-reanimated';

export function useKeyboardHeightShared() {
  const height = useSharedValue(0);
  useKeyboardHandler({
    onMove: (e) => {
      'worklet';
      height.value = e.height;   // every frame, not just at the end
    },
  }, []);
  return height;
}
```

Note `onMove` fires **throughout** the animation — that's the point. Keep it a
shared value and drive a `useAnimatedStyle` from it; never write it into React
state, which would re-render on every frame.

### Recipe 3 — a submit button hidden behind the keyboard

Don't pad the scroll view. Let the button ride the keyboard:

```tsx
import { KeyboardStickyView } from 'react-native-keyboard-controller';

<KeyboardStickyView offset={{ closed: 0, opened: 12 }}>
  <SubmitButton />
</KeyboardStickyView>
```

### Recipe 4 — multi-field forms get a toolbar

Ten fields on one screen means ten manual scrolls. One line fixes it:

```tsx
import { KeyboardToolbar } from 'react-native-keyboard-controller';

<>
  <KeyboardAwareScrollView bottomOffset={24}>{fields}</KeyboardAwareScrollView>
  <KeyboardToolbar />   {/* sibling of the scroll view, not a child */}
</>
```

`KeyboardToolbar` must be a **sibling** of the scroll view and a descendant of
`KeyboardProvider`. Nesting it inside the scroll view silently does nothing.

---

## Android: fix the manifest too

The library works best when the window resizes rather than pans. In a bare or
prebuilt project:

```xml
<!-- android/app/src/main/AndroidManifest.xml -->
<activity android:windowSoftInputMode="adjustResize" />
```

In an Expo managed project, set it in config rather than editing the file — a
hand-edit is erased by the next `expo prebuild --clean`:

```json
// app.json
{ "expo": { "android": { "softwareKeyboardLayoutMode": "resize" } } }
```

`adjustPan` is what forces the manual-padding workarounds in Recipe 2. Switching
to `resize` removes the need for them.

If the app is edge-to-edge, keep `KeyboardProvider` **outside**
`SafeAreaProvider`/navigation so it measures the full window.

---

## Form UX beyond the keyboard

Keyboard avoidance is necessary but not sufficient. These are the rest of what
makes a form feel finished.

### Focus handoff between fields

The keyboard's action key should advance the form, not dismiss it.

```tsx
const passwordRef = useRef<TextInput>(null);

<TextInput
  returnKeyType="next"
  onSubmitEditing={() => passwordRef.current?.focus()}
  blurOnSubmit={false}          // critical: without it the keyboard closes and reopens
/>
<TextInput
  ref={passwordRef}
  returnKeyType="done"
  onSubmitEditing={handleSubmit}   // last field submits
/>
```

`blurOnSubmit={false}` on every field **except the last** is the detail that gets
missed; without it the keyboard flickers closed between fields.

### Let the OS fill it in

Autofill is free UX and costs two props. Getting them wrong is worse than
omitting them, because the OS offers the wrong value.

| Field | `textContentType` (iOS) | `autoComplete` (Android) | Also set |
| --- | --- | --- | --- |
| Email | `emailAddress` | `email` | `keyboardType="email-address"`, `autoCapitalize="none"` |
| Password | `password` | `password` | `secureTextEntry` |
| New password | `newPassword` | `password-new` | `secureTextEntry` |
| One-time code | `oneTimeCode` | `sms-otp` | `keyboardType="number-pad"` |
| Phone | `telephoneNumber` | `tel` | `keyboardType="phone-pad"` |
| Name | `name` | `name` | `autoCapitalize="words"` |

Always pair with the right `keyboardType` — asking for a number-pad on a numeric
field removes a whole interaction step.

### Validate at the right moment

- **On change** — punishes people mid-word. Never for a first pass.
- **On blur** — the default. The user has finished the thought.
- **On submit** — for cross-field rules (passwords match, date ranges).
- **After a failed submit**, switch that field to on-change so the error clears
  as soon as it's fixed. This is the one case where on-change is right.

Never move focus automatically to an invalid field while the user is still
typing elsewhere.

### Submit button states

Disabled and loading are different states and must look different:

```tsx
<Pressable
  disabled={!isValid || isSubmitting}
  accessibilityState={{ disabled: !isValid || isSubmitting, busy: isSubmitting }}
>
  {isSubmitting ? <ActivityIndicator /> : <Text>Save</Text>}
</Pressable>
```

Keep the button's **width fixed** across both states, or the layout jumps at the
worst possible moment. Guard against double-submit in the handler, not just via
`disabled` — a fast double-tap can beat the state update.

### Dismissing the keyboard

Set `keyboardShouldPersistTaps="handled"` on scroll views containing inputs.
Without it, the first tap on a button only dismisses the keyboard and the user
has to tap twice — a bug that reads as unresponsiveness.

---

## Accessibility

- Every input needs a visible label, not just a `placeholder`. Placeholders
  vanish on focus, exactly when the user needs them, and screen readers treat
  them inconsistently.
- Link errors to their field with `accessibilityLabel` including the error text,
  so a screen reader announces the field *and* what's wrong with it.
- Use `accessibilityLiveRegion="polite"` (Android) / `AccessibilityInfo.announceForAccessibility`
  on validation summaries so failures are announced rather than silently rendered.
- Never rely on colour alone to mark an invalid field — pair it with text.

---

## Common pitfalls

- **Still importing `KeyboardAvoidingView` from `react-native`** — the single most
  common cause. The replacement is a drop-in; check the import line first.
- **Keeping `behavior` / `keyboardVerticalOffset`** after migrating. They fight
  the correct layout. Delete them, use `bottomOffset`.
- **`KeyboardProvider` missing or too deep in the tree** — components silently do
  nothing. It belongs at the root, above navigation.
- **`KeyboardToolbar` nested inside the ScrollView** — must be a sibling.
- **Writing keyboard height into React state** — re-renders every frame of the
  animation. Keep it a Reanimated shared value.
- **`adjustPan` left in the manifest**, then padding the scroll view by hand to
  compensate. Fix the manifest instead.
- **Missing `blurOnSubmit={false}`** on non-final fields — keyboard flickers
  between fields.
- **Version below the floor for your RN version** — installs cleanly, misbehaves
  at runtime. Check the table above.
- **Testing only on iOS.** The two platforms fail differently; the whole point of
  this library is that they stop doing so.
- **Expecting it to work in Expo Go.** It never will — build a dev client.

---

## Pre-ship checklist

- [ ] `KeyboardProvider` at the **root**, above navigation.
- [ ] Library version meets the **floor for the project's RN version**; `react-native-screens` ≥ 3.14.
- [ ] No remaining imports of `KeyboardAvoidingView` from `react-native`.
- [ ] No leftover `behavior` / `keyboardVerticalOffset` / manual keyboard-height padding.
- [ ] Android manifest (or Expo config) uses **`resize`**, not `adjustPan`.
- [ ] `keyboardShouldPersistTaps="handled"` on scroll views with inputs.
- [ ] `returnKeyType` chain + `blurOnSubmit={false}` on all but the last field.
- [ ] `textContentType` / `autoComplete` / `keyboardType` set per field.
- [ ] Validation on **blur**, switching to on-change only after a failed submit.
- [ ] Submit button has distinct disabled vs loading states, fixed width, and
      double-submit protection.
- [ ] Every input has a **visible label**, not just a placeholder.
- [ ] Tested on **both** platforms, and on a small screen where the keyboard
      covers more of the form.
