# 45s Theming — Lessons & Architecture

Everything an agent needs to implement a new theme correctly the first time.
Derived from the Irish Card Room theming session (v2.26–v2.27.47) and the
Cyberpunk theme session (v2.28.0–v2.29.8).

---

## How the Theme System Works

```javascript
// Module-level variable — read this anywhere without props
let currentThemeId = 'irish'; // set at boot from localStorage/Firebase

// Also stored as React state in MultiplayerApp
const [activeTheme, setActiveTheme] = useState('irish');
```

- `currentThemeId === 'irish'` gates ALL Irish-specific rendering in JSX and CSS
- Theme change: update `currentThemeId`, call `setActiveTheme`, write to Firebase
- CSS is gated with `.theme-irish` class on the root `.v3-phone` div
- Theme tiles live in **Preferences modal** (not Profile Settings)

---

## Design Tokens — Cyberpunk (second theme implemented)

```
bg:         linear-gradient(175deg, #060d18 0%, #020509 100%)
cyan:       #00e5ff   (primary accent, glows, borders)
magenta:    #ff00cc   (secondary accent, alerts, warnings)
amber:      #ff8c00   (dealer chip, bid buttons)
green:      #00ff88   (online presence, positive indicators)
red:        #ff1a75   (negative/error)
darkBg:     #020509   (deepest background)
panelBg:    rgba(4,10,20,0.85)   (card/panel surfaces)
textPrimary: #c0ddf0  (body text)
textMono:   #3a5f78   (dim labels)

Fonts: Orbitron 700/900 (headings, numbers), Share Tech Mono 400 (labels, mono), Inter (body)
Font root class: `theme-cyberpunk` on `.v3-phone` and lobby/WR root divs
Lobby root class: `cp-lobby-bg`
```

**Confirmed working @font-face for Cyberpunk (April 2026):**
```css
@font-face { font-family: 'Orbitron'; font-style: normal; font-weight: 700; font-display: swap;
  src: url(https://fonts.gstatic.com/s/orbitron/v31/yMJMMIlzdpvBhQQL_SC3X9yhF25-T1nyKS6BogtscYY.ttf) format('truetype'); }
@font-face { font-family: 'Orbitron'; font-style: normal; font-weight: 900; font-display: swap;
  src: url(https://fonts.gstatic.com/s/orbitron/v31/yMJMMIlzdpvBhQQL_SC3X9yhF25-T1nyGSmBogtscYY.ttf) format('truetype'); }
@font-face { font-family: 'Share Tech Mono'; font-style: normal; font-weight: 400; font-display: swap;
  src: url(https://fonts.gstatic.com/s/sharetechmono/v15/J7aHnp1uDWRBEqV98dVQztYldFc7pAsEIc3Xew.ttf) format('truetype'); }
```

---

## Design Tokens — Irish Card Room (reference implementation)

```
bg:         linear-gradient(160deg, #1a0e05 0%, #0c0602 50%, #130a03 100%)
felt:       #13572a
brass:      #c9a24a
brassHi:    #f6d778
brassLo:    #5a3f16
paper:      #fbf6e4
walnut:     #180b03
teamUs:     #5dd084
teamThem:   #ef7c74
meBlue:     #6bb6ff

Fonts: Cinzel (display/headings), Merriweather italic (body), Inter (UI numbers)
Font load: https://fonts.googleapis.com/css2?family=Cinzel:wght@400;700;900&family=Merriweather:ital,wght@1,400&family=Inter:wght@400;500;600&display=swap
```

When creating a new theme, define YOUR tokens in the same pattern and find/replace throughout.

---

## File Map

| File | Purpose |
|------|---------|
| `index-test.html` | Working test build — all theme dev goes here |
| `index-themes.html` | Always kept as exact copy of index-test.html |
| `index.html` | Production — NEVER touch during theme dev |
| `mockups/` | HTML mockups for user approval before implementation |

**Workflow:** mockup → user approves → implement in index-test.html → copy to index-themes.html → commit + push both.

**Never push index.html** unless the user explicitly says "push to production."

---

## Layout Architecture — What Is Structural vs Themeable

### STRUCTURAL — never change these (they control layout stability)

```css
.v3-middle-row     { flex: 1; display: flex; align-items: center; min-height: 0; }
.v3-side-seat      { align-self: flex-start; }   /* CRITICAL — pins E/W to top */
.v3-facedown-col   { min-height: 218px; justify-content: flex-start; }  /* prevents collapse */
.v3-rail           { width: 200px; height: 200px; position: relative; overflow: visible; }
.v3-table-wrap     { flex: 1; display: flex; ... }
```

### THEMEABLE — safe to restyle

Colors, borders, fonts, shadows, gradients, border-radius on any element.
Card back colors, nameplate backgrounds, button styles, modal backgrounds.

---

