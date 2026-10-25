# Claude.ai Chat — Design Rules

A practical, build-ready reference for making your own chat frontend *feel* like the Claude chat interface (claude.ai, chat view only): warm paper-like canvas, terracotta accent, serif AI voice, flat hairline-bordered surfaces, quiet motion.

**Contents**

0. Read this first (scope, confidence, legal)
1. Design philosophy
2. Replacing the "AI-generated" look
3. Color system (light + dark)
4. Typography
5. Spacing, sizing, radii, borders, shadows
6. App shell & layout
7. Screens: welcome state and conversation state
8. Components (sidebar, header, composer, messages, markdown, code, buttons, menus, modals, etc.)
9. Iconography
10. Motion & animation
11. Interaction states
12. Accessibility & contrast
13. Responsive / mobile behavior
14. Microcopy & tone
15. Drop-in CSS (tokens, base, components)
16. Tailwind mapping
17. Minimal HTML + JS skeleton
18. Implementation checklist
19. Verifying against the real thing (DevTools guide + known uncertainties)
20. Source notes

---

## 0. Read this first

**What this is.** A design spec reverse-engineered from the public look of the Claude chat product, written so you can copy tokens and rules straight into your own CSS/Tailwind/React project.

**Confidence and sourcing.** Anthropic does not publish the stylesheet of claude.ai. The values below combine:

- Anthropic's published brand palette (e.g. Slate `#141413`, Ivory `#FAF9F5`, Cloud `#B0AEA5`, Light Gray `#E8E6DC`, Clay `#D97757`, Dusty Blue `#6A9BCC`, Sage `#788C5D`),
- public design-token write-ups of Claude's web surfaces (cream canvas, terracotta `#C96442`-family accent, custom serif + sans + mono type family),
- widely observable behavior of the chat UI (layout, component anatomy, interaction patterns).

Values marked **≈** are close approximations, not exact. Claude's UI also changes over time. Section 19 explains how to read the exact current values yourself in your browser's DevTools — do that for anything you want pixel-perfect.

**Marketing site vs chat product.** `claude.com` (marketing) and `claude.ai` (the chat app) share a palette but differ in layout and density. This file targets the **chat product only**.

**Legal / IP note.** For a college project, taking *inspiration* from a visual style is fine. Do not:

- use the Claude name, wordmark or the starburst logo as your own branding (draw your own simple mark and name your product something else),
- ship Anthropic's proprietary fonts (Anthropic Serif / Sans / Mono) — use the free substitutes listed in §4,
- present your project as made by or affiliated with Anthropic.

---

## 1. Design philosophy — the "feel"

If you remember only ten things, remember these:

1. **Warm paper, not a screen.** Backgrounds are a creamy off-white (`#FAF9F5`), never pure white as the page and never cool gray. In dark mode they are warm charcoal (`#262624`), never blue-black.
2. **Every neutral has a yellow-brown undertone.** Grays are "stone/parchment/charcoal", not slate-blue or neutral-gray. This single rule does most of the work.
3. **One accent color: terracotta/clay.** Used sparingly — the send button, the "new chat" affordance, the logo mark, small highlights. Everything else is neutral.
4. **Serif is the AI's voice; sans is the interface's voice.** Assistant replies and the big greeting are in a literary serif. Buttons, menus, sidebar, and the user's message are in a clean sans.
5. **Flat and quiet.** No glow, no glassmorphism, no neon, no gradients on surfaces. Depth comes from a one-step background change and a **hairline border** (0.5px at ~15% opacity), with at most a very soft, large, low-opacity shadow.
6. **The assistant has no bubble and no avatar.** Its text sits directly on the page. Only the *user's* message gets a tinted rounded container.
7. **Generous whitespace and a narrow reading column.** Conversation content lives in a ~768px column; the composer is narrower than the page and floats at the bottom.
8. **Soft corners everywhere** (8 / 12 / 20px), pill shapes only for tiny chips and avatars.
9. **Restrained motion.** 150–250ms ease transitions, subtle fades, a pulsing/rotating logo as the "thinking" indicator. Nothing bounces or glows.
10. **Calm, human copy.** Plain sentences, no exclamation marks, no emoji in UI chrome.

---

## 2. Replacing the "AI-generated" look

Your current frontend has the standard template look (dark background, purple → pink → blue gradients). Here is a direct replacement map.

| Generic AI-template pattern | Replace with (Claude-style) |
|---|---|
| Dark purple/indigo page background | Cream canvas `#FAF9F5` (light) or warm charcoal `#262624` (dark) |
| Purple → pink → blue gradient headings, buttons, borders | Solid text color `#141413`; solid terracotta buttons `#C96442`; no gradients |
| Neon glow / `box-shadow` colored halos | No glow. 0.5px warm hairline border + optional faint shadow `rgba(0,0,0,.04)` |
| Glassmorphism (blur + translucent cards) | Opaque surfaces: white raised card on cream, or one-step darker panel |
| Gradient avatar for the AI, sparkle emoji, robot icon | No avatar for the AI; a tiny clay starburst-style mark used sparingly (your own design) |
| Chat bubbles on both sides, with colored AI bubble | AI: no bubble, plain serif text. User: soft beige bubble `#F0EEE6` |
| Inter/Poppins everywhere, bold headings | Serif for AI text + greeting, sans for UI, weights 400/500 (rarely 600) |
| Uppercase tracking-wide labels, heavy bold | Sentence case, normal tracking, medium weight at most |
| Big rounded-3xl cards with colored borders | 12px radius, 0.5px neutral borders |
| Animated gradient backgrounds, particles, blobs | Plain flat background; motion only on meaningful state changes |
| Cool grays (`slate-*`, `zinc-*`, `gray-*`) | Warm grays defined in §3 only — never use Tailwind's default grays |
| Emoji as icons | Thin-stroke line icons (§9) |
| Bright success green / pure red | Muted semantic colors (§3.6) |

**Quick audit:** search your CSS for `gradient`, `purple`, `violet`, `indigo`, `pink`, `fuchsia`, `blur(`, `drop-shadow`, `slate-`, `zinc-`, `gray-`, `neutral-` and delete or replace every hit.

---

## 3. Color system

### 3.1 Light theme — surfaces

| Token | Hex | Used for |
|---|---|---|
| `--bg-000` | `#FFFFFF` | Raised surfaces: composer, dropdown menus, modals, code blocks, cards |
| `--bg-100` | `#FAF9F5` | **Page canvas** (chat area background) — Anthropic "Ivory Light" |
| `--bg-200` | `#F5F4ED` | Sidebar, secondary panels, subtle section fills |
| `--bg-300` | `#F0EEE6` | **User message bubble**, hover fills, inline code background, chips |
| `--bg-400` | `#E8E6DC` | Pressed/selected fills, strong dividers-as-fill, toggles off-state — Anthropic "Light Gray" |

Alpha overlays for hover/active (work on any surface, preferred over solid hover colors):

| Token | Value |
|---|---|
| `--hover` | `rgba(31, 30, 29, 0.05)` |
| `--active` | `rgba(31, 30, 29, 0.08)` |

### 3.2 Light theme — text

| Token | Hex | Used for |
|---|---|---|
| `--text-100` | `#141413` | Primary text (Anthropic "Slate Dark") — assistant replies, headings, user text |
| `--text-200` | `#3D3D3A` | Secondary text — greeting, sidebar items, labels |
| `--text-300` | `#73726C` | Tertiary/muted — timestamps, helper text, inactive icons |
| `--text-400` | `#83827D` | Placeholder text, disabled labels |
| `--text-500` | `#B0AEA5` | Very faint text/icons (Anthropic "Cloud Medium") |

### 3.3 Light theme — borders

Borders are **warm-black at low opacity**, not solid grays. This keeps them looking right on every surface.

| Token | Value | Used for |
|---|---|---|
| `--border-100` | `rgba(31, 30, 29, 0.08)` | Very subtle dividers (between list sections) |
| `--border-200` | `rgba(31, 30, 29, 0.15)` | **Default border** — composer, buttons, cards, menus |
| `--border-300` | `rgba(31, 30, 29, 0.30)` | Hover/stronger borders, focused inputs |

Width: **0.5px** on high-DPI displays (use `@media (min-resolution: 2dppx)`), **1px** fallback on standard displays.

### 3.4 Dark theme

| Token | Hex | Used for |
|---|---|---|
| `--bg-000` | `#30302E` | Raised surfaces: composer, menus, modals |
| `--bg-100` | `#262624` | **Page canvas** |
| `--bg-200` | `#1F1E1D` | Sidebar, secondary panels |
| `--bg-300` | `#141413` | **User message bubble** (darker than canvas in dark mode), code block backgrounds |
| `--bg-400` | `#3D3D3A` | Pressed/selected fills |
| `--text-100` | `#FAF9F5` | Primary text |
| `--text-200` | `#C2C0B6` | Secondary text |
| `--text-300` | `#9C9A92` | Muted text and icons |
| `--text-400` | `#83827D` | Placeholder |
| `--text-500` | `#5E5D59` | Very faint |
| `--border-100` | `rgba(222, 220, 209, 0.08)` | Subtle dividers |
| `--border-200` | `rgba(222, 220, 209, 0.15)` | Default border |
| `--border-300` | `rgba(222, 220, 209, 0.30)` | Strong/hover border |
| `--hover` | `rgba(250, 249, 245, 0.05)` | Hover overlay |
| `--active` | `rgba(250, 249, 245, 0.08)` | Active overlay |

