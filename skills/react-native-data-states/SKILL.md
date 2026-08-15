---
name: react-native-data-states
description: >-
  The complete set of states an async region needs in a React Native app —
  loading, empty, error, offline, refetching and optimistic — and how to render
  each one so a screen never shows a bare spinner or a blank page. Use when
  building or reviewing any screen that fetches, lists, saves or syncs data;
  when a list has no empty state; when errors surface as raw messages or
  silent failures; when a pull-to-refresh flashes the whole screen; or when an
  offline-first app needs to show pending/synced/failed status per record.
  Trigger on "add a loading state", "empty state", "no data", "error state",
  "retry", "offline indicator", "sync status", "pending changes", "optimistic
  update", "pull to refresh", "the screen is blank while loading", or any
  ActivityIndicator-only screen. Pure patterns — no native dependency, so it is
  safe on the New Architecture and adds nothing to the Android 16 KB surface.
---

# React Native Data States

Most "the app feels unfinished" feedback is not about visual design. It is about
the states nobody built: the blank page before data arrives, the empty list with
no explanation, the failure that shows a raw error string, the save that seemed
to work but silently didn't sync.

This skill has **no dependencies**. It costs nothing native, works identically on
Expo and bare React Native, on Paper and Fabric.

---

## The one rule that matters most

**An async region has six states, not two.**

```
loading → empty → error → offline → refetching → optimistic
```

Building only `loading` and `success` is what produces screens whose entire
error handling is an `ActivityIndicator` that spins forever. Every one of the six
is a real thing that happens to real users; each needs a deliberate answer, even
if that answer is "render nothing".

Before writing a screen, answer all six. It takes a minute and prevents the
majority of data-state bugs.

| State | Question to answer |
| --- | --- |
| **loading** | First paint, no data yet. Skeleton, spinner, or nothing? |
| **empty** | Request succeeded, zero results. Why is it empty, and what now? |
| **error** | Request failed. What can the user *do*? |
| **offline** | No connection. Is the app still usable? |
| **refetching** | Have data, fetching again. Must not disturb what's on screen. |
| **optimistic** | Write in flight. Show the result before the server confirms? |

---

## Choosing the loading treatment

Not every wait deserves the same UI. Work down this list:

1. **Is the wait under ~300 ms?** Show **nothing**. Anything that appears and
   disappears in under a third of a second reads as a flicker, and flicker feels
   *slower* than a brief pause.
2. **Do you already know the layout's shape?** (list rows, cards, a profile
   header) → **skeleton**. It previews real structure and eliminates the jump
   when data lands. See the `react-native-skeleton-placeholder` skill.
3. **Is the result shape unknown, or the wait indeterminate?** (search across
   types, an upload, a submit) → **spinner**.
4. **Is this a refetch of data already on screen?** → **inline indicator only**.
   Never replace visible content with a skeleton.
5. **Is the region tiny?** (a badge, one value) → inline spinner or nothing.

The most common mistake is a full-screen spinner for a list whose shape is
perfectly predictable. The second most common is a skeleton on pull-to-refresh.

---

## A single contract for all six states

Branching on `isLoading && !data ? ... : error ? ...` inline, in every screen,
is how states get forgotten. Model them once.

```ts
// data/state.ts
export type DataState<T> =
  | { status: 'loading' }
  | { status: 'empty' }
  | { status: 'error'; error: Error; retry: () => void }
  | { status: 'offline'; staleData?: T }
  | { status: 'ready'; data: T; isRefetching: boolean };

export function toDataState<T>(q: {
  data: T | undefined;
  isLoading: boolean;
  isFetching: boolean;
  error: Error | null;
  refetch: () => void;
  isEmpty?: (d: T) => boolean;
}, isConnected: boolean): DataState<T> {
  // Order matters. Offline outranks error: a failure caused by no connection
  // is not the same problem, and must not be reported as one.
  if (!isConnected && !q.data) return { status: 'offline' };
  if (!isConnected && q.data)  return { status: 'offline', staleData: q.data };
  if (q.isLoading)             return { status: 'loading' };
  if (q.error)                 return { status: 'error', error: q.error, retry: q.refetch };
  if (!q.data || q.isEmpty?.(q.data)) return { status: 'empty' };
  return { status: 'ready', data: q.data, isRefetching: q.isFetching };
}
```

The ordering in `toDataState` is the important part. Reporting a network
timeout as "Something went wrong" when the user simply has no signal sends them
debugging the wrong problem.

Then a boundary component makes forgetting a state impossible — the compiler
requires every case:

```tsx
// data/DataBoundary.tsx
export function DataBoundary<T>({
  state, skeleton, empty, children,
}: {
  state: DataState<T>;
  skeleton: React.ReactNode;
  empty: React.ReactNode;
  children: (data: T, isRefetching: boolean) => React.ReactNode;
}) {
  switch (state.status) {
    case 'loading':
      return <View accessibilityLabel="Loading">{skeleton}</View>;
    case 'empty':
      return <>{empty}</>;
    case 'error':
      return <ErrorState error={state.error} onRetry={state.retry} />;
    case 'offline':
      return state.staleData
        ? <><OfflineBanner />{children(state.staleData, false)}</>
        : <OfflineState />;
    case 'ready':
      return <>{children(state.data, state.isRefetching)}</>;
  }
}
```