## Layout Stability Rules (the mistakes that cost the most time)

### Rule 1: E/W seats must have `align-self: flex-start`
`.v3-middle-row` uses `align-items: center`. Without `align-self: flex-start` on side seats,
any height change in the row (trick overlay, score strip) causes E/W to float up/down.
**Fix is already in place — don't remove it.**

### Rule 2: Conditional strips must always reserve height
Any element that conditionally appears/disappears in the flow causes layout shift.
Use `visibility: hidden` + `minHeight` instead of conditional mounting:
```jsx
// WRONG — causes layout jump
{lastTrick && <div>...</div>}

// RIGHT — height always reserved
<div style={{ visibility: lastTrick ? 'visible' : 'hidden', minHeight: '32px' }}>
  {lastTrick && ...}
</div>
```

### Rule 3: `.v3-facedown-col` needs `min-height: 218px`
When all cards are played, the opponent hand empties. Without min-height the column
collapses and the whole side seat shifts. 218px = 5 cards × 42px + 4 gaps × 2px.

### Rule 4: Overlays inside v3-rail must be `position: absolute`
Trick cards, bid flash, diamond announce, kitty overlay — all must be absolutely
positioned inside the rail. If any are in-flow they'll push other content and cause shifts.

---

## Animation State Variables

All declared in `MultiplayerGameTable` component (~line 10385):

| Variable | Type | Purpose |
|----------|------|---------|
| `dealAnimActive` | boolean | true for 4500ms when dealing starts |
| `kittyOnTable` | boolean | true from deal start until trump selected |
| `kittyFlying` | string\|null | direction ('top'/'bottom'/'left'/'right') when kitty flies |
| `drawAnimCards` | Set\<cardId\> | card IDs being draw-animated for me |
| `drawAnimOpponents` | `{pos: {count, ts}}` | opponent draw animation state |
| `prevDrawnCardsRef` | Ref\<Set\> | detects newly drawn cards (me) |
| `prevDrawnCountsRef` | Ref\<number[]\> | detects drawn count increases (opponents) |
| `bidFlashPrevRef` | Ref\<number[]\> | detects new bids for flash animation |
| `confirmLeave` | boolean | replaces system dialog for leave confirm |
| `diamondAnim` | object\|null | bid winner announce animation data |

### Animation Timing Rules

```javascript
// Deal lock — nothing should fire during deal
const DEAL_LOCK_MS = 4500;

// Draw stagger — must cover all cards
const DRAW_STAGGER_MS = 200; // per card
const drawClearDelay = cardCount * 200 + 700; // NOT a fixed 900ms

// Bid flash — suppress during deal
useEffect(() => {
  if (dealAnimActive) { bidFlashPrevRef.current = [...bids]; return; }
  // ... rest of bid flash logic
}, [bids, dealAnimActive]);
```

---

## CSS Targeting Rules

### When you add a card size variant to a modal, add ALL overrides
The `ir-show-hands-cards` block has rules for `.mid` cards. When E/W needed `.small`
cards, the missing `.small` overrides caused corner suits to reappear.
**Always copy the full set of overrides when adding a size variant:**

```css
/* Add BOTH blocks together: */
.ir-show-hands-cards .cp-card.mid .corner .su { display: none !important; }
.ir-show-hands-cards .cp-card.mid .center { font-size: 18px; }

.ir-show-hands-cards .cp-card.small .corner .su { display: none !important; }
.ir-show-hands-cards .cp-card.small .center { font-size: 14px; }
```

### Irish theme CSS lives in one block
All `.theme-irish` overrides are in a single CSS section. When adding new themed elements,
add them there — not scattered through the stylesheet.

### `@keyframes` must not bake in positioning transforms
If an element is positioned with `position: absolute; top: 50%; left: 50%; transform: translate(-50%,-50%)`,
the keyframe animation must NOT also include `translate(-50%,-50%)` — it will double-shift.
Keep positioning in the element style; keep only scale/opacity/rotation in keyframes.

---

## Font Loading Rule — Embed @font-face Directly

**Never rely on a Google Fonts `<link>` tag or `@import` for a theme's fonts.**
The `fonts.googleapis.com` CSS intermediary is a failure point — it makes two hops
(CSS request → font file request) and can fail silently on some browsers/networks,
including Android Chrome and Windows Chrome. Confirmed broken in the field (April 2026).

**Wrong — two-hop load, can silently fail on any browser:**
```html
<link href="https://fonts.googleapis.com/css2?family=YourFont:wght@700&display=swap" rel="stylesheet">
```

**Correct — get the direct gstatic URLs and embed @font-face in the `<style>` block:**
```html
<style>
  @font-face { font-family: 'YourFont'; font-style: normal; font-weight: 700; font-display: swap;
    src: url(https://fonts.gstatic.com/s/yourfont/v1/...) format('truetype'); }
</style>
```