In dark mode, shadows are essentially invisible — depth comes from stepping the background (`#262624` → `#30302E`) plus the border.

### 3.5 Brand / accent

| Token | Light | Dark | Used for |
|---|---|---|---|
| `--brand` | `#C96442` | `#D97757` | Primary button fill (send), "New chat" circle, key accents |
| `--brand-hover` | `#B5573B` | `#E58A6C` | Hover |
| `--brand-active` | `#A9583E` | `#C96442` | Pressed |
| `--brand-clay` | `#D97757` | `#D97757` | Logo mark / starburst color, "thinking" indicator |
| `--on-brand` | `#FFFFFF` | `#FFFFFF` | Icon/text on brand fill |
| `--brand-tint` | `rgba(217,119,87,0.12)` | `rgba(217,119,87,0.16)` | Subtle highlight washes, selected-state tint |

Extended brand swatches (use *very* sparingly, e.g. illustrations, tags, chart series):

| Name | Hex |
|---|---|
| Kraft ≈ | `#D4A27F` |
| Manilla ≈ | `#EBDBBC` |
| Dusty Blue | `#6A9BCC` |
| Sage Green | `#788C5D` |

### 3.6 Utility colors

| Token | Light | Dark | Used for |
|---|---|---|---|
| `--link` | `#2C84DB` ≈ | `#5B9FE3` ≈ | Links inside assistant messages (underlined), focus ring base |
| `--success` | `#17A34A` | `#4CC278` ≈ | Success toasts, "Copied" check |
| `--warning` | `#EAB308` | `#F2C94C` ≈ | Warnings |
| `--danger` | `#B53333` | `#E5736B` ≈ | Destructive actions, errors, inline-code accent text |

Keep these muted and rare. A chat UI in this style is ~95% neutrals + one terracotta accent.

### 3.7 Syntax-highlighting palette (warm, no purple)

| Token type | Light | Dark |
|---|---|---|
| Plain text | `#141413` | `#FAF9F5` |
| Keyword | `#B4442C` | `#E58A6C` |
| String | `#4D7A3E` | `#A3BE8C` |
| Number / constant | `#3E6C9E` | `#6A9BCC` |
| Function / title | `#8C5A1E` | `#D4A27F` |
| Type / class | `#2F6F7A` | `#7FB8C2` |
| Comment | `#8A887F` | `#83827D` |
| Operator / punctuation | `#73726C` | `#9C9A92` |

### 3.8 Rules for using color

- Page background is always `--bg-100`; sidebar is always one step off (`--bg-200`); raised things (composer, menus) are `--bg-000`.
- Text on canvas: `--text-100` for content, `--text-200` for chrome, `--text-300` for hints.
- Only **one** terracotta element should dominate any screen region (usually the send button).
- Never place text on a terracotta fill other than white.
- Never use pure black `#000` or pure white text on the canvas; use the tokens above.


---

## 4. Typography

### 4.1 The three families

Claude uses a custom type family: a **serif** for the AI's voice and big headings, a **sans** for UI chrome and the user's text, and a **mono** for code.

| Role | Claude uses (proprietary — do not ship) | Free substitute (use this) | Fallback stack |
|---|---|---|---|
| Serif (AI replies, greeting, wordmark) | Anthropic Serif (Tiempos-like) | **Newsreader** (best match for warmth) or **Source Serif 4** / **Lora** | `Georgia, "Times New Roman", serif` |
| Sans (UI, user message, buttons) | Anthropic Sans (Styrene-like) | **Inter** (safe) or **DM Sans** / **Figtree** (slightly friendlier) | `system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif` |
| Mono (code) | Anthropic Mono | **JetBrains Mono** or **IBM Plex Mono** | `ui-monospace, SFMono-Regular, Menlo, Consolas, monospace` |

