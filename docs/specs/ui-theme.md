# UI theme

Spec for restyling the whole site with Tailwind CSS and shadcn/ui, as decided in ADR 0005. **This is a restyle, not a rebuild**: what the pages say and do stays exactly as it is; only how they look changes.

Each rule has a number; tests cite it.

## Decided by the author

On 2026-10-14:

- Tailwind CSS and shadcn/ui (ADR 0005). shadcn components are copied into the repository.
- A light theme only; no dark mode.
- No dependency beyond what Tailwind and the shadcn setup need.
- The system font stack or one bundled font; no web font loaded from elsewhere.
- A header with the navigation, a footer, cards for the facilities and the events, a grid for the gallery, a styled admin table and a styled login.
- The hard constraints H1 to H6 below.

## Hard constraints

| Rule | |
|---|---|
| H1 | Same pages, same addresses, same text, same headings and heading levels, same labels, same link names and link order. No text is added, removed or reworded; no heading, link, button or form field is added or removed. |
| H2 | The F01 booking form keeps its fields, their order, labels, types, limits, messages and the place of each error message (under its field, `role="alert"`). The tick boxes stay native `<input type="checkbox">`; the lists of the admin filters stay native `<select>`; the decline and delete questions stay where they are, as they are (`role="dialog"`). shadcn's own Checkbox, Select and Dialog are not used: they change roles, focus and behaviour. |
| H3 | The accessibility rules A1 to A6 of `docs/specs/public-pages.md` still hold: one level-1 heading and no skipped level, alt text, one `main`, `nav` and `footer`, keyboard order with no `tabindex` above 0, the skip link first, `aria-current`, the browser titles. |
| H4 | Where a test reads the page's structure, that structure stays: each FAQ answer is the paragraph right after its question, with the next question right after it; the sections of the privacy notice run from one heading to the next with no wrapper between; the note of I2 comes before the first picture; a gallery figure holds only its picture and its caption; the facilities and the events stay list items whose text is exactly the item. |
| H5 | Every existing test passes unchanged. A change that makes one fail is wrong and is reverted. No locked test is edited. |
| H6 | Nothing functional changes: no request, no state, no handler, no address. |

## Dependencies

| Rule | |
|---|---|
| D1 | Added: `tailwindcss` and `@tailwindcss/vite` (development), and, for the shadcn components, `class-variance-authority`, `clsx` and `tailwind-merge`. Nothing else. No Radix package and no icon library: the components that would need them are not used (H2), and Button and Label are copied without the parts that need Radix. The native elements stay because shadcn's Checkbox is a button with `role="checkbox"` instead of an `<input type="checkbox">`, its Select replaces the native list with a custom one, and its Dialog moves the question into a portal and traps focus: each changes what the page is to a screen reader and to the tests that check it (H2, H5). |
| D2 | The shadcn setup files are `frontend/components.json`, `frontend/src/lib/utils.js` and the components under `frontend/src/components/ui/`, in JavaScript like the rest of the frontend. Vite gains the `@tailwindcss/vite` plugin and the `@` alias for `frontend/src`. |
| D3 | The image builds the styles inside the container, with the rest of the frontend (`docs/specs/deploy.md`, M1); nothing built on a developer's machine is copied in. |

## Theme

| Rule | |
|---|---|
| T1 | A light theme only. The stylesheet has no dark variant, no `.dark` class and no `prefers-color-scheme` rule. |
| T2 | The colours are shadcn's theme variables, written in hex on `:root`. Every text colour has a contrast ratio of at least 4.5 to 1 against every background it is used on (WCAG 2.2 AA). |
| T3 | The system font stack. No font is loaded from another site and none is bundled. |
| T4 | The keyboard focus ring is always visible; no rule removes an outline without putting a ring in its place. |
| T6 | **The focus ring is strong enough to see.** It is drawn in `--ring` at full strength, never faded with an opacity, 2px wide, with a 2px gap in `--background` between it and the element, so it shows even around a filled button. `--ring` has a contrast of at least 3 to 1 against `--background`, `--card` and `--muted` (WCAG 2.2, 1.4.11). |
| T7 | **Field edges are strong enough to see.** The border of every text field, text area and list is `--input`, which has a contrast of at least 3 to 1 against `--background` and `--card` (WCAG 2.2, 1.4.11). |
| T8 | **Every text colour pair in use is a theme pair at 4.5 to 1 or more**, including those T2 leaves out: `--destructive-foreground` on `--destructive` (the red buttons; no colour is written into a component directly, so no `text-white`), `--primary` on `--muted` (links in the footer), `--foreground` on `--muted` (table headings and the admin questions), and `--primary-foreground` and `--destructive-foreground` on their buttons' hover shades, which are `--primary` and `--destructive` at 90% over `--background`. |
| T5 | **Exactly one stylesheet loads**: `frontend/src/site.css`, imported once, by `frontend/src/main.jsx`. Its only import is `@import "tailwindcss";`. No other file imports a stylesheet and `index.html` links none. A test is never routed around with a second stylesheet: a rule that no longer fits is retired on the record, with its test. |