**How to get the direct URLs for a new theme's fonts:**
1. Construct the Google Fonts CSS2 URL for your fonts and weights
2. Fetch it (e.g. with the WebFetch tool): `https://fonts.googleapis.com/css2?family=YourFont:wght@400;700&display=swap`
3. Copy the `src: url(...)` values from the returned `@font-face` blocks
4. Embed those declarations directly in the HTML `<style>` block

The gstatic URLs contain a version number (e.g. `v26`). If fonts stop loading after a long
time, the version may have changed — re-fetch to get updated URLs.

**Irish Card Room — confirmed working gstatic URLs (April 2026):**
```css
@font-face { font-family: 'Cinzel'; font-weight: 500; font-display: swap; src: url(https://fonts.gstatic.com/s/cinzel/v26/8vIU7ww63mVu7gtR-kwKxNvkNOjw-uTnTYo.ttf) format('truetype'); }
@font-face { font-family: 'Cinzel'; font-weight: 700; font-display: swap; src: url(https://fonts.gstatic.com/s/cinzel/v26/8vIU7ww63mVu7gtR-kwKxNvkNOjw-jHgTYo.ttf) format('truetype'); }
@font-face { font-family: 'Cinzel'; font-weight: 900; font-display: swap; src: url(https://fonts.gstatic.com/s/cinzel/v26/8vIU7ww63mVu7gtR-kwKxNvkNOjw-n_gTYo.ttf) format('truetype'); }
@font-face { font-family: 'Merriweather'; font-style: italic; font-weight: 400; font-display: swap; src: url(https://fonts.gstatic.com/s/merriweather/v33/u-4B0qyriQwlOrhSvowK_l5-eTxCVx0ZbwLvKH2Gk9hLmp0v5yA-xXPqCzLvPee1XYk_XSf-FmTCUF3w.ttf) format('truetype'); }
@font-face { font-family: 'Inter'; font-weight: 400; font-display: swap; src: url(https://fonts.gstatic.com/s/inter/v20/UcCO3FwrK3iLTeHuS_nVMrMxCp50SjIw2boKoduKmMEVuLyfMZg.ttf) format('truetype'); }
@font-face { font-family: 'Inter'; font-weight: 500; font-display: swap; src: url(https://fonts.gstatic.com/s/inter/v20/UcCO3FwrK3iLTeHuS_nVMrMxCp50SjIw2boKoduKmMEVuI6fMZg.ttf) format('truetype'); }
@font-face { font-family: 'Inter'; font-weight: 600; font-display: swap; src: url(https://fonts.gstatic.com/s/inter/v20/UcCO3FwrK3iLTeHuS_nVMrMxCp50SjIw2boKoduKmMEVuGKYMZg.ttf) format('truetype'); }
@font-face { font-family: 'Inter'; font-weight: 700; font-display: swap; src: url(https://fonts.gstatic.com/s/inter/v20/UcCO3FwrK3iLTeHuS_nVMrMxCp50SjIw2boKoduKmMEVuFuYMZg.ttf) format('truetype'); }
```

---

## Multi-Theme JSX Pattern

When there are two or more themes, components branch by theme ID. The module-level variable
`currentThemeId` is readable everywhere without props.

```javascript
// Detection — declare at top of component
const isCyberpunk = currentThemeId === 'cyberpunk';
const isIrish = currentThemeId === 'irish';

// Class switching
<div className={isCyberpunk ? 'cp-lobby-bg' : 'irish-lobby-bg theme-irish'}>

// Inline style switching
style={isCyberpunk ? { color: '#00e5ff', fontFamily: "'Orbitron',sans-serif" }
                   : { color: '#f6d778', fontFamily: "'Cinzel',serif" }}

// Shared structure for themes with same layout
{(isIrish || isCyberpunk) && <div className="compass-grid">...</div>}
```

### Modal Early-Return Pattern

For modals with completely different styling, use an early-return for each theme:

```jsx
function SomeModal({ ... }) {
  if (currentThemeId === 'cyberpunk') {
    return <div className="cp-modal-overlay">...</div>;
  }
  // Irish (default) falls through
  return <div style={{ ...irishStyles }}>...</div>;
}
```

⛔ **Trap:** If a modal only checks `isIrish` and returns null for the else-case, cyberpunk
gets a blank screen. Always add an explicit cyberpunk branch OR a default catch-all. This
broke the GameOver modal — it returned null for cyberpunk until fixed.

---

## ⛔ Card Size Rule — NEVER USE `small` IN ANY THEMED CONTEXT (Irish + Cyberpunk)

**The `small` card variant has NO `.center` element. Any theme that relies on center suit symbols
(Irish, Cyberpunk, and likely any future theme) MUST NOT use `small`.**

The trap is the Card component:
```javascript
const showCenter = !small;  // small cards NEVER render .center
```