Google Fonts import (variable fonts, so weights like 330 or 450 work):

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,200..800;1,6..72,200..800&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
```

### 4.2 Type scale (chat product)

| Element | Family | Size / line-height | Weight | Color |
|---|---|---|---|---|
| Welcome greeting ("Good evening, Kanishk") | Serif | 36–40px / 1.2 | 400 (300 also works) | `--text-200` |
| Assistant message body | Serif | 16px / 1.7 (≈27px) — some builds 17px | 400 | `--text-100` |
| User message | Sans | 16px / 1.5 | 400 | `--text-100` |
| Composer text + placeholder | Sans ≈ (see §19 uncertainties) | 16px / 1.5 | 400 | text `--text-100`, placeholder `--text-400` |
| Assistant h1 (inside reply) | Serif or Sans | 24px / 1.3 | 600 | `--text-100` |
| Assistant h2 | same | 20px / 1.35 | 600 | `--text-100` |
| Assistant h3 | same | 18px / 1.4 | 600 | `--text-100` |
| Sidebar chat items | Sans | 14px / 20px | 400 | `--text-200` |
| Sidebar section label ("Recents") | Sans | 12px / 16px | 500 | `--text-400` |
| Buttons, menu items, model selector | Sans | 14px / 20px | 500 (400 for menu rows) | `--text-100` / `--text-200` |
| Chat title in header | Sans | 14px / 20px | 500 | `--text-100` |
| Helper text, disclaimer | Sans | 12px / 16px | 400 | `--text-400` |
| Inline code | Mono | 0.875em (≈14px) | 400 | `--danger` (warm red) ≈ |
| Code block | Mono | 14px / 1.55 | 400 | syntax palette §3.7 |
| Tooltip | Sans | 12px / 16px | 500 | inverted |

### 4.3 Typographic rules

- **Weights:** 400 body, 500 for UI labels/buttons, 600 only for headings inside replies. Avoid 700+.
- **Letter-spacing:** normal everywhere. Never uppercase + wide tracking.
- **Case:** sentence case for all UI labels ("New chat", not "NEW CHAT" or "New Chat").
- **Antialiasing:** `-webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale;`
- **Optical sizing:** `font-optical-sizing: auto` (Newsreader supports it) for nicer serif at 16px vs 40px.
- **Reading measure:** keep assistant text ≤ ~75 characters per line (the 768px column does this naturally).
- **Numbers:** `font-variant-numeric: tabular-nums` inside tables.
- **Text wrapping:** `text-wrap: pretty` on paragraphs, `text-wrap: balance` on the greeting.

---

## 5. Spacing, sizing, radii, borders, shadows

### 5.1 Spacing scale (4px base, Tailwind-compatible)

`4, 8, 12, 16, 20, 24, 32, 40, 48, 64`

Common uses: icon-to-label gap 8px; button padding `0 12px` (height 32px); menu padding 6px; composer inner padding 12–16px; gap between conversation turns 24–32px; paragraph spacing 16px (1em); page gutter 16px mobile / 24px tablet+.

### 5.2 Border radius

| Token | Value | Used for |
|---|---|---|
| `--radius-sm` | 6px | Tooltips, tiny chips, inline code (≈4–6px) |
| `--radius-md` | 8px | **Buttons, icon buttons, sidebar rows, inputs** |
| `--radius-lg` | 12px | **User message bubble**, dropdown menus, cards, code blocks |
| `--radius-xl` | 16px | Modals, large cards |
| `--radius-composer` | 20px (16px acceptable) | **The composer** |
| `--radius-full` | 9999px | Avatars, suggestion pills, toggles |

### 5.3 Shadows (use sparingly)

| Token | Light value | Used for |
|---|---|---|
| `--shadow-composer` | `0 4px 20px rgba(0,0,0,0.035)` | Composer at rest (plus 0.5px border) |
| `--shadow-composer-hover` | `0 4px 20px rgba(0,0,0,0.05)` | Composer hover |
| `--shadow-composer-focus` | `0 4px 24px rgba(0,0,0,0.075)` | Composer focus-within |
| `--shadow-menu` | `0 4px 16px rgba(0,0,0,0.08)` | Dropdowns, popovers |
| `--shadow-modal` | `0 8px 32px rgba(0,0,0,0.12)` | Modals |

Dark mode: set all of these to `none` (or ≤ 0.3 alpha black) and rely on border + bg step.

### 5.4 Borders

- Default: `0.5px solid var(--border-200)` (1px fallback on 1× screens).
- Hover on bordered controls: `--border-300`.
- Dividers between sections: `--border-100`.
- **No colored borders.** No gradient borders. No 2px+ borders except a 2px left rule on blockquotes and the sidebar-selected indicator (if you add one).

### 5.5 Z-index ladder

`base 0 → sticky header/composer fade 10 → sidebar overlay (mobile) 40 → dropdown/popover 50 → modal backdrop 60 → modal 61 → toast 70 → tooltip 80`

---

## 6. App shell & layout

```
┌────────────┬──────────────────────────────────────────────┐
│            │  Header (48px): chat title ▾          [Share] │
│  Sidebar   ├──────────────────────────────────────────────┤
│  288px     │                                              │
│  (bg-200)  │          Conversation column                 │
│            │          max-width 768px, centered           │
│  New chat  │                                              │
│  Chats     │          [user bubble]                       │
│  Projects  │          Assistant serif text …              │
│  Recents…  │                                              │
│            │      ┌────────────────────────────┐          │
│  ───────   │      │ Composer (max 672–720px)   │          │
│  Profile   │      └────────────────────────────┘          │
│            │       Disclaimer (12px, centered)            │
└────────────┴──────────────────────────────────────────────┘
```

| Region | Spec |
|---|---|
| App container | `display:flex; height:100dvh; background: var(--bg-100); color: var(--text-100)` |
| Sidebar (expanded) | width **≈288px**, `bg-200`, right border 0.5px `--border-100`, padding 8px, flex column |
| Sidebar (collapsed) | icon rail ≈ **48–52px** wide, same bg |
| Header | height **48px**, sticky top, padding `0 16px`, transparent over canvas (or canvas color with a bottom fade) |
| Scroll area | only the message list scrolls; `overflow-y:auto`, canvas background |
| Conversation column | `max-width: 48rem (768px)`, `margin: 0 auto`, padding `0 16px` (mobile) / `0 24px` (≥768px) |
| Composer wrapper | sticky bottom; `max-width: 42–45rem (672–720px)`; centered; padding `0 16px 12px` |
| Composer fade | 24–32px gradient from transparent to `--bg-100` above the composer so text fades out instead of cutting off (the *only* gradient in the UI) |
| Disclaimer line | below composer, 12px, `--text-400`, centered, 8px top margin |
| Scroll-to-bottom button | 32–36px circle, `bg-000`, 0.5px border, `shadow-menu`, centered above composer, down-arrow icon 16px |

---

## 7. Screens

### 7.1 Welcome / empty state (new chat)

Vertical stack, centered horizontally, positioned slightly above true center (~40% from top):

1. **Greeting row** — your own small clay mark (28–36px) + greeting text on one line, gap 12–16px, centered. Text is serif 36–40px, weight 400, `--text-200`, time-based ("Good morning / afternoon / evening, {name}"). Margin-bottom 24–32px.
2. **Composer** — same component as in conversation, width 672–720px, slightly taller on this screen (textarea min-height ≈ 52–56px).
3. **Suggestion chips** (optional) — a centered wrapping row 16–24px below the composer; each chip: height 36px, padding `0 14px`, 14px sans, `--text-300`, 0.5px `--border-200` border, `--radius-lg` (or full), icon 16px + label, hover `--hover` bg and text `--text-100`. Typical labels: *Write, Learn, Code, Life stuff, …*.
4. **No heavy hero artwork.** No illustrations, no gradient orbs. The whitespace *is* the design.

### 7.2 Conversation state

1. Header with chat title (and Share).
2. Message list in the 768px column. Each turn = user bubble then assistant text.
3. Composer pinned at bottom, with fade above it.
4. Disclaimer text under the composer.
5. When the user sends: the welcome block disappears, the composer animates down to the bottom (200–300ms ease-out), the user bubble fades in, a clay starburst/"thinking" mark appears where the reply will start.

### 7.3 Loading / thinking state

- A small (16–20px) clay mark below the user's message, **rotating slowly or pulsing** (opacity 0.5 ↔ 1, scale 0.95 ↔ 1.05, ~1.2–1.6s loop).
- Optional text next to it ("Thinking…") in 14px `--text-300` with a gentle left-to-right shimmer.
- When tokens start arriving, the mark stays at the bottom-left of the message until streaming ends, then becomes static/small.

### 7.4 Error state

- Inline in the message area, not a red banner: 14px sans text in `--text-200`, optional small `--danger` icon, a ghost "Retry" button. Background stays neutral; maybe a 0.5px `--danger` border at 30% opacity on a `bg-000` card if you need emphasis.

---

## 8. Components

### 8.1 Sidebar

| Part | Spec |
|---|---|
| Container | `bg-200`, width ≈288px, `padding: 8px`, vertical flex, right border 0.5px `--border-100` |
| Top row | Collapse/expand icon button (32px) on the left; wordmark in **serif ≈ 22px**, weight 400–500, `--text-100` (use *your* product name) |
| **New chat** row | Height 36px, `padding 0 8px`, `--radius-md`. Left: **24px circle filled `--brand`** with a white "+" (14px). Label "New chat" 14px/500, color `--brand` (light) — hover bg `--hover` |
| Nav rows (Chats, Projects, Artifacts, …) | Height 32–36px, icon 20px `--text-300` + label 14px `--text-200`, gap 12px, `--radius-md`, hover `--hover` |
| Section label ("Recents") | 12px/500 `--text-400`, padding `16px 8px 4px` |
| Chat item | Height 32px, `padding 0 8px`, 14px `--text-200`, single-line truncate with a **right-edge fade mask** (gradient from transparent to row bg over ~24px) instead of an ellipsis; hover `--hover`; **selected** = `--active` (or `--bg-300`) + text `--text-100`; on hover a "⋯" icon button (24px) appears at the right |
| Footer / profile | Pinned bottom, `padding 8px`, border-top `--border-100`. Avatar 32px circle (bg `#3D3D3A`, initial in `#FAF9F5`, 14px/500) + name 14px/500 + plan label 12px `--text-300`. Click opens a menu (settings, theme, log out) |
| Collapse behavior | Transition `width 200ms ease`; labels fade out first (opacity 0 in 100ms) then width shrinks |

### 8.2 Header

- Left (mobile): sidebar toggle. Center-left (desktop): chat title as a ghost button — 14px/500 with a small chevron-down; hover `--hover`, `--radius-md`, padding `4px 8px`; title truncates at ~40ch.
- Right: **Share** button — outlined (0.5px `--border-200`), height 32px, padding `0 12px`, `--radius-md`, 14px/500; hover bg `--hover` and border `--border-300`.
- Background: transparent over the canvas; when the list scrolls beneath, add a 16–24px fade at the bottom edge (not a hard border).

### 8.3 Composer (the signature element)

**Anatomy**

```
┌───────────────────────────────────────────────────────┐
│ [attachment chips / thumbnails — optional]            │
│ How can I help you today?                    ← textarea│
│                                                       │
│ [+]  [tools…]                  Model ⌄   [ ↑ send ]   │
└───────────────────────────────────────────────────────┘
          Disclaimer text (outside, below)
```

| Property | Value |
|---|---|
| Container | `background: var(--bg-000); border: 0.5px solid var(--border-200); border-radius: 20px; box-shadow: var(--shadow-composer); padding: 12px 12px 10px` |
| Hover | border → `--border-300`, shadow → `--shadow-composer-hover` |
| Focus-within | shadow → `--shadow-composer-focus`; border stays neutral (no colored glow ring) |
| Transition | `box-shadow 200ms ease, border-color 200ms ease` |
| Textarea | no border/outline/background; `padding: 6px 8px 0`; 16px/1.5; min-height 52px (welcome) / 40px (chat); **auto-grows** to max-height ≈ 384px (24rem), then scrolls; `resize: none` |
| Placeholder | `--text-400`; copy e.g. "How can I help you today?" / "Reply to…" (write your own) |
| Toolbar row | `display:flex; align-items:center; justify-content:space-between; margin-top: 8px` |
| Left tools | Icon buttons 32×32, `--radius-md`, icon 18–20px `--text-300`, hover `--hover` + `--text-100`. The "+" (attach) is typically the first |
| Model selector (right) | Ghost text button, 14px/400 `--text-300` + chevron-down 12px; hover `--hover`; opens a menu |
| **Send button** | 32×32px, `--radius-md` (8px), bg `--brand`, white up-arrow icon 16px (stroke 2). Hover `--brand-hover`. Active `--brand-active` + `scale(0.96)`. **Disabled (empty input): same fill at opacity 0.3, `cursor: default`.** |
| Stop button (while streaming) | Same 32px button; icon becomes a filled rounded square (≈12px); keeps brand fill |
| Attachments | Chips/cards above textarea: 0.5px border, `--radius-lg`, bg `--bg-100`, remove "×" button appearing on hover; images as 64–80px thumbnails with 8–12px radius |
| Keyboard | Enter = send, Shift+Enter = newline, Esc = blur |
| Position | Welcome: centered in content flow. Conversation: pinned bottom with page-fade above |

### 8.4 Messages

**User message**

- Container: `background: var(--bg-300); border-radius: 12px; padding: 10px 16px;` `width: fit-content; max-width: 100%` (≈ 85% on wide screens).
- Font: sans 16px/1.5, `--text-100`, `white-space: pre-wrap; word-break: break-word`.
- Alignment: left-aligned in the column on web (optionally with a 28–32px initial-avatar circle); the mobile apps right-align the bubble. Pick one and stay consistent — both read as "Claude-like" (see §19).
- Hover affordances: a small action row (Edit pencil, Copy) fades in beneath/beside the bubble — 28–32px ghost icon buttons, `--text-300`.
- Long messages collapse with a "Show more" fade after ~12 lines (optional).

**Assistant message**

