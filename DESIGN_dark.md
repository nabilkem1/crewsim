# Apple — Style Reference (Dark Ops Console Palette)
> Product storytelling re-skinned on a dark operations console. Content sits on near-black slate panels, with white type, a cool Horizon Blue for navigation and links, and a warm Review Amber reserved for actions.

**Theme:** dark

Source measurements are normalized; roles and recommendations are interpreted. Font summary lists are independent, not paired by position. HTML examples are reconstructions, not source components. Colors were re-mapped from the reference dashboard screenshot; typography, spacing, and radii are unchanged from the original Apple reference.

The page is now a dark console: enormous product photography occupies the center while compact Signal White typography gives each claim a controlled, almost editorial weight. The page alternates seamless #11181c storytelling sections with #1b252a panel bands containing #0b1215 recessed cards and #233034 raised cards, using one cool blue (#7cb8e8) for links and active navigation and one warm amber (#f8b878) only for compact action controls. Status is communicated with small pastel badges (rose, mint, cream). Rounded 28px media frames soften the composition; nearly every surface stays flat and shadowless.

## Tokens — Colors

| Name | Value | Token | Role |
|------|-------|-------|------|
| Ops Night | `#11181c` | `--color-ops-night` | Primary page canvas, hero background, product story sections, and default dark stage |
| Console Slate | `#1b252a` | `--color-console-slate` | Alternate full-width panel band, side-rail column, feature-stage backdrop, footer surface, and muted content blocks |
| Raised Graphite | `#233034` | `--color-raised-graphite` | Elevated inner cards, opened global-navigation surface, and list rows inside panels |
| Metric Black | `#0b1215` | `--color-metric-black` | Recessed KPI (Key Performance Indicator) tiles and feature-card surfaces set below the canvas |
| Grid Line | `#2f3b42` | `--color-grid-line` | 1px dividers, restrained control outlines, and subtle panel separators |
| Control Charcoal | `#2a353b` | `--color-control-charcoal` | Disabled control fills, subdued utility surfaces, and single-pixel navigation edge treatment |
| Signal White | `#f4f6f8` | `--color-signal-white` | Headlines, KPI values, primary body copy, navigation labels, and light utility icons |
| Fog Gray | `#8b949c` | `--color-fog-gray` | Secondary copy, metric captions, legal text, subdued navigation content, and low-emphasis glyphs |
| Muted Steel | `#5d6871` | `--color-muted-steel` | Input outlines, inactive indicators, chevrons, and fine outlined-control edges |
| Horizon Blue | `#7cb8e8` | `--color-horizon-blue` | Inline links, section links, active top-navigation tab, and blue text controls — a cool punctuation against the dark console |
| Review Amber | `#f8b878` | `--color-review-amber` | Filled action controls (Review, conversion, learn-more) — the warm amber reserves visual urgency for compact action moments; always paired with Ops Night text |
| Alert Coral | `#ef7a85` | `--color-alert-coral` | Small status labels such as new-product or attention markers, and hard-constraint warning glyphs |
| Violation Rose | `#f6d3dd` | `--color-violation-rose` | Fill for negative-count status badges (paired with Violation Ink #b4233c text) |
| Violation Ink | `#b4233c` | `--color-violation-ink` | Text on Violation Rose badges |
| Clear Mint | `#6fd3a5` | `--color-clear-mint` | Fill for zero/healthy status badges (paired with Ops Night text) |
| Caution Cream | `#fff6d6` | `--color-caution-cream` | Fill for soft-warning status badges (paired with Ops Night text) |
| Success Green | `#2ea37a` | `--color-success-green` | Approved/check glyphs and positive state icons |
| Warning Gold | `#f5c04a` | `--color-warning-gold` | Caution triangle glyphs and pending-action icons |
| Optimizer Lavender | `#9096c8` | `--color-optimizer-lavender` | Progress-track lines and step connectors in pipeline/stepper components |
| Map Black | `#050807` | `--color-map-black` | Full-bleed map or data-visual backdrop |

## Tokens — Typography

### SF Pro Display — Product names, display headlines, large feature statements, and section-level product claims. The 80px/600 hero treatment tightens to -1.2px, making the largest type feel compact rather than promotional. · `--font-sf-pro-display`
- **Substitute:** Inter, Helvetica Neue, Arial
- **Weights:** 400, 500, 600
- **Sizes:** 19px, 21px, 24px, 28px, 40px, 48px, 80px
- **Line height:** 1.00, 1.05, 1.08, 1.14, 1.17, 1.21, 1.33, 1.38
- **Letter spacing:** -1.2px at 80px; normal at 40px; +0.23px at 19-21px; profile range -0.015em to 0.012em
- **OpenType features:** `"numr"`
- **Role:** Product names, display headlines, large feature statements, and section-level product claims. The 80px/600 hero treatment tightens to -1.2px, making the largest type feel compact rather than promotional.

### SF Pro Text — Navigation, body copy, links, compact buttons, pricing details, labels, and footnotes. The consistently negative tracking lets small interface text remain dense and Apple-specific instead of looking like generic system UI. · `--font-sf-pro-text`
- **Substitute:** Inter, Helvetica Neue, Arial
- **Weights:** 400, 500, 600
- **Sizes:** 10px, 12px, 14px, 17px, 20px, 26px, 44px
- **Line height:** 1.00, 1.18, 1.24, 1.29, 1.33, 1.43, 1.47
- **Letter spacing:** -0.37px at 10px, -0.12px at 12px, -0.22px at 14px, -0.37px at 17px; profile range -0.037em to -0.003em
- **OpenType features:** `"numr"`
- **Role:** Navigation, body copy, links, compact buttons, pricing details, labels, and footnotes. The consistently negative tracking lets small interface text remain dense and Apple-specific instead of looking like generic system UI.

### Arial — Fallback text inside the observed search/input control only. · `--font-arial`
- **Substitute:** Arial
- **Weights:** 400
- **Sizes:** 13px
- **Line height:** 1.20
- **Role:** Fallback text inside the observed search/input control only.

### Type Scale

| Role | Family | Weight | Size | Line Height | Letter Spacing | Token |
|------|--------|--------|------|-------------|----------------|-------|
| global-nav | SF Pro Text | 400 | 12px | 1 | -0.12px | `--text-global-nav` |
| compact-control | SF Pro Text | 400 | 12px | 1.33 | -0.12px | `--text-compact-control` |
| body-small | SF Pro Text | 400 | 14px | 1.29 | -0.224px | `--text-body-small` |
| body | SF Pro Text | 400 | 17px | 1.47 | -0.374px | `--text-body` |
| feature-copy | SF Pro Text | 400 | 17px | 1.24 | -0.374px | `--text-feature-copy` |
| product-nav-title | SF Pro Display | 600 | 19px | 1.21 | 0.228px | `--text-product-nav-title` |
| product-kicker | SF Pro Display | 600 | 21px | 1 | 0.231px | `--text-product-kicker` |
| feature-heading | SF Pro Display | 600 | 40px | 1 | 0px | `--text-feature-heading` |
| hero-display | SF Pro Display | 600 | 80px | 1.05 | -1.2px | `--text-hero-display` |

## Tokens — Spacing & Shapes

**Base unit:** 4px

**Density:** comfortable

### Spacing Scale

| Name | Value | Token |
|------|-------|-------|
| 4 | 4px | `--spacing-4` |
| 8 | 8px | `--spacing-8` |
| 12 | 12px | `--spacing-12` |
| 16 | 16px | `--spacing-16` |
| 20 | 20px | `--spacing-20` |
| 24 | 24px | `--spacing-24` |
| 28 | 28px | `--spacing-28` |
| 32 | 32px | `--spacing-32` |
| 40 | 40px | `--spacing-40` |
| 48 | 48px | `--spacing-48` |
| 52 | 52px | `--spacing-52` |
| 64 | 64px | `--spacing-64` |
| 76 | 76px | `--spacing-76` |
| 80 | 80px | `--spacing-80` |
| 128 | 128px | `--spacing-128` |
| 144 | 144px | `--spacing-144` |

### Border Radius

| Element | Value |
|---------|-------|
| cards | 28px |
| links | 10px |
| pills | 36px |
| badges | 0px |
| images | 28px |
| inputs | 980px |
| buttons | 9999px |
| navigation | 20px |

### Shadows

| Name | Value | Token |
|------|-------|-------|
| subtle | `rgb(42, 53, 59) 0px 0px 0px 1px` | `--shadow-subtle` |
| subtle-2 | `rgb(93, 104, 113) 0px 0px 0px 1px` | `--shadow-subtle-2` |

### Layout

- **Section gap:** 90px
- **Card padding:** 28px
- **Element gap:** 20px

## Components

### Global Store Navigation
**Role:** Persistent utility navigation

A 44px-tall #11181c navigation bar with Apple glyph, compact SF Pro Text 12px/400 links, and rgba(244,246,248,0.85) labels. Keep controls unboxed; the active item uses a Horizon Blue (#7cb8e8) fill with #11181c text. Opened navigation uses #233034 with a 1px #2a353b edge and blur(20px).

### Product Local Navigation
**Role:** Product-page header and conversion controls

A #11181c local bar carries the product name in Signal White SF Pro Display 19px/600 and compact right-aligned pill controls. Use a 20px container radius where the local bar is floated over the page, with #2f3b42 as the hairline boundary.

### Outlined Explore Pill
**Role:** Secondary product-navigation control

Use transparent fill, #f4f6f8 text, a 1px #5d6871 outline, and a 9999px radius. Set compact SF Pro Text 12px/400 type with 16px line height; do not give this secondary control a colored fill.

### Review Amber Pill
**Role:** Filled conversion / action control

Use #f8b878 fill with #11181c SF Pro Text 12px/400 at 16px line height and -0.12px tracking. Set a 9999px radius; this amber treatment stays compact inside the product bar and floating pricing callout.

### Hero Product Stage
**Role:** Launch introduction

Set a #11181c full-bleed visual stage with centered product name in Signal White SF Pro Display 21px/600, then an 80px/600 #f4f6f8 display statement at 84px line height and -1.2px tracking. Place the device render directly beneath the text without a containing card.

### Floating Pricing Callout
**Role:** Purchase context over product imagery

Float a #233034 rounded 28px capsule near the lower product render with 14px/600 #f4f6f8 pricing text and #8b949c secondary copy. Keep the Review Amber pill inside the callout; do not use drop shadows.

### Section Anchor Navigation
**Role:** In-page feature navigation

Render a horizontal list of SF Pro Text 17px/500 labels at 25px line height and -0.374px tracking in #f4f6f8 (inactive items in #8b949c). Use transparent backgrounds, 28px vertical padding, and no card or underline treatment.

### Highlights Stage
**Role:** Feature-carousel section

Use #1b252a as the full section background, with a large #f4f6f8 section heading and a Horizon Blue text link aligned opposite it. Feature slides are #0b1215 28px-radius cards with no shadow.

### Feature Media Card
**Role:** Product-detail showcase

Use a #0b1215 surface, 28px radius, no border, and no shadow. Center the device render with an SF Pro Display 24px/600 or 40px/600 #f4f6f8 feature statement above it; media may crop beyond the card edge.

### Carousel Playback Control
**Role:** Highlights media control

Use a translucent control track based on rgba(35,48,52,0.72), 36px radius, and subdued rgba(244,246,248,0.64) glyphs. Keep slide dots and pause control grouped in a small pill rather than adding visible card chrome.

### Editorial Feature Block
**Role:** Long-form product story

Place a small #8b949c SF Pro Display kicker above a large left-aligned #f4f6f8 display statement, followed by SF Pro Text 17px/400 #f4f6f8 body copy at approximately 21px line height and -0.374px tracking. The accompanying hardware image is oversized and allowed to enter from the opposite side.

### Rounded Search Input
**Role:** Global navigation search

Use #1b252a fill, #f4f6f8 13px Arial text, #8b949c placeholder, 24px left padding, 45px right padding, a 1px #5d6871 outline, and a 980px radius. Keep the default field visually absent until expanded from navigation.

### Launch Status Label
**Role:** New-product annotation

Use #ef7a85 SF Pro Text 12px/600 with 16px line height and -0.12px tracking. Leave it as plain text with no pill background or border.

### Status Badge
**Role:** Count or state annotation (new — taken from the reference dashboard)

Compact SF Pro Text 12px/500 label with 4px radius and 2px 8px padding. Use Violation Rose (#f6d3dd) fill with #b4233c text for negative counts, Clear Mint (#6fd3a5) fill with #11181c text for zero/healthy, and Caution Cream (#fff6d6) fill with #11181c text for soft warnings. Pair with a #8b949c caption label to its left.

### Pipeline Stepper
**Role:** Process progress indicator (new — taken from the reference dashboard)

Horizontal steps joined by a 2px #9096c8 track; step nodes are 16px #9096c8 circles with #f4f6f8 glyphs. Step titles use SF Pro Text 10px/600 uppercase #f4f6f8, timestamps use 10px/400 #8b949c.

## Do's and Don'ts

### Do
- Use #11181c as the default canvas and reserve #1b252a for full-width panel bands, side rails, and footer regions.
- Use #0b1215 for recessed metric/feature tiles and #233034 for raised inner cards.
- Set display hero statements in SF Pro Display 80px/600, 84px line height, and -1.2px tracking, in #f4f6f8.
- Use SF Pro Text 17px/400 with -0.374px tracking for feature paragraphs and in-page navigation at 17px/500.
- Use 28px radius for feature cards and contained media; keep those cards shadowless.
- Use #f8b878 only for compact filled action pills with #11181c 12px SF Pro Text.
- Use #7cb8e8 for inline links, textual section links, and the single active navigation item.
- Space major storytelling sections by 90px and use 20px gaps between related interface elements.

### Don't
- Do not add gradients; product imagery and data visuals supply the page’s color and visual depth.
- Do not use shadows on feature cards, editorial blocks, or floating pricing capsules.
- Do not replace the 28px feature-card radius with 8px, 12px, or square corners.
- Do not use #f8b878 as a large hero background or a universal filled button color.
- Do not put #ffffff or other light surfaces behind content; light fills are reserved for small status badges.
- Do not set hero headlines in bold 700 or wider tracking than -1.2px at 80px.
- Do not use saturated red/green fills for status; use the pastel Violation Rose, Clear Mint, and Caution Cream badges.
- Do not place dense boxed UI panels over the product renders; keep #11181c space around hardware imagery.

## Surfaces

| Level | Name | Value | Purpose |
|-------|------|-------|---------|
| -1 | Metric Black | `#0b1215` | Recessed KPI tiles and feature-card surface. |
| 0 | Ops Night | `#11181c` | Primary hero, editorial canvas, and local navigation. |
| 1 | Console Slate | `#1b252a` | Alternate panel band, side rail, carousel backdrop, muted content area, and footer. |
| 2 | Raised Graphite | `#233034` | Raised inner cards, list rows, and opened global-navigation layer. |
| 3 | Control Charcoal | `#2a353b` | Disabled or subdued utility-control fill and thin navigation edge. |

## Elevation

Surfaces gain separation through tonal steps (#0b1215 → #11181c → #1b252a → #233034), 28px media corners, and sparse 1px #2f3b42 edges rather than cast shadows. Lighter means higher. The only elevation-like marks are 0 0 0 1px outlines on navigation and selected controls.

## Imagery

The page is dominated by high-resolution product photography, device renders, and dark data visuals (for example, maps on #050807) rather than illustration. Hardware is isolated against near-black backdrops, often cropped at an oversized scale so the form becomes the composition. Images are either edge-free on the #11181c hero canvas or contained in large 28px-radius #0b1215 cards against #1b252a. Product UI appears inside device screens as explanatory evidence, while icons remain small, monochrome #f4f6f8 / #8b949c navigation glyphs.

## Layout

The page begins with a compact dark global store navigation (active item in Horizon Blue) above a product-local navigation bar, then opens into a centered #11181c hero with stacked product label, oversized headline, preorder copy, a dominant product render, and a floating pricing capsule. Storytelling proceeds through a #1b252a highlights band with a horizontally advancing set of large #0b1215 28px-radius media cards, followed by wide #11181c editorial sections that pair left-aligned text blocks with oversized product imagery entering from the right or below. Section headers introduce each chapter, while an in-page horizontal anchor navigation supports long-form scrolling; the page is spacious, image-led, and does not rely on visible grid lines.

## Agent Prompt Guide

Quick Color Reference:
- Ops Night: #11181c — Primary page canvas, hero background, product story sections, and default dark stage
- Console Slate: #1b252a — Alternate full-width panel band, side-rail column, feature-stage backdrop, footer surface, and muted content blocks
- Raised Graphite: #233034 — Elevated inner cards, opened global-navigation surface, and list rows inside panels
- Metric Black: #0b1215 — Recessed KPI (Key Performance Indicator) tiles and feature-card surfaces set below the canvas
- Grid Line: #2f3b42 — 1px dividers, restrained control outlines, and subtle panel separators
- Control Charcoal: #2a353b — Disabled control fills, subdued utility surfaces, and single-pixel navigation edge treatment
- Signal White: #f4f6f8 — Headlines, KPI values, primary body copy, navigation labels, and light utility icons
- Fog Gray: #8b949c — Secondary copy, metric captions, legal text, subdued navigation content, and low-emphasis glyphs
- Muted Steel: #5d6871 — Input outlines, inactive indicators, chevrons, and fine outlined-control edges
- Horizon Blue: #7cb8e8 — Inline links, section links, active top-navigation tab, and blue text controls — a cool punctuation against the dark console
- Review Amber: #f8b878 — Filled action controls (Review, conversion, learn-more) — the warm amber reserves visual urgency for compact action moments; always paired with Ops Night text
- Alert Coral: #ef7a85 — Small status labels such as new-product or attention markers, and hard-constraint warning glyphs
- Violation Rose: #f6d3dd — Fill for negative-count status badges (paired with Violation Ink #b4233c text)
- Violation Ink: #b4233c — Text on Violation Rose badges
- Clear Mint: #6fd3a5 — Fill for zero/healthy status badges (paired with Ops Night text)
- Caution Cream: #fff6d6 — Fill for soft-warning status badges (paired with Ops Night text)
- Success Green: #2ea37a — Approved/check glyphs and positive state icons
- Warning Gold: #f5c04a — Caution triangle glyphs and pending-action icons
- Optimizer Lavender: #9096c8 — Progress-track lines and step connectors in pipeline/stepper components
- Map Black: #050807 — Full-bleed map or data-visual backdrop

Create a #11181c launch hero with centered SF Pro Display 21px/600 product label and a centered 80px/600, 84px-line-height headline in Signal White (#f4f6f8); place an oversized device render directly below with no enclosing card.
Create a Product Local Navigation bar on #11181c with an SF Pro Display 19px/600 Signal White product title, an outlined Explore Pill (#5d6871 outline), and a Review Amber (#f8b878) 9999px-radius pill using #11181c SF Pro Text 12px/400.
Create a Console Slate (#1b252a) highlights section with a Signal White heading and Horizon Blue (#7cb8e8) text link; use a #0b1215 28px-radius feature media card with no shadow and an SF Pro Display 40px/600 feature statement.
Create a #11181c editorial product section with a left-aligned Signal White feature statement and SF Pro Text 17px/400 body copy at 21px line height and -0.374px tracking; crop a large product photograph into the right side.
Create a floating #233034 28px-radius pricing callout over a product render using Signal White 14px/600 pricing copy and a compact Review Amber 9999px-radius pill.

## Similar Brands

- **Google Pixel** — Product-led landing pages pair isolated hardware renders with generous white space and compact blue conversion controls.
- **Sony** — Large hardware photography and restrained editorial feature chapters make the product, rather than decorative interface chrome, carry the page.
- **Nothing** — Uses oversized device imagery and sparse product storytelling, though Apple’s palette is more monochrome and its controls are smaller.
- **Tesla** — Full-width product visual stages and minimal surrounding UI create a similarly showroom-like conversion flow.


## Quick Start

### CSS Custom Properties

```css
:root {
  /* Colors */
  --color-ops-night: #11181c;
  --color-console-slate: #1b252a;
  --color-raised-graphite: #233034;
  --color-metric-black: #0b1215;
  --color-grid-line: #2f3b42;
  --color-control-charcoal: #2a353b;
  --color-signal-white: #f4f6f8;
  --color-fog-gray: #8b949c;
  --color-muted-steel: #5d6871;
  --color-horizon-blue: #7cb8e8;
  --color-review-amber: #f8b878;
  --color-alert-coral: #ef7a85;
  --color-violation-rose: #f6d3dd;
  --color-violation-ink: #b4233c;
  --color-clear-mint: #6fd3a5;
  --color-caution-cream: #fff6d6;
  --color-success-green: #2ea37a;
  --color-warning-gold: #f5c04a;
  --color-optimizer-lavender: #9096c8;
  --color-map-black: #050807;

  /* Typography — Font Families */
  --font-sf-pro-display: 'SF Pro Display', ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  --font-sf-pro-text: 'SF Pro Text', ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  --font-arial: 'Arial', ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;

  /* Typography — Scale */
  --text-global-nav: 12px;
  --leading-global-nav: 1;
  --tracking-global-nav: -0.12px;
  --text-compact-control: 12px;
  --leading-compact-control: 1.33;
  --tracking-compact-control: -0.12px;
  --text-body-small: 14px;
  --leading-body-small: 1.29;
  --tracking-body-small: -0.224px;
  --text-body: 17px;
  --leading-body: 1.47;
  --tracking-body: -0.374px;
  --text-feature-copy: 17px;
  --leading-feature-copy: 1.24;
  --tracking-feature-copy: -0.374px;
  --text-product-nav-title: 19px;
  --leading-product-nav-title: 1.21;
  --tracking-product-nav-title: 0.228px;
  --text-product-kicker: 21px;
  --leading-product-kicker: 1;
  --tracking-product-kicker: 0.231px;
  --text-feature-heading: 40px;
  --leading-feature-heading: 1;
  --tracking-feature-heading: 0px;
  --text-hero-display: 80px;
  --leading-hero-display: 1.05;
  --tracking-hero-display: -1.2px;

  /* Typography — Weights */
  --font-weight-regular: 400;
  --font-weight-medium: 500;
  --font-weight-semibold: 600;

  /* Spacing */
  --spacing-unit: 4px;
  --spacing-4: 4px;
  --spacing-8: 8px;
  --spacing-12: 12px;
  --spacing-16: 16px;
  --spacing-20: 20px;
  --spacing-24: 24px;
  --spacing-28: 28px;
  --spacing-32: 32px;
  --spacing-40: 40px;
  --spacing-48: 48px;
  --spacing-52: 52px;
  --spacing-64: 64px;
  --spacing-76: 76px;
  --spacing-80: 80px;
  --spacing-128: 128px;
  --spacing-144: 144px;

  /* Layout */
  --section-gap: 90px;
  --card-padding: 28px;
  --element-gap: 20px;

  /* Border Radius */
  --radius-md: 4px;
  --radius-lg: 10px;
  --radius-2xl: 20px;
  --radius-3xl: 28px;
  --radius-3xl-2: 32px;
  --radius-3xl-3: 36px;
  --radius-full: 120px;
  --radius-full-2: 170px;
  --radius-full-3: 980px;
  --radius-full-4: 999px;
  --radius-full-5: 9999px;

  /* Named Radii */
  --radius-cards: 28px;
  --radius-links: 10px;
  --radius-pills: 36px;
  --radius-badges: 0px;
  --radius-images: 28px;
  --radius-inputs: 980px;
  --radius-buttons: 9999px;
  --radius-navigation: 20px;

  /* Shadows */
  --shadow-subtle: rgb(42, 53, 59) 0px 0px 0px 1px;
  --shadow-subtle-2: rgb(93, 104, 113) 0px 0px 0px 1px;

  /* Surfaces */
  --surface-ops-night: #11181c;
  --surface-console-slate: #1b252a;
  --surface-raised-graphite: #233034;
  --surface-metric-black: #0b1215;
  --surface-control-charcoal: #2a353b;
}
```

### Tailwind v4

```css
@theme {
  /* Colors */
  --color-ops-night: #11181c;
  --color-console-slate: #1b252a;
  --color-raised-graphite: #233034;
  --color-metric-black: #0b1215;
  --color-grid-line: #2f3b42;
  --color-control-charcoal: #2a353b;
  --color-signal-white: #f4f6f8;
  --color-fog-gray: #8b949c;
  --color-muted-steel: #5d6871;
  --color-horizon-blue: #7cb8e8;
  --color-review-amber: #f8b878;
  --color-alert-coral: #ef7a85;
  --color-violation-rose: #f6d3dd;
  --color-violation-ink: #b4233c;
  --color-clear-mint: #6fd3a5;
  --color-caution-cream: #fff6d6;
  --color-success-green: #2ea37a;
  --color-warning-gold: #f5c04a;
  --color-optimizer-lavender: #9096c8;
  --color-map-black: #050807;

  /* Typography */
  --font-sf-pro-display: 'SF Pro Display', ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  --font-sf-pro-text: 'SF Pro Text', ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  --font-arial: 'Arial', ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;

  /* Typography — Scale */
  --text-global-nav: 12px;
  --leading-global-nav: 1;
  --tracking-global-nav: -0.12px;
  --text-compact-control: 12px;
  --leading-compact-control: 1.33;
  --tracking-compact-control: -0.12px;
  --text-body-small: 14px;
  --leading-body-small: 1.29;
  --tracking-body-small: -0.224px;
  --text-body: 17px;
  --leading-body: 1.47;
  --tracking-body: -0.374px;
  --text-feature-copy: 17px;
  --leading-feature-copy: 1.24;
  --tracking-feature-copy: -0.374px;
  --text-product-nav-title: 19px;
  --leading-product-nav-title: 1.21;
  --tracking-product-nav-title: 0.228px;
  --text-product-kicker: 21px;
  --leading-product-kicker: 1;
  --tracking-product-kicker: 0.231px;
  --text-feature-heading: 40px;
  --leading-feature-heading: 1;
  --tracking-feature-heading: 0px;
  --text-hero-display: 80px;
  --leading-hero-display: 1.05;
  --tracking-hero-display: -1.2px;

  /* Spacing */
  --spacing-4: 4px;
  --spacing-8: 8px;
  --spacing-12: 12px;
  --spacing-16: 16px;
  --spacing-20: 20px;
  --spacing-24: 24px;
  --spacing-28: 28px;
  --spacing-32: 32px;
  --spacing-40: 40px;
  --spacing-48: 48px;
  --spacing-52: 52px;
  --spacing-64: 64px;
  --spacing-76: 76px;
  --spacing-80: 80px;
  --spacing-128: 128px;
  --spacing-144: 144px;

  /* Border Radius */
  --radius-md: 4px;
  --radius-lg: 10px;
  --radius-2xl: 20px;
  --radius-3xl: 28px;
  --radius-3xl-2: 32px;
  --radius-3xl-3: 36px;
  --radius-full: 120px;
  --radius-full-2: 170px;
  --radius-full-3: 980px;
  --radius-full-4: 999px;
  --radius-full-5: 9999px;

  /* Shadows */
  --shadow-subtle: rgb(42, 53, 59) 0px 0px 0px 1px;
  --shadow-subtle-2: rgb(93, 104, 113) 0px 0px 0px 1px;
}
```