This has been re-broken 5+ times across both themes. The rule applies universally.

### Rule: NEVER use `small` cards in any theme. Always use `mid` + CSS wrapper to resize.

Every card context needs its own CSS wrapper class with sized-down `mid` rules:

```css
/* Example: trick strip */
.ir-trick-strip .cp-card.mid { width: 24px; height: 36px; }
.ir-trick-strip .cp-card.mid .corner .su { display: none !important; }
.ir-trick-strip .cp-card.mid .center { font-size: 16px; font-family: Georgia, serif; }

/* Example: E/W show-hands row */
.ir-show-hands-ew .ir-show-hands-cards .cp-card.mid { width: 30px; height: 50px; }
.ir-show-hands-ew .ir-show-hands-cards .cp-card.mid .corner .su { display: none !important; }
.ir-show-hands-ew .ir-show-hands-cards .cp-card.mid .center { font-size: 24px; }
```

And in JSX: `<Card card={c} mid disabled />` — never `small`.

### Last-Trick Strip — must use `mid` cards, not `small`

The "Last:" strip shown during the playing phase has TWO code paths — one for Irish (in-flow,
always reserves height) and one fallback for other themes. The fallback used `small` cards,
which broke the center suit rule.

**Every theme needs its own last-trick strip branch using `mid` cards + the theme's CSS wrapper.**

```jsx
// WRONG — fallback uses small, no center element
{lastTrick && phase === 'playing' && currentThemeId !== 'irish' && (
  <Card card={tc.card} small disabled />  // ← breaks center suit
)}

// CORRECT — explicit branch per theme
{lastTrick && phase === 'playing' && currentThemeId === 'cyberpunk' && (
  <div className="cp-trick-strip" style={{ position: 'relative', padding: 0, borderTop: 'none', marginTop: 0 }}>
    <Card card={tc.card} mid disabled />
  </div>
)}
```

The `.cp-trick-strip .cp-card.mid` CSS must hide corner suits and size the center:
```css
.cp-trick-strip .cp-card.mid { width: 24px; height: 36px; }
.cp-trick-strip .cp-card.mid .corner .su { display: none !important; }
.cp-trick-strip .cp-card.mid .center { font-size: 16px; }
```

### E/W Show-Hands Cards — hide corner suits

The compact E/W cards in the Round Summary must also hide corner suits.
Setting `font-size: 7px` instead of `display: none` keeps the suit visible — wrong.

```css
/* WRONG */
.cp-show-hands-ew .cp-show-hands-cards .cp-card.mid .corner .su { font-size: 7px; }

/* CORRECT */
.cp-show-hands-ew .cp-show-hands-cards .cp-card.mid .corner .su { display: none !important; }
```

---

## ShowHandsModal (Round Summary) — Definitive Layout Spec

This is the most pixel-sensitive modal. Follow these rules exactly for every new theme.

### Card sizes
| Context | Width | Height | Center font | Corner rank |
|---------|-------|--------|-------------|-------------|
| N/S (full) | 30px | 50px | 24px | 9px |
| E/W (compact) | 30px | 50px | 24px | 9px |

Both N/S and E/W use the **same 30×50px card size**. The E/W column is narrower — it fits
because `flex: 1 1 0; minWidth: 0` on the column allows slight overflow without a scrollbar.

### Modal padding — MUST override cp-modal-body
`cp-modal-body` has `padding: 16px` in the global CSS. At 16px the two 30px E/W card rows
**overflow their columns**. Override it inline on this specific modal only:

```jsx
<div className="cp-modal-body" style={{ padding: '12px' }}>
```

This matches Irish's 12px and gives each E/W column enough room.

### E/W container gap
```jsx
<div className="cp-show-hands-ew" style={{ display: 'flex', gap: '8px', ... }}>
```
8px gap (same as Irish).

### ⛔ NEVER add `overflow-x: auto` to the card strip container

This is the most common mistake. With `overflow-x: auto`, any card that overflows by even
1–2px shows a scrollbar on Android Chrome. Irish works fine because it never had it — the
cards silently overflow by a pixel inside their flex column without any scrollbar.

```css
/* WRONG — creates scrollbar on Android Chrome even at 1px overflow */
.cp-show-hands-ew .cp-show-hands-cards {
  overflow-x: auto;
}

/* CORRECT — let flex handle it silently */
.cp-show-hands-ew .cp-show-hands-cards {
  flex-wrap: nowrap;
  overflow: visible;
  justify-content: flex-start;
}
```

**Root cause of multiple regression cycles:** early cyberpunk session added `overflow-x: auto`
"for safety." This then required card shrinking and padding hacks across several versions.
The fix was to simply remove it and match Irish exactly.

---

## Bid/Pass Badge — Visibility Rule

Bid and pass badges in ShowHandsModal must **pop against the dark background** the same way
Irish uses a colored fill to make them stand out.