Typing `state` as a discriminated union means adding a seventh state later
produces compile errors at every call site — exactly where you want them.

---

## Empty states

An empty screen is a conversation the app is having badly. Three parts, in order:

1. **What happened** — plainly. "No tasks yet", not "Empty".
2. **Why** — only if it isn't obvious.
3. **One action** — the single most useful next step.

The three kinds are not interchangeable:

| Kind | Situation | Tone |
| --- | --- | --- |
| **First use** | Nothing has ever been created | Welcoming; the action is *create the first one* |
| **User cleared** | They finished or deleted everything | Congratulatory; often no action needed |
| **No results** | A filter or search matched nothing | Corrective; the action is *clear the filter* |

```tsx
// Wrong — three different situations, one useless message
{items.length === 0 && <Text>No data</Text>}
```

```tsx
// Right — the message answers "what now?"
{items.length === 0 && (
  hasActiveFilters
    ? <EmptyState
        title="No results"
        body="No tasks match the current filters."
        actionLabel="Clear filters"
        onAction={clearFilters} />
    : <EmptyState
        title="No tasks yet"
        body="Tasks assigned to you will appear here."
        actionLabel="Create a task"
        onAction={createTask} />
)}
```

A "no results" state that doesn't offer to clear the filter is a dead end — the
user often cannot see which filter is responsible.

---

## Error states

**Never show the user a raw error.** `error.message` is written for a developer.
Log it; show a sentence the user can act on.

```tsx
// Wrong
<Text>{error.message}</Text>   // "Request failed with status code 500"
```

```tsx
// Right
<ErrorState
  title="Couldn't load tasks"
  body="Something went wrong on our end. Your saved work is safe."
  actionLabel="Try again"
  onAction={retry}
/>
```

Rules that hold generally:

- **Every error state needs a retry affordance.** An error with no way forward is
  a dead app.
- **Say what is safe.** After a failed sync the user's first fear is lost work.
  Answer it before they ask.
- **Match scope to blast radius.** One failed widget gets an inline error; a
  failed screen gets a full error state. Never take over the screen for a
  non-critical fetch.
- **Distinguish retryable from terminal.** A 404 should not offer "Try again" —
  it will fail identically. Offer navigation instead.
- **Log the real error** with enough context to debug, and keep tokens/PII out
  of the log.

---

## Offline & sync status

The highest-value section for offline-first apps, and the most commonly missing.

### Three questions the UI must answer

1. **Am I online?** — a persistent, non-blocking connectivity banner.
2. **Did my change save?** — per-record status, because "saved locally" and
   "reached the server" are different promises.
3. **What is still pending?** — a global count the user can inspect.

### Never block on the network

In an offline-first app, a write goes to the local database and returns
immediately. The UI confirms the *local* write and shows sync as a background
concern.

```tsx
// Wrong — user waits on the network in an app designed not to need it
setSaving(true);
await api.saveTask(task);
setSaving(false);
```

```tsx
// Right — local write is the source of truth, sync is background
await db.write(() => tasks.create(task));   // fast, always succeeds
enqueueSync(task.id);                        // outbox picks it up
toast.success('Saved');                      // honest: it *is* saved, locally
```

### Per-record status

Three states, and the failed one must be actionable:

```tsx
type SyncStatus = 'pending' | 'synced' | 'failed';

function SyncBadge({ status, onRetry }: { status: SyncStatus; onRetry: () => void }) {
  switch (status) {
    case 'synced':
      return null;                                  // the default. Don't decorate success
    case 'pending':
      return <Badge icon="cloud-upload" label="Waiting to sync" tone="muted" />;
    case 'failed':
      return <Badge icon="alert" label="Sync failed" tone="danger" onPress={onRetry} />;
  }
}
```

Rendering a green tick on every synced row is noise — it trains the eye to ignore
the column exactly where the failed state needs to stand out.

### Copy that doesn't over-promise

| Situation | Say | Not |
| --- | --- | --- |
| Saved locally, not sent | "Saved. Will sync when online." | "Saved" (implies the server has it) |
| Sending now | "Syncing…" | "Saving…" |
| Server confirmed | "Synced" | "Done" |
| Sync failed | "Couldn't sync — tap to retry" | "Error" |

### Stale data beats no data

If you have cached data and the network is down, **show the cache** with a banner
saying how old it is. An offline screen that hides data the user already
downloaded is strictly worse than one that shows it.

---

## Refetch vs. initial load

The distinction that prevents the most jarring bug in this whole area.

| | Initial load | Refetch |
| --- | --- | --- |
| Data on screen | None | Yes |
| Treatment | Skeleton / spinner | Inline indicator only |
| May replace content | Yes | **Never** |

```tsx
// Wrong — pull-to-refresh flashes the whole list away
if (isFetching) return <ListSkeleton />;
```