## Layout

| Rule | |
|---|---|
| L1 | **Header.** A bar across the top with the site's navigation in a row that wraps on a narrow screen. The current page's link is marked by more than colour alone (weight or underline). |
| L2 | **Footer.** A band at the bottom, set apart from the page, with the centre's details and the two document links. |
| L3 | **Width.** Page content is centred and at most about 64rem wide; the admin page may be wider, for its table. |
| L4 | **Cards.** Each facility and each event is shown as the shadcn `Card` component inside its list item, in a grid that wraps. The list item's text is still exactly the item (H4). |
| L5 | **Gallery.** The pictures and their captions form a grid of as many columns as fit, each at least 16rem wide. |
| L6 | **Forms.** The booking form and the admin login use shadcn's Input, Textarea, Label and Button styling. Labels stay above their fields; tick boxes keep their label beside them. The login sits in a card. |
| L7 | **Admin table.** shadcn's Table styling: row lines, padded cells, a header row set apart. On a narrow screen the table scrolls sideways inside its own box, not the whole page. |
| L8 | **Skip link.** Hidden until it has keyboard focus, then shown at the top left (shadcn's `sr-only` and `focus:not-sr-only`). |

## Tests

`frontend/src/UiTheme.test.jsx` checks what can be checked without a browser: the dependencies of D1, the absence of a dark theme (T1), the contrast of the theme colours (T2), that no font is loaded (T3), that the shadcn components render the native elements (H2), and that the cards, the gallery grid, the admin table box and the skip link carry their styling (L4, L5, L7, L8). Every existing frontend test must still pass (H5). `make ci` builds the image, which proves D3.

## Known limits

- **The gallery test (L5) checks the exact Tailwind class** `grid-cols-[repeat(auto-fill,minmax(16rem,1fr))]`, not the rule "columns at least 16rem wide". It is tied to the implementation: an equivalent grid written another way would fail it. It stays, and the file is locked.
- **Seven theme tests passed before any code** (no Radix, three checks of T5, T1, T3, and the stylesheet half of T4). They guard against something forbidden coming in, and could not fail while there was nothing to forbid.
- **Seven tests of `ThemeContrast.test.js` also passed before their fix**: the three contrast checks of `--ring` (the colour was strong enough; only its opacity was wrong), the check that fields are bordered in `--input`, and three colour pairs of T8 that already passed. They guard those values from now on.
- **`--secondary` and `--secondary-foreground` stay in the theme** although no component uses them: the locked test of T2 checks them.

- **How it looks is checked by eye**, not by a test.
- **The admin dialogs are not modal** in the sense of trapping focus; they were not before either (H2).

## Where this differs

| Earlier document | Now |
|---|---|
| `public-pages.md` ST1 to ST9: one hand-written stylesheet, no framework | ST1 to ST9 retired by ADR 0005; `SiteCss.test.js` retired with them. |

## Confirmed by the author

On 2026-10-14: ADR 0005; the hard constraints H1 to H6; the dependencies of D1 and the reasons for keeping the native elements; the system font stack (T3) and a page width of about 64rem (L3); retiring ST1 to ST9 and `SiteCss.test.js`, which the author deletes by hand; T5, exactly one stylesheet, with the second-stylesheet route rejected for good.

On 2026-10-14, after the review of the implementation: the checks of `UiTheme.test.jsx`, including the `data-slot` checks, the exact-class gallery check (listed under Known limits) and the loose header-and-footer check, and the seven checks that passed before any code; the fixes for the focus ring (T6), the field edges (T7), the colour pairs (T8) and real `Card` use (L4), with their tests in `frontend/src/ThemeContrast.test.js`.
