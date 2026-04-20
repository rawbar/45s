# 45s Theming — Lessons & Architecture

Everything an agent needs to implement a new theme correctly the first time.
Derived from the Irish Card Room theming session (v2.26–v2.27.47).

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
2. **Lobby topbar** — logo, title, version number (tappable → release notes)
3. **Lobby game list** — rows, status badges, seat pips
4. **Lobby leaderboard** — rank rows, top-3 treatment, badges
5. **Lobby online strip** — presence dots, usernames
6. **Lobby action buttons** — Create Game, Refresh, tabs
7. **Waiting room** — compass grid, seat cards, player chips, Start button
8. **Seat picker** — compass layout, seat selection
9. **Game table nameplates** — me/partner/opponent variants, active glow
10. **Bid buttons** — brass/ghost/disabled states
11. **Trump select buttons** — suit buttons
12. **Follow-suit toast** — alert strip
13. **Score strip** — tap-to-expand, column order (+pts LEFT of total)
14. **Last-trick strip** — always reserves height during playing phase
15. **Trick overlay** — cards in center rail (absolutely positioned)
16. **Bid flash animation** — large floating text at bidder compass position
17. **Diamond announce** — centered in rail, directional arrow to bid winner
18. **Deal animation** — cards fly from dealer direction, 3-3-3-kitty-2-2-2-2 sequence
19. **Kitty overlay** — 3 cards on table, flies to bid winner on trump select
20. **Draw animation** — newly drawn cards slide in (all 4 players, 200ms stagger)
21. **ShowHandsModal** — 4 players, E/W compact (small cards), large center suit
22. **Stats/badges modal** — bottom sheet, single scroll, badge detail as floating overlay
23. **Round-end modal** — scores, trick breakdown
24. **Game-over modal** — winner announcement
25. **Preferences modal** — house rules, theme tiles (themes live HERE not in profile)
26. **Leave confirm modal** — themed, never system dialog
27. **GameWrapper init** — return null

---

## Agent Prompt Requirements

When briefing an agent to implement theme work:
- **Include exact CSS values** — not "match the mockup", paste the actual hex/px values
- **Name the exact line numbers** to edit when possible
- **Specify the exact class** the new rule should live in (`.theme-irish` block, `ir-show-hands-cards`, etc.)
- **Include the layout stability rules** above as context — agents commonly break these
- After implementation, run through `THEMING_CHECKLIST.md` before reporting done