```tsx
// Right — the skeleton is gated on having no data at all
if (isLoading && !data) return <ListSkeleton />;

<FlashList
  data={data}
  refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}
  ListFooterComponent={isFetchingNextPage ? <InlineSpinner /> : null}
/>
```

Pagination follows the same rule: a footer spinner, never a full-screen state.

---

## Optimistic updates

Show the result before the server confirms — when it's safe.

### When optimistic is right

The action is reversible, likely to succeed, and the user's next move depends on
seeing it: toggling a like, checking off a task, reordering a list, editing text.

### When optimistic is wrong

- **Irreversible actions** — deleting, sending, submitting for approval.
- **Anything involving money** — payments, transfers, balances.
- **Server-decided outcomes** — anything the backend can reject on business
  rules the client doesn't know. Showing success then reverting is worse than a
  one-second wait.
- **Anything another person sees.** Never optimistically render a message as
  delivered.

For those, show a pending state and wait.

### Rollback is mandatory

An optimistic update without rollback is a lie the UI never takes back.

```tsx
async function toggleComplete(id: string, next: boolean) {
  const previous = getTask(id);
  setTask(id, { ...previous, isCompleted: next });   // 1. apply immediately

  try {
    await api.updateTask(id, { isCompleted: next }); // 2. confirm
  } catch (err) {
    setTask(id, previous);                           // 3. roll back to the exact prior value
    toast.error("Couldn't update — try again");      // 4. and say so
    log(err);
  }
}
```

Roll back to the **captured previous value**, not to a recomputed one — by the
time the failure lands, other state may have changed.

Silent rollback is the worst outcome: the user sees their change undo itself with
no explanation and assumes the app is broken. Always pair rollback with a message.

---

## Anti-flicker timing

A state that appears and vanishes within a few frames is worse than no state.
Two thresholds fix it:

```ts
/** Show loading UI only after `delay`; once shown, keep it for `minDuration`. */
export function useDelayedLoading(isLoading: boolean, delay = 300, minDuration = 500) {
  const [visible, setVisible] = useState(false);
  const shownAt = useRef<number | null>(null);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;

    if (isLoading) {
      timer = setTimeout(() => {
        shownAt.current = Date.now();
        setVisible(true);
      }, delay);
    } else if (visible) {
      const elapsed = Date.now() - (shownAt.current ?? 0);
      timer = setTimeout(() => {
        setVisible(false);
        shownAt.current = null;
      }, Math.max(0, minDuration - elapsed));
    }

    return () => clearTimeout(timer);
  }, [isLoading, visible, delay, minDuration]);

  return visible;
}
```

- **`delay` (~300 ms)** — fast responses never show a loading state at all.
- **`minDuration` (~500 ms)** — once shown, it stays long enough to be read.

Apply the same idea to success toasts and sync badges: anything that flashes for
100 ms is visual noise, not feedback.

---

## Accessibility

- Give the loading region `accessibilityLabel="Loading"` — a skeleton is
  invisible to a screen reader otherwise.
- Announce state transitions that happen without user input:
  `AccessibilityInfo.announceForAccessibility('Tasks loaded')`, and always for
  errors, which are otherwise silent.
- Empty and error states are `accessibilityRole="text"` with the action as a
  proper `button` — not one blob of text.
- Never communicate sync status with colour alone; pair every badge with a label
  or icon.

---

## Common pitfalls

- **Only two states built.** The root cause of everything else here.
- **`if (isLoading) return <Spinner />`** without checking for existing data —
  turns every refetch into a full-screen flash.
- **A generic "No data" for every empty case** — misses that the user needs
  different help in each.
- **Raw `error.message` on screen.** Log it, don't render it.
- **An error state with no retry.** A dead end.
- **Reporting offline as a generic error** — sends the user to debug the wrong
  thing. Check connectivity before classifying a failure.
- **Hiding cached data when offline.** Show it with a staleness note.
- **"Saved" when it's only saved locally.** Say "will sync when online".
- **A success tick on every synced row** — noise that hides the failures.
- **Optimistic updates on irreversible or money actions.**
- **Rollback with no message.** The UI appears to break itself.
- **Loading states that flash.** Use `useDelayedLoading`.
- **Sync failures that only exist in logs** — if the user can't see it, it will
  never be retried.

---

## Pre-ship checklist

For **every** async region on the screen:

- [ ] All six states answered — loading, empty, error, offline, refetching, optimistic.
- [ ] Loading treatment chosen deliberately (skeleton / spinner / nothing), not by habit.
- [ ] Skeleton gated on `isLoading && !data` so refetch never replaces content.
- [ ] Empty state names its kind (first-use / cleared / no-results) and offers one action.
- [ ] Error state is human-readable, offers retry, and says what is safe.
- [ ] Offline is distinguished from error **before** classifying the failure.
- [ ] Cached data is shown when offline, with a staleness indicator.
- [ ] Local-only writes are described honestly ("will sync"), never as confirmed.
- [ ] Per-record sync status visible, with failures actionable.
- [ ] Optimistic updates capture the previous value, roll back on failure, and
      tell the user when they do.
- [ ] Anti-flicker delay + minimum duration applied.
- [ ] Loading regions labelled; error and completion announced to screen readers.