- **No bubble, no background, no avatar.** Text directly on `--bg-100`.
- Font: **serif**, 16px/1.7, `--text-100`, weight 400; full column width.
- Paragraph spacing: `margin: 0 0 16px` (last child 0).
- Top margin from the preceding user bubble: 16–24px. Gap between full turns: 24–32px.
- Streaming: append text as it arrives with no cursor block; show the small clay mark at the bottom-left of the message until complete (see §7.3).
- **Action bar** below the message: icon buttons 32×32 (Copy, thumbs-up, thumbs-down, Retry), icon 16–18px `--text-300`, hover `--hover` + `--text-100`, gap 2–4px. Always visible on the latest reply, hover-only on older ones. Copy → icon swaps to a check for ~1.5s.
- Thinking / reasoning block (optional): a collapsible row "Thought process ›" — 14px `--text-300`, chevron rotates 90° on open; content: 14px/1.6 sans, `--text-300`, with a 2px left rule `--border-200` and 16px left padding.

### 8.5 Markdown rendering inside assistant messages

| Element | Rule |
|---|---|
| Paragraph | 16px/1.7, margin-bottom 16px |
| Headings | Weight 600, color `--text-100`, margin `24px 0 8px` (h1/h2) / `20px 0 8px` (h3); no underline/borders; sizes in §4.2 |
| Bold / italic | `font-weight: 600` / true italic (use a font with real italics — Newsreader has them) |
| Links | `--link`, `text-decoration: underline; text-underline-offset: 2px; text-decoration-thickness: 1px`; hover → thicker (2px) or darker |
| Unordered list | `padding-left: 24px; list-style: disc` (markers `--text-300`); item gap 4–6px; nested lists `margin-top: 6px` |
| Ordered list | same, decimal markers `--text-300` |
| Blockquote | `border-left: 2px solid var(--border-300); padding-left: 16px; color: var(--text-200)`; no italics, no background |
| Horizontal rule | `1px (0.5px hi-dpi) solid var(--border-200); margin: 24px 0` |
| Table | wrapper `overflow-x:auto`, border 0.5px `--border-200`, `--radius-lg`; header row bg `--bg-300` at ~60%, 14px/600; cells 14px, padding `8px 12px`, row divider `--border-100`; `tabular-nums`; no zebra stripes |
| Inline code | mono ≈14px, `background: var(--bg-300)`, `color: var(--danger)` ≈ (warm red, light mode; dark mode uses a lighter red), `padding: 1px 6px`, `border-radius: 6px`, optional 0.5px `--border-100` border |
| Images | `max-width: 100%; border-radius: 12px` |
| Math (if used) | KaTeX, inherits text color |

### 8.6 Code blocks

| Part | Spec |
|---|---|
| Container | `border: 0.5px solid var(--border-200); border-radius: 12px; overflow: hidden; margin: 16px 0`. Background: **light** `--bg-000` (white-ish) ≈ / **dark** `--bg-300` (`#141413`) ≈ |
| Header strip | Height 36–40px, padding `0 12px 0 16px`, language label 12px sans `--text-300` (lowercase) at left; **Copy** button at right: ghost, 12–14px `--text-300`, icon 14–16px; label switches to "Copied" with a check (success color) for 1.5–2s |
| Body | `padding: 12px 16px 16px; overflow-x: auto`; mono 14px/1.55; `tab-size: 2`; no line numbers by default |
| Scrollbar | thin, warm (see 8.12) |
| Highlighter | Prism/Shiki with the warm palette in §3.7; do **not** use stock purple/pink themes (Dracula, Night Owl, Synthwave) |

### 8.7 Buttons

| Variant | Spec |
|---|---|
| **Primary** | bg `--brand`, text `--on-brand`, height 36px (32px compact), padding `0 16px`, `--radius-md`, 14px/500. Hover `--brand-hover`; active `--brand-active` + `scale(0.98)`; disabled opacity 0.4–0.5 |
| **Secondary / outlined** | transparent bg, 0.5px `--border-200`, text `--text-100`, same size. Hover bg `--hover`, border `--border-300` |
| **Ghost** | no border/bg, text `--text-200`. Hover bg `--hover`, text `--text-100` |
| **Dark/neutral solid** (e.g. confirm dialogs) | bg `--text-100`, text `--bg-100`, hover opacity .9 |
| **Danger** | text `--danger` on ghost/outlined; or solid `--danger` bg with white text for confirmations |
| **Icon button** | 32×32 (28 compact, 40 touch), `--radius-md`, icon 18–20px `--text-300` → hover `--text-100` + `--hover` |
| **Pill / chip button** | height 32–36px, `--radius-full` or `--radius-lg`, 0.5px border, 14px, icon 16px |
| Press feedback | `transition: transform 100ms, background-color 150ms; :active { transform: scale(0.98) }` |

### 8.8 Inputs (settings, modals, search)

- Height 40px, padding `0 12px`, bg `--bg-000`, 0.5px `--border-200`, `--radius-md` (8px) — 12px for large fields.
- Text 16px (prevents iOS zoom), placeholder `--text-400`.
- Hover: `--border-300`. Focus: border `--border-300` + 2px focus ring `rgba(44,132,219,0.35)` ≈ (or a 2px `--brand-tint` ring) — keep it subtle.
- Labels above field: 14px/500 `--text-200`, 6–8px gap. Helper text 12px `--text-300`. Error text 12px `--danger`.
- Toggle switch: 36×20px track, off `--bg-400`, on `--brand`; 16px white thumb; 150ms transition.
- Checkbox/radio: 16px, 0.5px border, checked fill `--brand` with white check.
- Select/segmented control: container `--bg-300`, `--radius-md`, 2px padding; selected segment `--bg-000` + 0.5px border + faint shadow; text 14px/500.

### 8.9 Dropdown menus, popovers, model selector

- Container: `bg-000`, 0.5px `--border-200`, `border-radius: 12px`, `padding: 6px`, `box-shadow: var(--shadow-menu)`, min-width 200–240px, appears 4–8px from trigger.
- Items: height 32–36px, padding `0 10px`, `--radius-md` (8px), 14px/400 `--text-200`, icon 16–18px `--text-300` + 10–12px gap; hover `--hover` & text `--text-100`; selected item shows a check at right.
- Secondary description line under label: 12px `--text-300` (used by the model selector rows).
- Separators: 0.5px `--border-100`, margin `6px -6px`.
- Destructive item: text `--danger`.
- Animation: fade + 4px translate-y + `scale(0.98 → 1)`, 120–150ms ease-out; exit 100ms.

### 8.10 Modals / dialogs

- Backdrop: `rgba(20, 20, 19, 0.45)` (no heavy blur; at most `backdrop-filter: blur(2px)` — optional).
- Panel: `bg-000` (light) / `#30302E` (dark), `border-radius: 16px`, padding 24px, max-width 448–512px (settings: up to ~720px), 0.5px border, `--shadow-modal`.
- Title: serif 20–24px/500 (or sans 18px/600). Description 14px `--text-300`.
- Footer buttons right-aligned, 8–12px gap: ghost "Cancel" + primary action.
- Enter animation: 200ms fade + `scale(0.97 → 1)`; Esc and backdrop click close.

### 8.11 Tooltips, toasts, badges

- **Tooltip:** bg `--text-100` (inverted), text `--bg-100`, 12px/500, padding `4px 8px`, `--radius-sm`, delay 400–600ms, 100ms fade.
- **Toast:** bottom-center or bottom-right, `bg-000`, 0.5px border, `--radius-lg`, `--shadow-menu`, 14px text, padding `12px 16px`, auto-dismiss 3–5s, slide-up + fade.
- **Badge / tag:** 12px/500, padding `2px 8px`, `--radius-sm` or full, bg `--bg-300`, text `--text-200`. Accent badge: bg `--brand-tint`, text `--brand`.

### 8.12 Scrollbars

```css
* { scrollbar-width: thin; scrollbar-color: rgba(31,30,29,.25) transparent; }
[data-theme="dark"] * { scrollbar-color: rgba(222,220,209,.25) transparent; }
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-thumb { background: rgba(31,30,29,.25); border-radius: 9999px; border: 2px solid transparent; background-clip: content-box; }
::-webkit-scrollbar-track { background: transparent; }
```

### 8.13 Avatars

- User: 28–32px circle, bg `#3D3D3A` (dark gray-brown), initial in `#FAF9F5`, 14px/500. In dark mode: bg `#C2C0B6`, initial `#141413` ≈.
- Assistant: none. Optional 16–20px clay mark only as the streaming indicator.

### 8.14 Skeleton / loading placeholders

- Skeleton bars: `bg-300`, `--radius-md`, height 12–16px, shimmer `linear-gradient(90deg, transparent, rgba(255,255,255,.5), transparent)` 1.4s infinite (dark: `rgba(250,249,245,.06)`). This is a *loading* effect only, never decoration.

---

## 9. Iconography

- **Style:** thin-to-regular line icons, rounded caps/joins, ~1.5px stroke at 20px. No filled/duotone icons except the send arrow's solid button and the stop square.
- **Free sets that match:** **Phosphor (Regular)** is closest; **Lucide** at stroke-width 1.5 is a good second.
- **Sizes:** 16px (inline/menus/actions), 18–20px (sidebar nav, toolbar), 24px (rare, empty states).
- **Color:** inherit `currentColor`; default `--text-300`, hover `--text-100`. Never colored icons except brand mark, success check, danger.
- **Logo mark:** Claude's mark is a clay-colored radial starburst. **Do not copy it.** Make your own simple geometric mark (e.g. an 8-point asterisk or a simple arc/dot) in `--brand-clay` `#D97757`, used at 16–36px in three places only: greeting, streaming indicator, favicon/wordmark.
- **Common icons you'll need:** plus, arrow-up (send), square (stop), copy, check, thumbs-up, thumbs-down, rotate-ccw (retry), pencil (edit), more-horizontal, chevron-down/right, panel-left (sidebar), search, settings/sliders, paperclip, share, trash, star, folder, message-square, sun/moon.

