# Hermes Agent Web — Design System

## Product context

Hermes Agent is a technical dashboard for configuring and operating an AI agent across chat, sessions, files, models, skills, plugins, profiles, channels, automation, and system settings. The requested new target is a responsive reader-registration screen at the conceptual route `/library/register`: it lets a visitor apply for a library card while remaining visually native to the existing Hermes dashboard.

Primary job to be done: complete a trustworthy reader registration without losing context, understand which fields are required, review consent, and leave with a clear application/reader-card status.

Baseline viewport: desktop web at 1440×1024. The design must remain usable at tablet and mobile widths; below 1024px the sidebar becomes a mobile drawer and content collapses to one column.

## Existing application shell

- Preserve the Hermes dashboard shell: fixed/collapsible left sidebar on desktop, mobile top bar below 1024px, shared page header, scrollable main region.
- Expanded sidebar width: 256px (`w-64`); collapsed desktop rail: 56px (`w-14`).
- The shell background is `#041c1c`; borders use the active cream midground at low alpha.
- Brand is text-only in the source UI: `HERMES AGENT`, uppercase, compact two-line wordmark. Do not invent a logo or pictogram.
- New conceptual navigation item: `Library` / `Библиотека`, using a book icon, visibly active for this screen.
- Shared page header title: `Запись в библиотеку`.

## Canonical visual language

Use the default Hermes Teal theme as the hard visual source of truth.

### Color tokens

- Canvas/background: `#041c1c`.
- Primary text and primary action fill (`midground`): `#ffe6cb`.
- Primary action text: `#041c1c`.
- Card/popover: 4% mix of `#ffe6cb` into `#041c1c`.
- Secondary: 6% mix; muted: 8% mix; accent: 10% mix.
- Borders/inputs: 15% `#ffe6cb` over transparent.
- Secondary text: approximately 80% cream/midground.
- Success: `#4ade80`; warning: `#ffbd38`; destructive: `#fb2c36`.
- Do not introduce purple, blue, neon gradients, white page canvases, or unrelated accent colors.

### Typography

- UI sans/display: `system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`.
- Monospace/data: `ui-monospace, "SF Mono", "Cascadia Mono", Menlo, Consolas, monospace`.
- Base size 15px, line-height 1.55, default letter-spacing 0.
- Dashboard chrome and section labels may use compact uppercase text with 0.08–0.12em tracking.
- Body copy and form labels use sentence case. Avoid decorative serif or handwritten fonts.

### Geometry and density

- Spacing scale: 4px base; comfortable density.
- Radius base: 8px; use 4–12px derived radii. Do not turn the UI into pill-heavy consumer styling.
- Cards: quiet 1px token border, low-contrast background, restrained or no shadow.
- Controls: minimum 40px touch height on mobile; desktop fields approximately 40–44px.
- Use 24px section gaps, 16–20px card padding, 8–12px local gaps.

### Motion

- Fast, restrained transitions around 180–250ms.
- Use subtle fade/4px translate for dialogs or progressive content.
- No large parallax, floating decorative motion, or animated gradients.

## Components and interaction rules

- Reuse the visual behavior of the existing Hermes `Button`, `Input`, `Label`, `Checkbox`, `Card`, `Badge`, and `Toast` primitives.
- Primary buttons use cream fill and dark teal text; secondary actions are outlined or ghost.
- Inputs use token borders and dark surfaces with strong focus rings in cream.
- Validation appears adjacent to the field, not only in a toast.
- Required/optional status must be explicit.
- Preserve keyboard navigation, visible focus states, semantic labels, and adequate contrast.
- Use Lucide-style outline icons only; icons support text rather than replacing important labels.

## Reader-registration content contract

The two concepts may reorganize the flow, but both must visibly support the same complete task:

- Applicant identity: surname, first name, patronymic optional, date of birth.
- Contact: phone and email; at least one contact channel is clearly required.
- Identity document: document type, series/number, issue date; explain privacy briefly.
- Library preferences: preferred branch and notification channel.
- Consent: personal-data processing and library rules; consent cannot be preselected.
- Review/status: clear progress, editable summary, submit CTA, and a brief statement of what happens after submission.
- Use realistic Russian-language labels and helper text. Never show real personal data, credentials, or secrets.

## Responsive behavior

- Desktop: content can use two columns when that improves comprehension; keep the main task within a readable 1100–1200px region.
- Tablet: reduce secondary panels and keep form fields at comfortable widths.
- Mobile: single column, mobile Hermes header, sidebar hidden behind menu, sticky or naturally reachable primary action, no clipped horizontal stepper.

## Fidelity constraints

- The screen must look like a native Hermes dashboard route, not a standalone marketing page or municipal portal.
- Keep the existing dark teal/cream theme, shell proportions, border treatment, fonts, spacing, and component language.
- Do not add new colors, fonts, glassmorphism, glossy gradients, oversized hero sections, stock photos, illustrations, or decorative branding.
- The two concepts should differ in information architecture and composition, not in brand styling.