**Wrong — near-black background blends into the modal:**
```javascript
// rgba(2,18,10,0.96) is essentially black — badge is invisible against dark modal bg
background: 'rgba(2,18,10,0.96)'
```

**Correct — use a solid-tinted fill that creates a visible colored block:**
```javascript
// Cyberpunk green bid badge
const cpBidBg = isBag
  ? 'rgba(255,0,204,0.22)'   // magenta-tinted for BAGGED
  : isBidder
  ? 'rgba(0,255,136,0.22)'   // green-tinted for bid winner
  : 'rgba(0,255,136,0.12)';  // lighter green for PASS

// Matching border + glow
const cpBidBorder = isBag ? '#ff00cc' : '#00ff88';
const cpBidShadow = isBidder
  ? '0 0 14px rgba(0,255,136,0.9), 0 0 30px rgba(0,255,136,0.4)'
  : '0 0 8px rgba(0,255,136,0.55), 0 0 16px rgba(0,255,136,0.2)';
const cpBorderWidth = isBidder && !isBag ? '2px' : '1.5px';
```

The key insight: **the fill opacity (0.22) is what makes it visible**, not just the border glow.
A dark near-transparent fill + glow looks like text floating in space. A tinted fill looks like
a badge.

### Suit glyph font rule (also critical)

`.center` and `.corner .su` must use `font-family: Georgia, 'Times New Roman', serif`.
Cinzel does not contain ♠ ♥ ♦ ♣ — suits silently vanish without this override.

```css
.theme-irish .cp-card .center        { font-family: Georgia, 'Times New Roman', serif; }
.theme-irish .cp-card .corner .su    { font-family: Georgia, 'Times New Roman', serif; }
```

**Side effect of fixing fonts:** Cinzel is more compact than the system serif fallback —
card center font sizes may need increasing after a font fix.

---

## Font Quoting Rule — React Inline Styles

**Always quote font names with inner single quotes inside the JS string:**

```javascript
// WRONG — browser may treat "Cinzel, serif" as a single unknown font name
fontFamily: 'Cinzel, serif'

// CORRECT — generates font-family: 'Cinzel', serif in CSS
fontFamily: "'Cinzel', serif"
fontFamily: "'Merriweather', Georgia, serif"
fontFamily: "'Inter', sans-serif"
```

Why it breaks: `fontFamily: 'Cinzel, serif'` passes the JS string `Cinzel, serif` directly into
the CSS `font-family` property. Some browsers parse this as a single unknown font name and fall
back to the inherited body font (Palatino in this app). Wrapping the name in inner single-quotes
generates proper CSS that matches the Google Fonts `@font-face` declaration.

**Note:** The body font is `'Palatino Linotype', Palatino, Georgia, serif`. Any element that fails
to load Cinzel/Inter/Merriweather will silently fall back to Palatino — which looks completely
different but gives no error.

---

## Gradient Text Rule — Never Use WebkitTextFillColor on Critical Text

The `-webkit-text-fill-color: transparent` + `background-clip: text` gradient technique is
unreliable on mobile. When the clip fails, text becomes **completely invisible** with no warning.
When the font also fails to load, the result looks like the wrong font in a wrong color.

```javascript
// WRONG — silently invisible if clip fails on mobile
{
  background: 'linear-gradient(135deg, #f6d778, #c9a24a)',
  WebkitBackgroundClip: 'text',
  WebkitTextFillColor: 'transparent',
}

// CORRECT — solid gold, always visible, always Cinzel
{
  color: '#f6d778',
  fontFamily: "'Cinzel', serif",
}
```

Use solid `color: '#f6d778'` (brassHi) for all headings and labels. Reserve gradient-text only
for large decorative numbers (hero stat card) where invisibility is immediately obvious.

---

## Badge Symbol Rendering Rule

Badge `sym` values are emoji (`'⚡'`, `'🏆'`, `'⚜️'`) and text (`'30'`, `'W10'`).

**Always use `fontSize: '22px'` — never use `.length` to choose the size.**

```javascript
// WRONG — JS .length returns 2 for almost all emoji (surrogate pairs in UTF-16)
// so length===2 → 15px fires for every emoji, never 22px
fontSize: sym.length <= 1 ? '22px' : sym.length === 2 ? '15px' : ...

// CORRECT — fixed size, works for all symbols
fontSize: '22px'
```

Most emoji occupy two UTF-16 code units (`.length === 2`), so any `length === 1` branch is
unreachable in practice. Always use a fixed `22px` for badge circles.

Font: `fontFamily: "'Cinzel', serif"` on the span. Browsers override Cinzel with emoji rendering
automatically, so it's safe to apply Cinzel universally.
Color: `earned ? brassHi : 'rgba(255,255,255,0.4)'`

---

## Badge Grid Rule — Equal Columns