---

## 10. Motion & animation

### 10.1 Principles

Motion exists to explain state changes, not to decorate. Keep it short, ease-out, and low-amplitude.

### 10.2 Tokens

| Token | Value |
|---|---|
| `--ease-out` | `cubic-bezier(0.16, 1, 0.3, 1)` (or plain `ease-out`) |
| `--ease-in-out` | `cubic-bezier(0.4, 0, 0.2, 1)` |
| `--dur-fast` | 100ms (press, tooltips exit) |
| `--dur-base` | 150ms (hover, menus, color changes) |
| `--dur-slow` | 200–250ms (sidebar width, modal, composer move) |
| `--dur-slower` | 300ms (message entrance, page-level) |

### 10.3 Specific behaviors

| Interaction | Animation |
|---|---|
| Hover on buttons/rows | `background-color`/`color` 150ms |
| Press | `transform: scale(0.98)` 100ms |
| Message entrance | user bubble + assistant block: opacity 0→1 and `translateY(6px→0)`, 250–300ms ease-out |
| Streaming text | no per-character typewriter effect; append chunks as they arrive (a very light 100–150ms fade-in per chunk is fine) |
| Thinking mark | 1.2–1.6s infinite loop: slow rotation (360° over ~3s) *or* pulse (opacity .5↔1, scale .95↔1.05) |
| Thinking text shimmer | background-clip text, gradient sweep 1.8s linear infinite |
| Composer welcome → chat | transform/position transition 250ms ease-out |
| Sidebar collapse | width 200ms ease; labels opacity 100ms |
| Menu open | fade + translateY(4px→0) + scale(.98→1), 120–150ms; close 100ms |
| Modal open | backdrop fade 150ms; panel fade + scale(.97→1) 200ms |
| Chevron rotate | 150ms ease |
| Copy success | icon cross-fade to check 100ms; revert after ~1.5s |
| Scroll-to-bottom button | fade + translateY(8px→0) 150ms |

### 10.4 Reduced motion

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: .01ms !important; animation-iteration-count: 1 !important; transition-duration: .01ms !important; scroll-behavior: auto !important; }
}
```

---

## 11. Interaction states (all interactive elements)

| State | Rule |
|---|---|
| Rest | Neutral color tokens only |
| Hover | `--hover` overlay (5% warm black / 5% warm white) and text one step darker; border → `--border-300` where bordered; `cursor: pointer` |
| Active/pressed | `--active` overlay, `scale(0.98)` for buttons |
| Focus-visible | `outline: 2px solid rgba(44,132,219,.55); outline-offset: 2px;` (keyboard only; mouse focus shows nothing extra). Inside the composer use the shadow change instead of an outline |
| Selected | `--active` background + `--text-100`; optional check icon |
| Disabled | `opacity: .4–.5` (send button `.3`), `pointer-events: none` or `cursor: not-allowed`, no hover changes |
| Loading | Replace the label/icon with the clay mark or a 14px spinner (stroke `currentColor`, 1.5px, 700ms rotation) |
| Error | `--danger` text/icon and a 0.5px `--danger` border at ~50% alpha; helper text beneath |
| Text selection | optional: `::selection { background: rgba(217,119,87,.25); }` |

---

## 12. Accessibility & contrast

- Body text `#141413` on `#FAF9F5` ≈ 17:1; `--text-300 #73726C` on `#FAF9F5` ≈ 4.5:1 (OK for 14px+); do **not** use `--text-400/500` for essential information.
- White on `--brand #C96442` ≈ 3.9:1 — passes the 3:1 bar for icons and UI components, but is below 4.5:1 for small text. If a brand-filled button carries small text and you need AA, use `#B5573B` (≈ 4.8:1) as the fill.
- Hit targets: minimum 32px desktop, 44px on touch (pad with transparent hit area if the visual is smaller).
- Always keep visible keyboard focus (see §11).
- Provide `aria-label`s on icon buttons, `aria-live="polite"` on the streaming message container, `role="log"` on the message list, and `aria-busy="true"` while streaming.
- Respect `prefers-color-scheme` (default) and let the user override with a toggle (Light / Auto / Dark).
- Respect `prefers-reduced-motion` (§10.4).
- Never rely on color alone for state (pair with icon/text).

---

## 13. Responsive / mobile behavior

| Breakpoint | Behavior |
|---|---|
| `< 640px` (phone) | Sidebar becomes an off-canvas drawer (width `min(85vw, 320px)`, backdrop `rgba(20,20,19,.4)`, slide 200ms). Header shows a menu button. Page gutters 12–16px. Composer full-width with 8–12px side margins, `padding-bottom: env(safe-area-inset-bottom)`. All inputs ≥16px font size. Suggestion chips scroll horizontally or wrap. |
| `640–767px` | Same drawer sidebar; gutters 16–24px |
| `≥ 768px` | Persistent sidebar (collapsible); conversation column 768px max |
| `≥ 1024px` | Comfortable default layout as in §6 |
| `≥ 1280px` | Same widths — content does **not** stretch; extra space is simply cream canvas |

Other mobile rules:

- Use `100dvh` (not `100vh`) so the composer isn't hidden by browser bars.
- Action bars on messages are always visible on touch (no hover).
- Long code blocks scroll horizontally inside the block; the page never scrolls sideways.

---

## 14. Microcopy & tone

The voice is calm, plain, and warm. Sentence case. No exclamation points, no emoji in chrome, no hype.

| Place | Example (write your own variants) |
|---|---|
| Greeting | "Good morning, {name}" / "Good afternoon, {name}" / "Good evening, {name}" (time-based; occasional friendly variants like "Welcome back, {name}") |
| Composer placeholder (new chat) | "How can I help you today?" |
| Composer placeholder (in chat) | "Reply…" |
| Disclaimer under composer | "{Product} can make mistakes. Please double-check responses." |
| New chat button | "New chat" |
| Empty recents | "Your chats will appear here" |
| Copy feedback | "Copied" |
| Errors | "Something went wrong. Please try again." + Retry |
| Delete confirm | Title "Delete chat?", body "This will permanently delete this conversation.", buttons "Cancel" / "Delete" |
| Share | "Share" |
| Loading | "Thinking…" (14px, `--text-300`, shimmer) |

---

## 15. Drop-in CSS

### 15.1 `tokens.css`

```css
:root {
  color-scheme: light;

  /* surfaces */
  --bg-000: #FFFFFF;
  --bg-100: #FAF9F5;
  --bg-200: #F5F4ED;
  --bg-300: #F0EEE6;
  --bg-400: #E8E6DC;

  /* text */
  --text-100: #141413;
  --text-200: #3D3D3A;
  --text-300: #73726C;
  --text-400: #83827D;
  --text-500: #B0AEA5;

  /* borders + overlays (warm black, low alpha) */
  --border-100: rgba(31, 30, 29, 0.08);
  --border-200: rgba(31, 30, 29, 0.15);
  --border-300: rgba(31, 30, 29, 0.30);
  --hover:      rgba(31, 30, 29, 0.05);
  --active:     rgba(31, 30, 29, 0.08);
  --border-w: 1px;

  /* brand */
  --brand:        #C96442;
  --brand-hover:  #B5573B;
  --brand-active: #A9583E;
  --brand-clay:   #D97757;
  --on-brand:     #FFFFFF;
  --brand-tint:   rgba(217, 119, 87, 0.12);

  /* utility */
  --link: #2C84DB;
  --success: #17A34A;
  --warning: #EAB308;
  --danger: #B53333;
  --focus-ring: rgba(44, 132, 219, 0.55);

  /* code */
  --code-bg: #FFFFFF;
  --code-inline-text: #B53333;
  --tok-keyword: #B4442C;
  --tok-string: #4D7A3E;
  --tok-number: #3E6C9E;
  --tok-func: #8C5A1E;
  --tok-type: #2F6F7A;
  --tok-comment: #8A887F;
  --tok-punct: #73726C;

  /* shape */
  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-xl: 16px;
  --radius-composer: 20px;
  --radius-full: 9999px;

  /* elevation */
  --shadow-composer:       0 4px 20px rgba(0, 0, 0, 0.035);
  --shadow-composer-hover: 0 4px 20px rgba(0, 0, 0, 0.05);
  --shadow-composer-focus: 0 4px 24px rgba(0, 0, 0, 0.075);
  --shadow-menu:           0 4px 16px rgba(0, 0, 0, 0.08);
  --shadow-modal:          0 8px 32px rgba(0, 0, 0, 0.12);

  /* type */
  --font-serif: "Newsreader", "Source Serif 4", Georgia, "Times New Roman", serif;
  --font-sans:  "Inter", system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  --font-mono:  "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;

  /* motion */
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --dur-fast: 100ms;
  --dur-base: 150ms;
  --dur-slow: 220ms;
}

@media (min-resolution: 2dppx) {
  :root { --border-w: 0.5px; }
}

[data-theme="dark"] {
  color-scheme: dark;

  --bg-000: #30302E;
  --bg-100: #262624;
  --bg-200: #1F1E1D;
  --bg-300: #141413;
  --bg-400: #3D3D3A;

  --text-100: #FAF9F5;
  --text-200: #C2C0B6;
  --text-300: #9C9A92;
  --text-400: #83827D;
  --text-500: #5E5D59;

  --border-100: rgba(222, 220, 209, 0.08);
  --border-200: rgba(222, 220, 209, 0.15);
  --border-300: rgba(222, 220, 209, 0.30);
  --hover:      rgba(250, 249, 245, 0.05);
  --active:     rgba(250, 249, 245, 0.08);

  --brand:        #D97757;
  --brand-hover:  #E58A6C;
  --brand-active: #C96442;
  --brand-tint:   rgba(217, 119, 87, 0.16);

  --link: #5B9FE3;
  --success: #4CC278;
  --warning: #F2C94C;
  --danger: #E5736B;

  --code-bg: #141413;
  --code-inline-text: #E5736B;
  --tok-keyword: #E58A6C;
  --tok-string: #A3BE8C;
  --tok-number: #6A9BCC;
  --tok-func: #D4A27F;
  --tok-type: #7FB8C2;
  --tok-comment: #83827D;
  --tok-punct: #9C9A92;

  --shadow-composer: none;
  --shadow-composer-hover: none;
  --shadow-composer-focus: none;
  --shadow-menu: 0 4px 16px rgba(0, 0, 0, 0.3);
  --shadow-modal: 0 8px 32px rgba(0, 0, 0, 0.4);
}
```

