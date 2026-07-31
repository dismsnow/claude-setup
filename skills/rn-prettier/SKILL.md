---
name: rn-prettier
description: Review and rewrite an Expo React Native TypeScript file to follow clean, consistent code style — imports, structure, TypeScript, StyleSheet, performance, and JSX rules.
argument-hint: <file-path>
---

Review and rewrite the target Expo React Native TypeScript file (or the currently open/selected file if no argument given: $ARGUMENTS) to follow clean, consistent code style. Apply ALL of the rules below — do not skip any section.

---

## 1. Import Order

Enforce this exact grouping, each separated by a blank line:

```
1. React (always first)
2. React Native core modules
3. Expo packages (expo-*, @expo/*)
4. Third-party packages (alphabetical within group)
5. Local imports — absolute paths (../../components/...) then relative (./)
```

Remove unused imports. Never use wildcard imports.

---

## 2. Component File Structure

Enforce this top-to-bottom order within every file:

```
1. Imports
2. Types / Interfaces (Props interface always named <ComponentName>Props)
3. Constants (outside component, if any)
4. Component function
   a. State declarations (useState)
   b. Refs (useRef)
   c. Store hooks (useSelector, useDispatch)
   d. Derived values (useMemo)
   e. Callbacks (useCallback)
   f. Effects (useEffect)
   g. Helper functions (plain functions used only inside this component)
   h. Return (JSX)
5. StyleSheet.create({}) — always at the bottom of the file
```

---

## 3. TypeScript Rules

- Every component must have an explicit Props interface, even if empty: `interface ComponentNameProps {}`
- Use `React.FC<Props>` for component typing
- No `any` — replace with proper types or `unknown`
- Prefer type unions over enums: `'pekerja' | 'pemantau'` not `enum Role`
- All `useSelector` calls must be typed: `useSelector((state: RootState) => ...)`
- All event handlers must have typed parameters

---

## 4. Naming Conventions

- Components: `PascalCase`
- Functions / variables: `camelCase`
- Constants (module-level): `UPPER_SNAKE_CASE`
- StyleSheet keys: `camelCase`
- Files: `PascalCase.tsx` for components, `camelCase.ts` for utilities/hooks

---

## 5. StyleSheet Rules

- All styles must live inside `StyleSheet.create({})` at the bottom — no inline style objects
- Exception: dynamic styles that depend on runtime values (e.g. `{ color: isActive ? '#89D1C7' : '#333' }`) can remain inline, but extract the static part to StyleSheet
- Use the project's spacing scale: `8, 12, 15, 16, 20, 24`
- Use the project's border radius scale: `8, 12, 24`
- Use the project's color palette where applicable:
  - Primary teal: `#89D1C7` / `#1a7a7a`
  - Text dark: `#333` / `#1E293B`
  - Border: `#E1E5E9`
- No magic numbers — extract repeated values to a named constant

---

## 6. Performance Rules

- Wrap components exported from list-item files with `React.memo()`
- Wrap callbacks passed as props with `useCallback`
- Wrap expensive derived values with `useMemo`
- Never create new objects/arrays directly inside JSX props — extract to a variable or memo

---

## 7. JSX Rules

- Self-close tags with no children: `<Icon />` not `<Icon></Icon>`
- Destructure props at the top of the component, not inline in JSX
- No ternary expressions longer than one line directly in JSX — extract to a variable above the return
- Keep JSX return clean: no logic, only rendering

---

## 8. General Cleanliness

- Remove all `console.log` / `console.warn` statements
- Remove commented-out code blocks
- No unused variables or functions
- Add a single blank line between logical sections inside a component
- No trailing whitespace

---

After rewriting, briefly list what was changed under a `## Changes` heading.