Use `minmax(0, 1fr)` not `1fr` for the badge grid. The standard `1fr` is shorthand for
`minmax(auto, 1fr)`, which allows columns to grow to fit their content. `minmax(0, 1fr)` enforces
truly equal widths regardless of content.

```javascript
// WRONG — columns can be uneven if any badge name overflows
gridTemplateColumns: 'repeat(5, 1fr)'

// CORRECT — strictly equal columns
gridTemplateColumns: 'repeat(5, minmax(0, 1fr))'
```

---

## iOS Safari Viewport Rule

`100vh` on iOS Safari is calculated including the area behind the browser toolbar, so content
at the bottom is hidden. The `.v3-phone` element (game table root) must NOT have an inline
`height: '100%'` — that overrides the CSS declarations.

**CSS on `.v3-phone` (already in place — do not remove):**
```css
.v3-phone {
  height: 100vh;                   /* fallback */
  height: -webkit-fill-available;  /* older Safari/Chrome */
  height: 100dvh;                  /* modern — adjusts with toolbar */
  overflow: hidden;
  padding-bottom: env(safe-area-inset-bottom); /* iPhone home indicator ~34px */
}
```

**JSX — `.v3-phone` inline style must NOT include `height`:**
```jsx
// WRONG — inline style overrides the CSS above; table gets cut off on iPhone
<div className="v3-phone theme-irish" style={{ height: '100%', display: 'flex', ... }}>

// CORRECT — let CSS handle height
<div className="v3-phone theme-irish" style={{ display: 'flex', flexDirection: 'column', color: '#e8e4d9' }}>
```

The same `.fs-screen` class on lobby/waiting room already uses this 3-value stack correctly.

---

## Close Button Rule — Rounded Bottom-Sheet Modals

A `position: absolute` close button centered with `top: '50%', transform: 'translateY(-50%)'`
inside a small pill/header div will overflow the div upward and get clipped by the parent
modal's `overflow: hidden` and `border-radius`.

```javascript
// WRONG — 32px button at top:50% of a 24px container overflows 4px upward
// → clipped by the modal's 20px border-radius
{ position: 'absolute', top: '50%', right: '16px', transform: 'translateY(-50%)', height: '32px' }

// CORRECT — explicit top clears the rounded corner (20px border-radius needs ~8px clearance)
{ position: 'absolute', top: '10px', right: '16px', height: '32px' }
```

Any bottom sheet with `borderRadius: '20px 20px 0 0'` clips anything above ~8px from its top
edge. Position close buttons at `top: '10px'` minimum.

---

## Stats Modal — All-Gold Accents, No isMe Split

The stats/badges modal uses gold/brass for ALL players, including the viewing player's own profile.
There is no blue-for-me color split.

```javascript
// WRONG — shows blue accents when viewing own profile
const accentColor = isMe ? meBlue : brass;
const accentHi    = isMe ? '#a8d8ff' : brassHi;

// CORRECT — always gold
const accentColor = brass;   // '#c9a24a'
const accentHi    = brassHi; // '#f6d778'
```

---

## Avg Win Bid Formula

Gate on `bids30Won > 0`, not `bidAttempts > 0`. `bidAttempts = bids30Won + timesSet`, so a
player with 0 wins and 10 sets would pass the `bidAttempts > 0` check and show `0.0` instead of `—`.

```javascript
// WRONG — shows 0.0 when player has been set but never won a 30-bid
bids30Won * 30 / Math.max(bidAttempts, 1)  // with gate: bidAttempts > 0

// CORRECT
bids30Won > 0 ? (bids30Won * 30 / Math.max(bidAttempts, 1)).toFixed(1) : '—'
```

---

## Shared Render Functions — Must Be Theme-Aware

`ShowHandsModal` uses a shared `renderHand()` function that renders both the Irish and cyberpunk
card hands in the Round Summary. When the cyberpunk early-return branch was added to the modal,
`renderHand` still had hardcoded Irish values (Cinzel font, brass colors). Those showed through
in cyberpunk mode.

**Rule: any shared helper function that outputs visible UI must check `isCyberpunk` (or the
theme ID) for every color, font, and border it renders.**

Key values `renderHand` must branch on:
| Element | Irish | Cyberpunk |
|---------|-------|-----------|
| Player name font | `'Cinzel', serif` | `'Orbitron', sans-serif` |
| Draw count font | `'Merriweather', serif` | `'Share Tech Mono', monospace` |
| Trick number circles | brass `#c9a24a` border + color | cyan `#00e5ff` border + color |
| Led-trick border | `brassHi` `#f6d778` | `#00e5ff` |
| Bid badge font | Cinzel | Share Tech Mono |
| Bid badge bid color | brassHi | cyan |
| Bid badge bag color | `#ff6b6b` | `#ff00cc` (magenta) |
| Dealer D badge bg | brass radial gradient | amber `rgba(255,140,0,0.15)` + amber border |