Set the theme before first paint to avoid a flash (put in `<head>`):

```html
<script>
  (function () {
    var saved = localStorage.getItem('theme'); // 'light' | 'dark' | null (auto)
    var dark = saved ? saved === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
    document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
  })();
</script>
```

### 15.2 `base.css`

```css
*, *::before, *::after { box-sizing: border-box; }
html, body { height: 100%; }
body {
  margin: 0;
  background: var(--bg-100);
  color: var(--text-100);
  font-family: var(--font-sans);
  font-size: 16px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}
button { font: inherit; color: inherit; background: none; border: 0; padding: 0; cursor: pointer; }
textarea, input { font: inherit; color: inherit; }
a { color: var(--link); }
:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 2px; }
::selection { background: rgba(217, 119, 87, 0.25); }

* { scrollbar-width: thin; scrollbar-color: var(--border-300) transparent; }
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-thumb { background: var(--border-300); border-radius: 9999px; border: 2px solid transparent; background-clip: content-box; }

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: .01ms !important; animation-iteration-count: 1 !important; transition-duration: .01ms !important; }
}
```

### 15.3 `components.css`

```css
/* ---------- shell ---------- */
.app { display: flex; height: 100dvh; }
.sidebar {
  width: 288px; flex: none; display: flex; flex-direction: column; padding: 8px;
  background: var(--bg-200); border-right: var(--border-w) solid var(--border-100);
}
.main { flex: 1; min-width: 0; display: flex; flex-direction: column; background: var(--bg-100); }
.header { height: 48px; flex: none; display: flex; align-items: center; justify-content: space-between; padding: 0 16px; }
.stage { flex: 1; min-height: 0; display: flex; flex-direction: column; }
.scroll { flex: 1; overflow-y: auto; }
.column { max-width: 48rem; margin: 0 auto; padding: 8px 24px 32px; }

/* ---------- sidebar ---------- */
.brand-word { font-family: var(--font-serif); font-size: 22px; font-weight: 450; padding: 8px; }
.sb-row {
  display: flex; align-items: center; gap: 12px; width: 100%; height: 36px; padding: 0 8px;
  border-radius: var(--radius-md); font-size: 14px; color: var(--text-200); text-align: left;
  transition: background-color var(--dur-base);
}
.sb-row:hover { background: var(--hover); color: var(--text-100); }
.sb-row[aria-current="true"] { background: var(--active); color: var(--text-100); }
.sb-new { color: var(--brand); font-weight: 500; }
.sb-new .plus { width: 24px; height: 24px; border-radius: 50%; background: var(--brand); color: var(--on-brand); display: grid; place-items: center; font-size: 16px; line-height: 1; }
.sb-label { font-size: 12px; font-weight: 500; color: var(--text-400); padding: 16px 8px 4px; }
.sb-chat { height: 32px; overflow: hidden; white-space: nowrap;
  -webkit-mask-image: linear-gradient(90deg, #000 calc(100% - 24px), transparent);
          mask-image: linear-gradient(90deg, #000 calc(100% - 24px), transparent); }
.sb-footer { margin-top: auto; padding-top: 8px; border-top: var(--border-w) solid var(--border-100); }
.avatar { width: 32px; height: 32px; border-radius: 50%; background: #3D3D3A; color: #FAF9F5; display: grid; place-items: center; font-size: 14px; font-weight: 500; flex: none; }
[data-theme="dark"] .avatar { background: #C2C0B6; color: #141413; }

/* ---------- welcome ---------- */
.welcome { display: flex; align-items: center; justify-content: center; gap: 14px; margin-bottom: 28px; padding: 0 16px; }
.greeting { font-family: var(--font-serif); font-size: clamp(30px, 4vw, 40px); line-height: 1.2; font-weight: 400; color: var(--text-200); margin: 0; text-wrap: balance; }
.mark { width: 32px; height: 32px; color: var(--brand-clay); flex: none; }
.main[data-empty="false"] .welcome, .main[data-empty="false"] .chips { display: none; }
.main[data-empty="true"] .scroll { display: none; }
.main[data-empty="true"] .stage { justify-content: center; padding-bottom: 8vh; }

/* ---------- composer ---------- */
.composer-wrap { width: 100%; max-width: 45rem; margin: 0 auto; padding: 0 16px 12px; position: relative; }
.main[data-empty="false"] .composer-wrap::before {
  content: ""; position: absolute; left: 0; right: 0; top: -28px; height: 28px; pointer-events: none;
  background: linear-gradient(to top, var(--bg-100), transparent);
}
.composer {
  background: var(--bg-000); border: var(--border-w) solid var(--border-200); border-radius: var(--radius-composer);
  box-shadow: var(--shadow-composer); padding: 12px 12px 10px;
  transition: box-shadow 200ms ease, border-color 200ms ease;
}
.composer:hover { border-color: var(--border-300); box-shadow: var(--shadow-composer-hover); }
.composer:focus-within { box-shadow: var(--shadow-composer-focus); }
.composer textarea {
  display: block; width: 100%; min-height: 52px; max-height: 384px; resize: none; border: 0; outline: 0; background: transparent;
  padding: 6px 8px 0; font-size: 16px; line-height: 1.5; color: var(--text-100);
}
.composer textarea::placeholder { color: var(--text-400); }
.toolbar { display: flex; align-items: center; justify-content: space-between; margin-top: 8px; }
.toolbar-right { display: flex; align-items: center; gap: 4px; }
.icon-btn { width: 32px; height: 32px; display: grid; place-items: center; border-radius: var(--radius-md); color: var(--text-300); transition: background-color var(--dur-base), color var(--dur-base); }
.icon-btn:hover { background: var(--hover); color: var(--text-100); }
.ghost-btn { height: 32px; padding: 0 8px; border-radius: var(--radius-md); font-size: 14px; color: var(--text-300); }
.ghost-btn:hover { background: var(--hover); color: var(--text-100); }
.send { width: 32px; height: 32px; display: grid; place-items: center; border-radius: var(--radius-md); background: var(--brand); color: var(--on-brand); transition: background-color var(--dur-base), transform var(--dur-fast), opacity var(--dur-base); }
.send:hover { background: var(--brand-hover); }
.send:active { background: var(--brand-active); transform: scale(0.96); }
.send:disabled { opacity: .3; cursor: default; transform: none; background: var(--brand); }
.disclaimer { margin: 8px 0 0; text-align: center; font-size: 12px; color: var(--text-400); }
.chips { display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; margin-top: 20px; }
.chip { height: 36px; padding: 0 14px; display: inline-flex; align-items: center; gap: 8px; font-size: 14px; color: var(--text-300);
  border: var(--border-w) solid var(--border-200); border-radius: var(--radius-lg); transition: background-color var(--dur-base), color var(--dur-base); }
.chip:hover { background: var(--hover); color: var(--text-100); }

/* ---------- messages ---------- */
.turn { margin-top: 28px; animation: rise 280ms var(--ease-out) both; }
@keyframes rise { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }
.msg-user {
  width: fit-content; max-width: 100%; padding: 10px 16px; background: var(--bg-300); border-radius: var(--radius-lg);
  font-size: 16px; line-height: 1.5; white-space: pre-wrap; word-break: break-word;
}
.msg-ai { margin-top: 20px; font-family: var(--font-serif); font-size: 16px; line-height: 1.7; color: var(--text-100); }
.thinking { display: inline-flex; align-items: center; gap: 8px; color: var(--text-300); font-family: var(--font-sans); font-size: 14px; }
.thinking .mark { width: 18px; height: 18px; animation: spin 3s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.actions { display: flex; gap: 2px; margin-top: 8px; }

/* ---------- markdown ---------- */
.prose > * + * { margin-top: 16px; }
.prose h1, .prose h2, .prose h3 { font-weight: 600; line-height: 1.35; margin-top: 24px; margin-bottom: 8px; }
.prose h1 { font-size: 24px; } .prose h2 { font-size: 20px; } .prose h3 { font-size: 18px; }
.prose a { color: var(--link); text-decoration: underline; text-underline-offset: 2px; text-decoration-thickness: 1px; }
.prose ul, .prose ol { padding-left: 24px; } .prose li + li { margin-top: 4px; } .prose li::marker { color: var(--text-300); }
.prose blockquote { border-left: 2px solid var(--border-300); padding-left: 16px; color: var(--text-200); margin-left: 0; }
.prose hr { border: 0; border-top: var(--border-w) solid var(--border-200); margin: 24px 0; }
.prose :not(pre) > code { font-family: var(--font-mono); font-size: .875em; background: var(--bg-300); color: var(--code-inline-text); padding: 1px 6px; border-radius: var(--radius-sm); }
.prose pre { background: var(--code-bg); border: var(--border-w) solid var(--border-200); border-radius: var(--radius-lg); padding: 14px 16px; overflow-x: auto; font-family: var(--font-mono); font-size: 14px; line-height: 1.55; tab-size: 2; }
.prose table { border-collapse: collapse; width: 100%; font-family: var(--font-sans); font-size: 14px; }
.prose th, .prose td { text-align: left; padding: 8px 12px; border-bottom: var(--border-w) solid var(--border-100); font-variant-numeric: tabular-nums; }
.prose th { font-weight: 600; background: color-mix(in srgb, var(--bg-300) 60%, transparent); }

/* ---------- buttons ---------- */
.btn { height: 36px; padding: 0 16px; border-radius: var(--radius-md); font-size: 14px; font-weight: 500; display: inline-flex; align-items: center; justify-content: center; gap: 8px;
  transition: background-color var(--dur-base), border-color var(--dur-base), transform var(--dur-fast); }
.btn:active { transform: scale(0.98); }
.btn-primary { background: var(--brand); color: var(--on-brand); }
.btn-primary:hover { background: var(--brand-hover); }
.btn-outline { border: var(--border-w) solid var(--border-200); color: var(--text-100); }
.btn-outline:hover { background: var(--hover); border-color: var(--border-300); }
.btn-ghost { color: var(--text-200); }
.btn-ghost:hover { background: var(--hover); color: var(--text-100); }
.btn[disabled] { opacity: .45; pointer-events: none; }

/* ---------- menus / modals ---------- */
.menu { min-width: 220px; padding: 6px; background: var(--bg-000); border: var(--border-w) solid var(--border-200); border-radius: var(--radius-lg); box-shadow: var(--shadow-menu); animation: pop 140ms var(--ease-out) both; }
@keyframes pop { from { opacity: 0; transform: translateY(4px) scale(.98); } to { opacity: 1; transform: none; } }
.menu-item { display: flex; align-items: center; gap: 10px; width: 100%; height: 34px; padding: 0 10px; border-radius: var(--radius-md); font-size: 14px; color: var(--text-200); text-align: left; }
.menu-item:hover { background: var(--hover); color: var(--text-100); }
.menu-item.danger { color: var(--danger); }
.menu-sep { height: var(--border-w); background: var(--border-100); margin: 6px -6px; }
.backdrop { position: fixed; inset: 0; background: rgba(20, 20, 19, 0.45); }
.modal { background: var(--bg-000); border: var(--border-w) solid var(--border-200); border-radius: var(--radius-xl); padding: 24px; max-width: 480px; box-shadow: var(--shadow-modal); }
.modal h2 { font-family: var(--font-serif); font-size: 22px; font-weight: 500; margin: 0 0 8px; }
.tooltip { background: var(--text-100); color: var(--bg-100); font-size: 12px; font-weight: 500; padding: 4px 8px; border-radius: var(--radius-sm); }

/* ---------- mobile ---------- */
@media (max-width: 767px) {
  .sidebar { position: fixed; inset: 0 auto 0 0; width: min(85vw, 320px); z-index: 40; transform: translateX(-100%); transition: transform 200ms ease; }
  .sidebar[data-open="true"] { transform: none; }
  .column { padding: 8px 16px 24px; }
  .composer-wrap { padding: 0 12px calc(12px + env(safe-area-inset-bottom)); }
}
```

