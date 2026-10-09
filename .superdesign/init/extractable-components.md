# Extractable components — `web/`

Catalog of reusable layout and basic components suitable for Superdesign `DraftComponent` extraction. Page-specific feature panels and route implementations are intentionally excluded.

## Layout components

### AppShell
- Source: `web/src/App.tsx`
- Category: layout
- Description: Responsive dashboard shell with mobile header, collapsible sidebar, plugin slots, banner stack, route outlet, and persistent chat host.
- Key props: none today; extraction candidates are `activePath`, `collapsed`, `mobileOpen`, and plugin navigation entries.
- Hardcoded: `Hermes Agent` wordmark, built-in route labels/paths, Lucide icon mapping, 1024px desktop breakpoint, sidebar widths (`w-64`/`w-14`), localStorage key `hermes-sidebar-collapsed`, Tailwind classes, plugin-slot names.

### SidebarNavigation
- Source: `web/src/App.tsx`
- Category: layout
- Description: Primary navigation rail with grouped built-in and plugin routes, active-link styling, collapse behavior, and mobile overlay.
- Key props: `activePath`, `collapsed`, `mobileOpen`, `items`, `pluginItems`, `onNavigate`, `onToggleCollapsed` (extraction candidates; currently internal state/data).
- Hardcoded: core route inventory and fallback English labels, icon registry, group presentation, Tailwind classes, desktop/mobile breakpoints.

### PageHeaderProvider
- Source: `web/src/contexts/PageHeaderProvider.tsx`
- Category: layout
- Description: Shared page frame that resolves route titles and exposes `afterTitle` and end-toolbar slots above a scroll-managed main region.
- Key props: `children`, `pluginTabs`; contextual state is `title`, `afterTitle`, and `end`.
- Hardcoded: `/chat` and `/env` responsive exceptions, header/main Tailwind classes, semantic `<header>`/`<main>` structure.

### ProfileSwitcher
- Source: `web/src/components/ProfileSwitcher.tsx`
- Category: layout
- Description: Sidebar profile target selector that collapses to an icon and hides when only one profile exists.
- Key props: `collapsed`; profile list, selected profile, and change handler currently come from `useProfileScope`.
- Hardcoded: `Users` icon, fallback profile name `default`, translated labels, sidebar sizing and Tailwind classes.

### SidebarStatusStrip
- Source: `web/src/components/SidebarStatusStrip.tsx`
- Category: layout
- Description: Compact gateway/session summary linking the sidebar to the Sessions route, including a loading skeleton.
- Key props: `status` (`StatusResponse | null`).
- Hardcoded: destination `/sessions`, status-dot colors, gateway/session row structure, skeleton width, Tailwind classes.

### SidebarFooter
- Source: `web/src/components/SidebarFooter.tsx`
- Category: layout
- Description: Sidebar footer displaying the running version and Nous Research attribution.
- Key props: `status` (`StatusResponse | null`).
- Hardcoded: `https://nousresearch.com`, version prefix `v`, external-link behavior, typography and Tailwind classes.

### ProfileScopeBanner
- Source: `web/src/components/ProfileScopeBanner.tsx`
- Category: layout
- Description: App-wide amber notice shown while the dashboard manages a non-current profile.
- Key props: none today; extraction candidates are `profile`, `currentProfile`, and visibility.
- Hardcoded: `Users` icon, amber palette, translated fallback sentence, border/padding classes.

### MemoryPressureBanner
- Source: `web/src/components/MemoryPressureBanner.tsx`
- Category: layout
- Description: Dismissible app-wide warning for elevated/critical memory or disk pressure and suspected prior OOM events.
- Key props: `status` (`StatusResponse | null`); dismissal state is internally persisted.
- Hardcoded: severity precedence, warning/close icons, sessionStorage key scheme, warning/destructive palettes, threshold-derived copy and Tailwind classes.

### MultiplexStandaloneBanner
- Source: `web/src/components/MultiplexStandaloneBanner.tsx`
- Category: layout
- Description: Dismissible warning when a standalone gateway leaves additional profiles unserved.
- Key props: `status` (`StatusResponse | null`).
- Hardcoded: command `hermes gateway migrate --multiplex`, `AlertTriangle`/`X` icons, sessionStorage key, amber styling and copy template.

### SharedMetricsConsentBanner
- Source: `web/src/components/SharedMetricsConsentBanner.tsx`
- Category: layout
- Description: First-run, app-wide metrics-consent offer with equal allow/deny/later actions.
- Key props: none today; consent and profile are loaded from API/context.
- Hardcoded: relay-metrics documentation URL, sessionStorage key, `BarChart3`/`X` icons, action set, banner styling.