---

## Lobby Background — Must Be Fixed-Height Flex Container

The lobby body uses a flex chain to make the leaderboard tab scrollable:

```
.lobby-bg  (flex column, fixed height)
  └─ .irlb-screen  (flex:1, overflow:hidden)
       └─ .irlb-scroll  (flex:1, overflow-y:auto)  ← this scrolls
            └─ leaderboard list
```

For this chain to work, the root `lobby-bg` class **must** use `height` not `min-height`, and
must be a flex column container with `overflow:hidden`.

```css
/* WRONG — breaks scroll chain, leaderboard won't scroll */
.cp-lobby-bg {
  min-height: 100dvh;
  /* no display:flex, no overflow:hidden */
}

/* CORRECT — matches Irish lobby pattern */
.cp-lobby-bg {
  height: 100vh;
  height: -webkit-fill-available;
  height: 100dvh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
```

Any new theme's lobby root class must follow this same pattern.

---

## Stats Modal — Must Show All 12 Boxes + Last Seen

The stats modal (popup when tapping a player in lobby/leaderboard) must show exactly:

| Box | Value |
|-----|-------|
| Games Played | `gamesPlayed` |
| Wins | `gamesWon` |
| Losses | `gamesPlayed - gamesWon` |
| Win % | `gamesWon/gamesPlayed * 100` |
| Cur Streak 🔥 | `currentStreak` |
| Max Streak ⭐ | `bestStreak` |
| Bids Made | `bid15Made + bid20Made + bid25Made + bid30Made + baggedBidMade` |
| Bid % | `bidsWon / (bidsWon + timesSet) * 100` |
| Times Set | `timesSet` |
| Perfect 30s | `perfect30s` |
| Quits | `gamesQuit` |
| Avg Win Bid | `totalBidPts / bidsWon` (or `—`) |
| Last Seen (full-width) | formatted timestamp |

**Cyberpunk initial implementation had only 6 boxes.** When implementing a new theme's stats
modal, always compare against the Irish version to ensure all 12 + Last Seen are present.

---

## Leaderboard Avatar Chips — Must Be Theme-Specific

The leaderboard row renders a player avatar circle. The Irish version used a green felt
background (`background: '#13572a'`). This was hardcoded and showed through in cyberpunk.

Every theme needs its own avatar chip style. Use a conditional className:

```jsx
// In renderIrishLbRow (shared by Irish + Cyberpunk)
<div className={isCyberpunk ? 'cp-lb-avatar' : 'irlb-lb-avatar'} ...>
  {getAvatarById(p.avatar).emoji}
</div>
```

```css
/* Irish */
.irlb-lb-avatar { background: #13572a; border: 1.5px solid #c9a24a; ... }

/* Cyberpunk */
.cp-lb-avatar { background: rgba(0,229,255,0.06); border: 1.5px solid rgba(0,229,255,0.35); ... }
```

Any shared render function that outputs a colored element must be checked for hardcoded
Irish/theme values whenever a new theme is added.

---

## Cyberpunk Card Rank Corners

Cyberpunk cards use Orbitron Bold for rank characters in corners to improve readability
(the default system font was too thin on dark backgrounds):

```css
.theme-cyberpunk .cp-card .corner .rk {
  font-family: 'Orbitron', sans-serif;
  font-weight: 700;
}
/* Size by card variant */
.theme-cyberpunk .cp-card.small .corner .rk { font-size: 10px; }
.theme-cyberpunk .cp-card.mid .corner .rk   { font-size: 14px; }
.theme-cyberpunk .cp-card.large .corner .rk { font-size: 19px; }
```

When adding a new theme with a custom heading font, apply it to `.corner .rk` as well.

---

## Version Bump Rule

**Every time `VERSION` is changed, a matching entry MUST be added to `versionHistory` in `WhatsNewModal`.**
The array is at the top of `WhatsNewModal` (~line 4424). The newest entry goes first.
Skipping this causes the What's New modal to show an outdated version number and missing entries.

```javascript
const versionHistory = [
  { version: '2.27.41', date: 'Apr 2026', changes: ['Description of what changed.'] },
  // ... older entries below
];
```

---

## Deleting Dead Code — Full Removal Checklist

When removing a modal or feature, grep for ALL related symbols before committing:

```
// If you delete a modal, also delete:
const [modalState, setModalState] = useState(...)   // the state declaration
setModalState(...)                                   // ALL setter calls (may be in other functions)
modalState && (...)                                  // the render gate
```

**The setStatsTab lesson:** The old tabbed stats modal was deleted and `statsTab` state removed,
but `setStatsTab('stats')` inside `fetchPlayerStats` was missed. This caused a runtime crash
whenever a player was tapped in the leaderboard.