---

## 16. Tailwind mapping

Tailwind v3 (`tailwind.config.js`). Colors point at the CSS variables so light/dark switches automatically.

```js
/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['selector', '[data-theme="dark"]'],
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    // Replace Tailwind's cool grays entirely so you can't reach for them by accident
    colors: {
      transparent: 'transparent',
      current: 'currentColor',
      bg:     { 0: 'var(--bg-000)', 1: 'var(--bg-100)', 2: 'var(--bg-200)', 3: 'var(--bg-300)', 4: 'var(--bg-400)' },
      text:   { 1: 'var(--text-100)', 2: 'var(--text-200)', 3: 'var(--text-300)', 4: 'var(--text-400)', 5: 'var(--text-500)' },
      border: { 1: 'var(--border-100)', 2: 'var(--border-200)', 3: 'var(--border-300)' },
      brand:  { DEFAULT: 'var(--brand)', hover: 'var(--brand-hover)', active: 'var(--brand-active)', clay: 'var(--brand-clay)', on: 'var(--on-brand)', tint: 'var(--brand-tint)' },
      link: 'var(--link)', success: 'var(--success)', warning: 'var(--warning)', danger: 'var(--danger)',
    },
    extend: {
      fontFamily: { serif: ['var(--font-serif)'], sans: ['var(--font-sans)'], mono: ['var(--font-mono)'] },
      borderRadius: { sm: '6px', md: '8px', lg: '12px', xl: '16px', composer: '20px' },
      boxShadow: {
        composer: 'var(--shadow-composer)', 'composer-hover': 'var(--shadow-composer-hover)',
        'composer-focus': 'var(--shadow-composer-focus)', menu: 'var(--shadow-menu)', modal: 'var(--shadow-modal)',
      },
      maxWidth: { column: '48rem', composer: '45rem' },
      borderWidth: { hair: '0.5px' },
      transitionTimingFunction: { out: 'cubic-bezier(0.16, 1, 0.3, 1)' },
    },
  },
};
```

Example utility strings:

```html
<!-- composer -->
<div class="bg-bg-0 border-hair border-border-2 rounded-composer shadow-composer hover:border-border-3 hover:shadow-composer-hover focus-within:shadow-composer-focus transition p-3">
<!-- user bubble -->
<div class="bg-bg-3 rounded-lg px-4 py-2.5 w-fit max-w-full text-text-1">
<!-- assistant text -->
<div class="font-serif text-[16px] leading-[1.7] text-text-1">
<!-- send button -->
<button class="size-8 grid place-items-center rounded-md bg-brand text-brand-on hover:bg-brand-hover active:scale-95 disabled:opacity-30">
```

For Tailwind v4, move the same values into an `@theme { --color-bg-100: …; }` block in your CSS instead of a config file.

---

## 17. Minimal HTML + JS skeleton

A single-file starting point that wires the tokens and components above (drop `tokens.css`, `base.css`, `components.css` into `<style>` or separate files).

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>Your app</title>
  <!-- fonts link from §4.1 here -->
  <!-- theme-before-paint script from §15.1 here -->
  <link rel="stylesheet" href="tokens.css">
  <link rel="stylesheet" href="base.css">
  <link rel="stylesheet" href="components.css">
</head>
<body>
<div class="app">
  <aside class="sidebar" id="sidebar">
    <div class="brand-word">YourApp</div>
    <button class="sb-row sb-new"><span class="plus">+</span> New chat</button>
    <button class="sb-row">Chats</button>
    <button class="sb-row">Projects</button>
    <div class="sb-label">Recents</div>
    <button class="sb-row sb-chat" aria-current="true">Designing a REST API</button>
    <button class="sb-row sb-chat">Async patterns in Python</button>
    <div class="sb-footer">
      <button class="sb-row" style="height:48px"><span class="avatar">K</span> Kanishk</button>
    </div>
  </aside>

  <main class="main" id="main" data-empty="true">
    <header class="header">
      <button class="ghost-btn" id="chatTitle">New chat</button>
      <button class="btn btn-outline" style="height:32px">Share</button>
    </header>

    <div class="stage">
      <div class="scroll" id="scroll"><div class="column" id="messages" role="log" aria-live="polite"></div></div>

      <div class="welcome">
        <svg class="mark" viewBox="0 0 24 24" aria-hidden="true"><g stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M12 3v18M3 12h18M5.6 5.6l12.8 12.8M18.4 5.6L5.6 18.4"/></g></svg>
        <h1 class="greeting" id="greeting"></h1>
      </div>

      <div class="composer-wrap">
        <div class="composer">
          <textarea id="input" rows="1" placeholder="How can I help you today?" aria-label="Message"></textarea>
          <div class="toolbar">
            <button class="icon-btn" aria-label="Attach">+</button>
            <div class="toolbar-right">
              <button class="ghost-btn">Model ⌄</button>
              <button class="send" id="send" aria-label="Send" disabled>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5M5 12l7-7 7 7"/></svg>
              </button>
            </div>
          </div>
        </div>
        <div class="chips"><button class="chip">Write</button><button class="chip">Learn</button><button class="chip">Code</button></div>
        <p class="disclaimer">AI can make mistakes. Please double-check responses.</p>
      </div>
    </div>
  </main>