### AuthWidget
- Source: `web/src/components/AuthWidget.tsx`
- Category: layout
- Description: Sidebar identity/status widget with provider label, truncated user ID, failure state, and logout action.
- Key props: none today; auth state is loaded internally.
- Hardcoded: `/login` navigation, 14-character ID truncation, `LogOut` icon, fallback error copy, Tailwind classes.

## Basic components

### ConfirmDialog
- Source: `web/src/components/ConfirmDialog.tsx`
- Category: basic
- Description: Portal-based confirmation modal with focus restoration, Escape/backdrop dismissal, destructive tone, and busy state.
- Key props: `open`, `title`, `description`, `confirmLabel` (default `Confirm`), `cancelLabel` (default `Cancel`), `destructive` (default `false`), `loading` (default `false`), `onConfirm`, `onCancel`.
- Hardcoded: `AlertTriangle` icon, modal width `max-w-md`, overlay opacity/z-index, ellipsis loading label, focus target and Tailwind classes.

### DeleteConfirmDialog
- Source: `web/src/components/DeleteConfirmDialog.tsx`
- Category: basic
- Description: Localized destructive wrapper around the shared confirmation-dialog contract.
- Key props: `open`, `title`, `description`, `confirmLabel`, `cancelLabel`, `loading`, `onConfirm`, `onCancel`.
- Hardcoded: destructive mode is always enabled; default labels come from `t.common.delete` and `t.common.cancel`.

### LoadErrorNotice
- Source: `web/src/components/LoadErrorNotice.tsx`
- Category: basic
- Description: Persistent alert card for page-load failures with optional detail and retry action.
- Key props: `what`, `detail`, `onRetry`, `className`.
- Hardcoded: `AlertCircle`/`RotateCcw` icons, destructive tint, compact card layout, translated retry copy and Tailwind classes.

### Markdown
- Source: `web/src/components/Markdown.tsx`
- Category: basic
- Description: Lightweight Markdown renderer optimized for assistant text, including blocks, inline formatting, links, highlights, and streaming state.
- Key props: `content`, `highlightTerms`, `streaming`.
- Hardcoded: supported Markdown subset, external-link target/rel, code/list styles, blinking caret behavior and Tailwind classes.

### AutoField
- Source: `web/src/components/AutoField.tsx`
- Category: basic
- Description: Recursive schema-driven editor for scalar, select, boolean, list, object, and array values.
- Key props: `schemaKey`, `schema`, `value`, `onChange`.
- Hardcoded: schema type names (`boolean`, `select`, `number`, `text`, `list`), comma-separated list parsing, label title-casing, `(none)` and placeholder strings, Tailwind classes.

### AllowlistInput
- Source: `web/src/components/AllowlistInput.tsx`
- Category: basic
- Description: Repeating input rows for an allowlist serialized as one deduplicated comma-separated value.
- Key props: `id`, `label`, `value`, `onChange`, `invalid`.
- Hardcoded: comma/newline parsing, `Plus`/`X` icons, add/remove behavior, row classes and button affordances.

### LanguageSwitcher
- Source: `web/src/components/LanguageSwitcher.tsx`
- Category: basic
- Description: Locale selector that adapts from an anchored listbox to a mobile bottom sheet.
- Key props: `collapsed` (boolean, default `false`), `dropUp` (boolean, default `false`); locale state currently comes from i18n context.
- Hardcoded: 640px sheet breakpoint, `Check` icon, no-flag presentation, dropdown geometry and Tailwind classes.

### ThemeSwitcher
- Source: `web/src/components/ThemeSwitcher.tsx`
- Category: basic
- Description: Theme/font chooser with palette swatches and responsive dropdown/bottom-sheet presentation.
- Key props: `collapsed` (boolean, default `false`), `dropUp` (boolean, default `false`); selected theme/font and options come from theme context.
- Hardcoded: 640px sheet breakpoint, `Palette`/`Type`/`Check` icons, three-stop swatch design, dropdown geometry and Tailwind classes.

### PlatformsCard
- Source: `web/src/components/PlatformsCard.tsx`
- Category: basic
- Description: Reusable status card listing connected, disconnected, disabled, or failed messaging platforms.
- Key props: `platforms`.
- Hardcoded: `Radio`/`Wifi`/`WifiOff`/`PowerOff`/`AlertTriangle` icons, four state-to-badge-tone mappings, card/list layout and Tailwind classes.