**Rule:** After deleting any `useState`, grep for the setter name (`set<X>`) before pushing.

---

## Modal Rules

**NEVER use `window.confirm`, `window.alert`, or `window.prompt`.**
All confirmations use React state + a themed modal JSX block.

```jsx
// WRONG
if (window.confirm('Leave game?')) { ... }

// RIGHT
const [confirmLeave, setConfirmLeave] = useState(false);
// ... render a themed modal when confirmLeave === true
```

---

## WaitingRoom — No Loading Screens

The WaitingRoom has an early return for when Firebase hasn't loaded the game node yet.
This must return `null`, not a loading div. A loading div flashes visibly during the
Start Game transition because Firebase briefly hasn't synced.

```jsx
// WRONG — flashes a plain unstyled screen on Start Game
if (!game) {
  return <div style={{ color: 'white', ... }}>Loading game...</div>;
}

// CORRECT — invisible during the brief sync window
if (!game) {
  return null;
}
```

---

## GameWrapper Init Screen

```jsx
// CORRECT — return null so waiting room stays visible during init
if (!gameState || !gameState.initialized) {
  return null;
}
```

Never show a loading screen here — it flashes old UI.

---

## `visualPositions` — Compass Mapping

```javascript
const visualPositions = {
  bottom: mySeatIndex,
  top:    (mySeatIndex + 2) % 4,
  left:   (mySeatIndex + 1) % 4,
  right:  (mySeatIndex + 3) % 4,
};
```

Use this everywhere NSEW position is needed. Never hardcode seat indices.
Bid flash, diamond arrow, deal origin, draw animation direction — all derive from this.

---

## Screens That Need Theming (complete list)

For each new theme, every one of these needs a themed implementation:

1. **Login** — form, background, button
2. **Lobby root bg** — `height:100dvh + overflow:hidden + display:flex` (NOT `min-height`) — required for leaderboard scroll
3. **Lobby topbar** — logo, title, version number (tappable → release notes)
4. **Lobby game list** — rows, status badges, seat pips
5. **Lobby leaderboard tab** — rank rows, top-3 treatment, badges, **avatar chips** (theme-specific class, not hardcoded color)
6. **Lobby online strip** — presence dots, usernames
7. **Lobby action buttons** — Create Game, Refresh, tabs
8. **Waiting room** — compass grid, seat cards, player chips, Start button
9. **Seat picker** — compass layout, seat selection
10. **Game table nameplates** — me/partner/opponent variants, active glow
11. **Bid buttons** — primary/ghost/disabled states
12. **Trump select buttons** — suit buttons (red suits vs black suits may glow differently)
13. **Follow-suit toast** — alert strip
14. **Score strip** — tap-to-expand, column order (+pts LEFT of total)
15. **Last-trick strip** — always reserves height during playing phase; **each theme needs its own branch using `mid` cards** (never `small`) — see card size rule
16. **Trick overlay** — cards in center rail (absolutely positioned)
17. **Bid flash animation** — large floating text at bidder compass position
18. **Diamond announce** — centered in rail, directional arrow to bid winner
19. **Deal animation** — cards fly from dealer direction, 3-3-3-kitty-2-2-2-2 sequence
20. **Kitty overlay** — 3 cards on table, flies to bid winner on trump select
21. **Draw animation** — newly drawn cards slide in (all 4 players, 200ms stagger)
22. **Dealer chip** — `D` badge on dealer's nameplate (cyberpunk: amber pulse glow animation)
23. **Bid coin/pass badge** — bid amount indicators on nameplates during bidding
24. **ShowHandsModal** — 4 players, E/W compact (use `mid` sized down via CSS, NEVER `small`), large center suit
25. **Stats/badges modal** — **all 12 stat boxes + Last Seen** (compare against Irish; cyberpunk v2.28 shipped with only 6 initially)
26. **Round-end modal (ShowHandsModal)** — see *ShowHandsModal Definitive Layout Spec* section above; 30×50px cards, 12px body padding override, 8px EW gap, NO `overflow-x:auto`; `renderHand()` helper must be theme-aware (fonts, colors); corner suits hidden on all cards
27. **Game-over modal** — winner announcement (⛔ must handle ALL themes — returning null for non-Irish breaks it)
28. **Preferences modal** — house rules, theme tiles (themes live HERE not in profile)
29. **Leave confirm modal** — themed, never system dialog
30. **GameWrapper init** — return null

---

## Agent Prompt Requirements

When briefing an agent to implement theme work:
- **Include exact CSS values** — not "match the mockup", paste the actual hex/px values
- **Name the exact line numbers** to edit when possible
- **Specify the exact class** the new rule should live in (`.theme-irish` block, `ir-show-hands-cards`, etc.)
- **Include the layout stability rules** above as context — agents commonly break these
- After implementation, run through `THEMING_CHECKLIST.md` before reporting done