</div>

<script>
  const $ = (id) => document.getElementById(id);
  const main = $('main'), input = $('input'), send = $('send'), list = $('messages'), scroll = $('scroll');

  // time-based greeting
  const h = new Date().getHours();
  $('greeting').textContent = `${h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening'}, Kanishk`;

  // auto-grow textarea + enable send
  input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 384) + 'px';
    send.disabled = !input.value.trim();
  });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); if (!send.disabled) submit(); }
  });
  send.addEventListener('click', submit);

  function submit() {
    const text = input.value.trim();
    if (!text) return;
    main.dataset.empty = 'false';
    const turn = document.createElement('div');
    turn.className = 'turn';
    const user = document.createElement('div');
    user.className = 'msg-user';
    user.textContent = text;                       // textContent: never inject user HTML
    const ai = document.createElement('div');
    ai.className = 'msg-ai prose';
    ai.innerHTML = '<span class="thinking"><svg class="mark" viewBox="0 0 24 24"><g stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M12 3v18M3 12h18M5.6 5.6l12.8 12.8M18.4 5.6L5.6 18.4"/></g></svg>Thinking…</span>';
    turn.append(user, ai);
    list.append(turn);
    input.value = ''; input.style.height = 'auto'; send.disabled = true;
    scroll.scrollTop = scroll.scrollHeight;

    // TODO: replace with your real streaming API call
    setTimeout(() => { ai.textContent = 'Replace this with the streamed response from your backend.'; }, 900);
  }

  // theme toggle helper (call from a menu item)
  window.setTheme = (t) => { localStorage.setItem('theme', t); document.documentElement.dataset.theme = t; };
</script>
</body>
</html>
```

---

## 18. Implementation checklist

**Foundation**
- [ ] Delete every gradient, glow, blur, purple/pink/indigo/blue utility from the project (see §2 audit).
- [ ] Add `tokens.css` (light + dark), `base.css`, and the Google Fonts link.
- [ ] Replace Tailwind's default color palette with the tokens (or only use the CSS variables).
- [ ] Set page background `--bg-100`, text `--text-100`; sidebar `--bg-200`.

**Layout**
- [ ] 288px sidebar + flexible main; 48px header; 768px centered conversation column.
- [ ] Composer pinned to bottom (max 672–720px) with a fade above it; disclaimer line below.
- [ ] Welcome state: serif greeting + centered composer (+ optional chips); composer drops to the bottom after the first message.

**Components**
- [ ] Composer: white raised surface, 20px radius, 0.5px border, faint shadow, auto-grow textarea, terracotta send button (disabled at 30% opacity when empty).
- [ ] User message: beige `--bg-300` bubble, 12px radius, sans 16px.
- [ ] Assistant message: no bubble/avatar, serif 16px / 1.7, action row (copy, like, dislike, retry).
- [ ] Code blocks with language label + copy button, warm syntax palette, no purple themes.
- [ ] Inline code: beige chip with warm-red text.
- [ ] Sidebar rows 32–36px, fade-mask truncation, "New chat" with terracotta circle.
- [ ] Menus, modals, tooltips, toasts per §8.9–8.11.

**Polish**
- [ ] Hairline borders (0.5px on hi-dpi) everywhere instead of heavy 1–2px borders.
- [ ] Thin-stroke icons (Phosphor Regular / Lucide @1.5).
- [ ] Thinking indicator (your own clay mark, slow spin/pulse).
- [ ] 150–250ms ease-out transitions; message entrance fade/rise; `prefers-reduced-motion` respected.
- [ ] Dark mode via `data-theme`, with a Light / Auto / Dark toggle.
- [ ] Keyboard focus rings, aria labels, `role="log"` on the message list.
- [ ] Mobile: drawer sidebar, safe-area padding, 16px inputs, `100dvh`.

**Final sanity pass (squint test)**
- [ ] Blur your eyes at the screen: you should see cream, near-black text, and exactly one small terracotta element. If you see any purple, blue or glow — something is wrong.

---

## 19. Verifying against the real thing

Because these values are approximations, check them yourself for anything you want exact. Do this in your own browser, for reference only.

### 19.1 DevTools walkthrough

1. Open the Claude chat app in Chrome/Edge/Firefox, press **F12** (or right-click → *Inspect*).
2. In **Elements**, select the `<html>` element. In the **Styles** pane look for **CSS custom properties** (variables) declared on `:root` / `html` — historically these are named like `--bg-000 … --bg-500`, `--text-000 … --text-500`, `--border-100 … --border-400`, `--brand-100`, `--accent-*` and store HSL components (e.g. `48 33.3% 97.1%`). Names/values may have changed; if so, just read whatever is there.
3. Toggle the app's theme (Light/Dark) and note which variables change — that's your token list for each mode.
4. Inspect the **composer**, a **user message**, an **assistant message**, a **sidebar row**, and a **code block**; read border-radius, padding, font-family, font-size, line-height and box-shadow from the **Computed** tab.
5. Use the **Eyedropper** (color picker in the Styles pane) to sample any color.
6. Hover over elements in the **Elements** panel with *Force state → :hover/:focus* to read hover/focus styles.
7. Open **Network → Font** to see which font files load (for *reference only* — do not download or redistribute them).
8. Test breakpoints with **Device Toolbar** (Ctrl/Cmd+Shift+M) to see the mobile drawer behavior.

Handy extensions: CSS Peeper, ColorZilla, WhatFont.

### 19.2 Known uncertainties (verify these first)

| Detail | What this file assumes | Why uncertain |
|---|---|---|
| User bubble alignment | Left-aligned in the column | Web vs mobile apps differ; alignment has changed across redesigns |
| Composer font | Sans 16px | Some versions used the serif in the input |
| Sidebar width | ≈288px expanded, ≈48–52px collapsed | Changes with redesigns / user resizing |
| Composer radius | 20px (16px acceptable) | Differs between welcome and chat states |
| Code block background | White (light) / `#141413` (dark) | Has varied between versions |
| Link color | `#2C84DB` ≈ | Observed blue; may differ in current build |
| Inline code color | Warm red `#B53333` ≈ | Uses a danger-family color; exact shade approximate |
| Exact cream | `#FAF9F5` canvas, `#F5F4ED` sidebar | Different sources list `#F5F4ED`, `#F8F8F6`, `#F0ECE0` — they're all in the same warm family; marketing and product differ slightly |
| Suggestion chips / extra toolbar buttons | Optional | Labels, icons and presence change often |

None of these change the overall look — the warm palette, serif/sans split, bubble logic, flat hairline surfaces and single terracotta accent do.

---

## 20. Source notes

Compiled from the following kinds of public material (accessed October 2026):

- Anthropic's published brand palette and the open `anthropics/skills` brand-guidelines (Dark `#141413`, Light `#faf9f5`, Mid Gray `#b0aea5`, Light Gray `#e8e6dc`, accents orange/blue `#6a9bcc`/green `#788c5d`; Claude Clay `#d97757`).
- Public design-system write-ups of Claude's web surfaces (cream canvas, terracotta `#c96442` / `#cc785c`-family accent, Anthropic Serif + Sans + Mono family, hairline borders, large radii) — e.g. design-token pages on shadcn.io, open-design.ai, kombai.com, webdesignhot.com.
- An open-source Claude-style chat clone (assistant-ui) illustrating: no avatar/no bubble for the assistant, tinted user bubble, composer with border only, warm cream canvas.
- General, widely observed behavior of the Claude chat UI.

These are third-party interpretations, not official Anthropic documentation, which is why §19 exists.

---

## Appendix — One-screen cheat sheet

```
CANVAS        #FAF9F5   (dark #262624)
SIDEBAR       #F5F4ED   (dark #1F1E1D)
RAISED        #FFFFFF   (dark #30302E)      composer, menus, modals
USER BUBBLE   #F0EEE6   (dark #141413)      radius 12px, sans 16px
TEXT          #141413 / #3D3D3A / #73726C   (dark #FAF9F5 / #C2C0B6 / #9C9A92)
BORDER        0.5px rgba(31,30,29,.15)      (dark rgba(222,220,209,.15))
ACCENT        #C96442 (dark #D97757)        send button, "New chat", logo mark only
FONTS         serif = AI text + greeting (Newsreader), sans = UI (Inter), mono = code (JetBrains Mono)
COLUMN        768px max;  COMPOSER 672–720px, radius 20px, shadow 0 4px 20px rgba(0,0,0,.035)
SIDEBAR       288px; rows 32–36px, radius 8px, 14px text, fade-mask truncation
MOTION        150–250ms ease-out; message rise 6px; logo spin/pulse while thinking
NEVER         gradients · glow · glass blur · purple/pink/blue · bold uppercase · emoji icons · AI avatar bubbles
```
