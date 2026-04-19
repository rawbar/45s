# Theming Implementation Guide — 45s

A reusable reference for applying any design language to the 45s single-file React app.
Future Claude sessions: read this before starting any theming work.

---

## 1. How the Theme System Works

### CSS Architecture
The app uses three CSS injection blocks in `<head>`:
- **Lines 21–31** — Global animations (fadeIn, slideUp, cardPlay, pulse, voicePulse, scoreChange)
- **Lines 39–643** — Irish Card Room design system (tokens, layout, card faces, table, components)
- **Lines 646–1182** — Shared `cp-card` shell + Cyberpunk theme overrides

**All theme-specific CSS is scoped under a theme class on the root container:**
```css
.theme-irish  .cp-card { ... }
.theme-cyberpunk .cp-card { ... }
```

The root container gets the class at runtime:
```javascript
let currentThemeId = 'irish';  // module-level, updated when user changes theme
// Applied in render:
<div className={`theme-${currentThemeId}`} ...>
```

### THEMES Config (around line 1169)
```javascript
const THEMES = {
  irish: {
    id: 'irish',
    name: 'Irish Card Room',
    cssClass: 'theme-irish',
    cardLayout: 'flat',         // 'flat' = straight row; 'fan' = rotated fan
    unlocked: (stats) => true,  // always available
    unlockHint: null,
    progressLabel: null
  },
  cyberpunk: {
    id: 'cyberpunk',
    name: 'Cyberpunk',
    cssClass: 'theme-cyberpunk',
    cardLayout: 'fan',
    unlocked: (stats) => (stats?.gamesPlayed || 0) >= 25,
    unlockHint: 'Play 25 games to unlock',
    progressOf: 25,
    progressStat: 'gamesPlayed'
  },
};
const THEME_ORDER = ['irish', 'cyberpunk'];
```

### Adding a New Theme
1. Add entry to `THEMES` + `THEME_ORDER`
2. Add a CSS block under `.theme-newtheme { ... }` at the bottom of the style block
3. Add thumbnail tile to the theme picker (both the gear/preferences modal and settings modal use the same tile renderer)
4. Store selected theme in Firebase at `users/${uid}/settings/theme`

---

## 2. Component Map (Screen → Line Numbers)

### Full-Page Screens
| Screen | Line | Description |
|--------|------|-------------|
| LoginScreen | ~4485 | Username/PIN auth, avatar selection |
| LobbyScreen | ~5060 | Game list, create game, settings |
| WaitingRoom | ~7311 | Pre-game seat selection |
| GameWrapper | ~8322 | Firebase sync wrapper |
| MultiplayerGameTable | ~8565 | Main game play surface |
| MultiplayerApp | ~8068 | Root router component |

### Modals / Dialogs
| Modal | Line | Trigger |
|-------|------|---------|
| WhatsNewModal | ~3782 | App startup, new version |
| HelpModal | ~3941 | ? button in game |
| RulesModal | ~4041 | Rules tab in help |
| ShowHandsModal | ~4335 | "Show Hands" button |
| House Rules Toast | ~11161 | Game start if house rules active |

### LobbyScreen State-Driven Overlays
| Panel | State var | Line |
|-------|-----------|------|
| Create Game Dialog | showCreateGame | ~5063 |
| Game Options Panel | showGameOptions | ~5065 |
| Settings Modal | showSettings | ~5073 |
| Avatar Picker | showAvatarPicker | ~5076 |
| Theme Preview | showThemePreview | ~5079 |
| Player Stats Modal | showStatsModal | ~5085 |
| Leaderboard Modal | showLeaderboard | ~5095 |
| Preferences Modal | showPreferences | ~5104 |

### Reusable Components
| Component | Line | Notes |
|-----------|------|-------|
| Card | ~3695 | cp-card class, sizes: small/mid/large, fanStyle prop |
| TricksWonDisplay | ~3672 | 5 pip dots, optional vertical |
| CardsDrawnIndicator | ~3682 | "+N" label |
| DealerBadge | ~3687 | "D" badge |
| ScoreTable | ~3750 | Round history grid |
| GameListItem | ~7005 | Lobby game card |

---

## 3. Style Injection Pattern

All theme CSS lives in the `<style>` block inside `<head>`. To add theme styles:

1. Find the end of the Cyberpunk block (~line 1182)
2. Add a new scoped block:
```css
/* ============================================================
   THEME: [Theme Name]
   ============================================================ */

.theme-newtheme {
  /* CSS custom properties / tokens */
  --bg: #...;
  --accent: #...;
}

.theme-newtheme .cp-card { ... }
.theme-newtheme .cp-card.small { ... }
.theme-newtheme .cp-card.mid { ... }
.theme-newtheme .cp-card.large { ... }
/* etc. */
```

**Note:** Inline styles in JSX components take precedence over CSS classes. For screens that use 100% inline styles (LobbyScreen, LoginScreen, etc.), you need to either:
- Pass theme-dependent style objects from a theme config, OR
- Use a CSS class override with `!important` (last resort)
- Inject conditional logic based on `currentThemeId`

The game table (MultiplayerGameTable) uses `cp-card` classes heavily and is easiest to theme.
Lobby/Login use mostly inline styles — harder, requires either theme style maps or inline conditionals.

---

## 4. Design Token Application Pattern

### Defining Tokens
```css
.theme-irish {
  --wood-dark: #2d1a0e;
  --felt: #1a4a2e;
  --brass: #b8860b;
  --paper: #f5f0e8;
  /* ... */
}
```

### Consuming Tokens in CSS
```css
.theme-irish .cp-card { background: var(--paper); border-color: var(--brass); }
```

### Consuming Tokens in Inline JSX Styles
For components with inline styles, use a theme helper:
```javascript
function getThemeTokens() {
  if (currentThemeId === 'irish') return {
    bg: '#1a4a2e', accent: '#b8860b', text: '#f5f0e8', ...
  };
  if (currentThemeId === 'cyberpunk') return {
    bg: '#020509', accent: '#00e5ff', text: '#c0ddf0', ...
  };
  return {}; // fallback
}
// Use in component:
const T = getThemeTokens();
<div style={{ background: T.bg, color: T.text }}>
```

---

## 5. Card Layout Modes

### Flat (Irish Card Room default)
Cards render in a straight horizontal row. No transforms applied.
```jsx
// cardLayout === 'flat'
<div style={{ display:'flex', gap:'4px', justifyContent:'center' }}>
  {hand.map(card => <Card key={card.id} card={card} ... />)}
</div>
```

### Fan (Cyberpunk)
Cards use per-position rotation + Y translation transforms. Config:
```javascript
const FAN_CONFIG = {
  5: { t:[{r:-9,y:9},{r:-4,y:3},{r:0,y:0},{r:4,y:3},{r:9,y:9}], z:[1,2,3,4,5], m:-14 },
  6: { t:[{r:-10,y:10},{r:-6,y:4},{r:-2,y:1},{r:2,y:1},{r:6,y:4},{r:10,y:10}], z:[1,2,3,4,5,6], m:-10 },
  7: { t:[...], z:[1,2,3,4,5,6,7], m:-8 },
  8: { t:[...], z:[1,2,3,4,5,6,7,8], m:-6 },
};
```
- `t[i].r` = rotation degrees (negative = left lean)
- `t[i].y` = translateY pixels (positive = lower)
- `z[i]` = z-index (left-to-right increasing = right card on top)
- `m` = margin-right px (negative = overlap)
- `transform-origin: bottom center` on each card

Playable card overrides: `rotate(0deg) translateY(-14px)`, z-index 5.

---

## 6. Mockup-First Workflow

For each screen or dialog:

**Step 1 — Standalone HTML Mockup**
Create `mockups/[screen]-[theme].html` as a self-contained HTML file.
- Copy the relevant JSX structure and convert to static HTML
- Apply the design language directly with inline styles / CSS
- No Firebase, no React — just the visual
- **Read `table-mockup-v3.html` before starting any Irish mockup** — copy exact gradient stacks, don't approximate. Approximated tokens produce generic "web form" look, not card room atmosphere.
- Show all relevant states in one file (login/register, normal/error, etc.) separated by a spacer and a mockup-label div
- **Always include the desktop scaler** (see below) — without it the 390px phone frame looks tiny on a Windows/Mac desktop browser

**Desktop preview scaler — include in every mockup with a `.phone` frame:**
```css
.phone-scaler {
  transform-origin: top center;
  transform: scale(calc(88vh / 844px));
  /* transform doesn't affect layout — box stays 844px tall.
     Scaled visual height = 88vh. Push next sibling down to visual bottom + 40px gap. */
  margin-bottom: calc(88vh - 844px + 40px);
}
```

**Body layout for mockups with multiple states — always vertical stack:**
```css
body {
  display: flex;
  flex-direction: column;   /* ← critical: stack states vertically, not side by side */
  align-items: center;
  padding: 24px 12px 80px;
  gap: 0; /* gap handled by phone-scaler margin-bottom */
}
```

**Why vertical not horizontal:** `transform: scale()` doesn't affect the layout box — the phone stays 390px wide in the document flow even when visually scaled to ~700px wide. Side-by-side placement means the second phone's layout box starts at 390px and visually overlaps the first. Always stack vertically.

Wrap every `<div class="phone">` with `<div class="phone-scaler">...</div>`.
The canonical 390×844px internal dimensions stay unchanged — this only affects desktop preview.

**Step 2 — User Review**
Present mockup for approval before touching production code.
Changes at mockup stage cost ~100 tokens. Changes after wiring cost ~1000+ tokens.
Iterate until approved — don't implement partial designs.

**Step 3 — Extract CSS/Tokens**
From the approved mockup, extract:
- Color tokens
- Typography rules
- Shadow/border recipes
- Layout constants

**Step 4 — Implement**
Apply to index-themes.html via:
1. CSS additions in the theme style block (for cp-card and themed CSS classes)
2. `getThemeTokens()` updates (for inline-style components)
3. Conditional JSX (for structural differences between themes)

**Step 5 — Test + Sync**
```bash
cp index-themes.html index.html
git add index-themes.html index.html
git commit -m "vX.Y.Z: [Theme] [Screen] implementation"
git push
```

---

## 7. Irish Card Room Design Tokens

**Source of truth: `table-mockup-v3.html`** — always read that file for exact values.
`STYLE_GUIDE_V3.md` is a prose spec; the HTML is the authoritative implementation.
Approved login mockup: `mockups/login-irish-v2.html` — use it as the style reference for all auth/lobby screens.

### Colors (from table-mockup-v3.html :root)
```
/* Wood */
--wood-1:      #4a2712    walnut, mid
--wood-2:      #341807    walnut, dark
--wood-3:      #1e0e04    walnut, darkest
--wood-high:   #a26a3a    walnut, highlight grain

/* Felt */
--felt-1:      #1f7a3f    emerald felt, light
--felt-2:      #13572a    emerald felt, main
--felt-3:      #093a1a    emerald felt, dark
--felt-shadow: #051f0c    emerald felt, deepest shadow

/* Brass */
--brass-hi:    #f6d778    brass, highlight / sheen
--brass:       #c9a24a    brass, main
--brass-lo:    #5a3f16    brass, dark / shadow

/* Card paper */
--paper-1:     #fbf6e4    card face, bright
--paper-2:     #f1e8cf    card face, shadow
--paper-edge:  #9b8d6a    card edge / worn
--ink:         #1a1409    card text, black suits
--red:         #a81824    card text, red suits

/* Team / UI */
--team-us:     #5dd084    score green
--team-them:   #ef7c74    score red/pink
--me-blue:     #6bb6ff    "me" player highlight
--lamp:        #ffd288    warm pendant light color
```

### Typography
```
Cinzel         — brand "45s", screen titles, labels, tab buttons (weights: 500, 700, 900)
Merriweather   — card ranks, PIN digits, player names, body (weights: 700, 900)
Inter          — small labels, hints, secondary UI (weights: 400, 500, 600, 700)
```
Note: `Playfair Display` is also loaded in the table mockup but not prominently used — stick to Cinzel/Merriweather/Inter.

### Material Recipes (copy-paste ready CSS)

**Walnut wood background** — use on full-screen surfaces (body / root container):
```css
background-color: #180b03;
background-image:
  /* 1. warm pendant lamp spotlight */
  radial-gradient(ellipse 95% 55% at 50% -5%,
    rgba(255,210,136,0.28) 0%, rgba(255,180,110,0.1) 30%, transparent 60%),
  /* 2. satin lacquer sheen */
  linear-gradient(180deg,
    rgba(255,220,175,0.08) 0%, rgba(255,220,175,0.03) 22%, transparent 52%),
  /* 3. amber chatoyance streaks */
  linear-gradient(92deg,
    transparent 4%,  rgba(255,220,168,0.055) 7%,  transparent 11%,
    transparent 20%, rgba(255,205,148,0.04)  24%, transparent 29%,
    transparent 44%, rgba(255,215,160,0.06)  49%, transparent 54%,
    transparent 66%, rgba(255,208,148,0.045) 71%, transparent 76%,
    transparent 86%, rgba(255,218,168,0.05)  91%, transparent 96%),
  /* 4. dark grain shadow streaks */
  linear-gradient(91deg,
    transparent 13%, rgba(0,0,0,0.12) 15%, transparent 17%,
    transparent 28%, rgba(0,0,0,0.09) 30%, transparent 32%,
    transparent 51%, rgba(0,0,0,0.14) 53%, transparent 55%,
    transparent 64%, rgba(0,0,0,0.1)  66%, transparent 68%,
    transparent 81%, rgba(0,0,0,0.11) 83%, transparent 85%),
  /* 5. SVG turbulence — organic wood fiber noise */
  url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='390' height='844'><filter id='g'><feTurbulence type='turbulence' baseFrequency='0.35 0.008' numOctaves='2' seed='7' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 0.06  0 0 0 0 0.025  0 0 0 0 0.01  0.45 0 0 0 0'/></filter><rect width='100%' height='100%' filter='url(%23g)'/></svg>"),
  /* 6. base walnut */
  linear-gradient(172deg, #3a2312 0%, #281609 35%, #180b03 68%, #1f0f05 100%);
background-repeat: no-repeat;
background-size: cover;
```

**Edge vignette** (add as ::after on the background container):
```css
background: radial-gradient(ellipse 110% 80% at 50% 50%, transparent 40%, rgba(0,0,0,0.6) 100%);
```

**Brass frame** — outer wrapper for panels/cards:
```css
background: conic-gradient(
  from 135deg,
  #5a3f16 0deg,  #c9a24a 60deg, #f6d778 120deg,
  #c9a24a 180deg, #5a3f16 240deg, #c9a24a 300deg,
  #f6d778 330deg, #5a3f16 360deg
);
border-radius: 8px;
padding: 3px;
box-shadow:
  0 0 0 1px rgba(0,0,0,0.9),
  0 16px 50px rgba(0,0,0,0.75),
  inset 0 1px 0 rgba(246,215,120,0.5);
```

**Emerald felt surface** — inner panel content area:
```css
background-color: #13572a;
background-image:
  radial-gradient(circle, rgba(255,255,255,0.055) 1px, transparent 1px),
  radial-gradient(ellipse 90% 40% at 50% -10%, rgba(31,122,63,0.6) 0%, transparent 70%);
background-size: 6px 6px, 100% 100%;
border-radius: 6px;
/* Inner rim shadow */
box-shadow: inset 0 2px 12px rgba(0,0,0,0.5), inset 0 -2px 8px rgba(0,0,0,0.3);
```

**Brass gradient text** (for "45s" brand):
```css
background: linear-gradient(180deg, #f6d778 0%, #c9a24a 45%, #8a6421 100%);
-webkit-background-clip: text;
background-clip: text;
color: transparent;
filter: drop-shadow(0 2px 6px rgba(0,0,0,0.8));
```

**Dark input fields** (on felt surface — NOT white):
```css
background:
  linear-gradient(180deg, rgba(255,255,255,0.04) 0%, transparent 100%),
  linear-gradient(180deg, #2a1c0c 0%, #1e1308 100%);
border: 1px solid rgba(201,162,74,0.3);
color: #fbf6e4;
box-shadow: inset 0 1px 4px rgba(0,0,0,0.5);
/* Focus state: */
border-color: rgba(201,162,74,0.65);
box-shadow: inset 0 1px 4px rgba(0,0,0,0.5), 0 0 0 2px rgba(201,162,74,0.12);
```

**Brass action button**:
```css
background: linear-gradient(180deg, #f6d778 0%, #c9a24a 45%, #9a7630 100%);
color: #1a0e03;
box-shadow:
  0 0 0 1px rgba(0,0,0,0.6),
  0 3px 0 rgba(0,0,0,0.5),
  0 5px 15px rgba(0,0,0,0.4),
  inset 0 1px 0 rgba(255,245,200,0.6);
font-family: 'Cinzel', serif;
letter-spacing: 2.5px;
text-transform: uppercase;
```

**Brass horizontal rule** (section dividers):
```css
background: linear-gradient(90deg,
  transparent 0%, #5a3f16 10%, #c9a24a 30%,
  #f6d778 50%, #c9a24a 70%, #5a3f16 90%, transparent 100%
);
height: 1px;
```

**Field labels** (on felt):
```css
font-family: 'Cinzel', serif;
font-size: 9px;
font-weight: 700;
letter-spacing: 2px;
text-transform: uppercase;
color: rgba(201,162,74,0.75);
```

### Key Measurements
- Table ring: 188px diameter
- Card sizes: small 30×42px, mid 48×68px, large 56×80px
- Nameplate border-radius: 14px (pill shape), dark semi-opaque background
- Bid coin: 30px circle, radial-gradient brass, Merriweather 900
- Brass frame padding: 3px
- Felt surface padding: 28px 24px 24px

---

## 7b. Irish Card Room — Component Library

All components below are styled for the felt surface context (dark background, brass accents).
Copy these recipes into any new Irish mockup or implementation.

---

### Alert / Message Boxes

**Error box** (wrong PIN, username taken, etc.):
```css
background: rgba(168,24,36,0.12);
border: 1px solid rgba(168,24,36,0.55);
border-radius: 3px;
padding: 9px 12px;
color: #e8a0a8;          /* desaturated pink-red, readable on dark */
font-size: 12px;
font-style: italic;
```

**Warning box** (e.g. house rules notice, destructive action confirm):
```css
background: rgba(180,120,10,0.12);
border: 1px solid rgba(201,162,74,0.45);
border-radius: 3px;
padding: 9px 12px;
color: rgba(246,215,120,0.85);
font-size: 12px;
```

**Success / info box** (registration complete, save confirmed):
```css
background: rgba(31,122,63,0.2);
border: 1px solid rgba(93,208,132,0.4);
border-radius: 3px;
padding: 9px 12px;
color: #8ddba8;
font-size: 12px;
```

---

### Modal / Dialog Overlay

**Backdrop** (full-screen scrim behind modal):
```css
position: fixed;
inset: 0;
background: rgba(0,0,0,0.75);
backdrop-filter: blur(3px);
z-index: 50;
display: flex;
align-items: center;
justify-content: center;
padding: 20px;
```

**Modal container** (the brass-framed felt panel):
Use the same brass-frame → felt-surface → content pattern as the login card.
For modals, reduce frame padding to 2px and felt padding to 20px 18px.

```css
/* Outer brass frame */
background: conic-gradient(from 135deg,
  #5a3f16 0deg, #c9a24a 60deg, #f6d778 120deg,
  #c9a24a 180deg, #5a3f16 240deg, #c9a24a 300deg,
  #f6d778 330deg, #5a3f16 360deg);
border-radius: 6px;
padding: 2px;
box-shadow: 0 0 0 1px rgba(0,0,0,0.9), 0 20px 60px rgba(0,0,0,0.8);
max-width: 420px;
width: 100%;
max-height: 85vh;
overflow: hidden;

/* Inner felt */
background-color: #13572a;
background-image: radial-gradient(circle, rgba(255,255,255,0.055) 1px, transparent 1px);
background-size: 6px 6px;
border-radius: 5px;
overflow-y: auto;
```

**Modal header** (title bar at top of modal):
```css
padding: 16px 18px 14px;
border-bottom: 1px solid rgba(201,162,74,0.2);
/* Optional: add brass rule pseudo-element same as title-plaque::after */
font-family: 'Cinzel', serif;
font-size: 13px;
font-weight: 700;
letter-spacing: 2px;
color: #f6d778;           /* brass-hi */
text-transform: uppercase;
```

**Modal close button** (top-right ×):
```css
width: 26px; height: 26px;
border-radius: 50%;
background: rgba(0,0,0,0.3);
border: 1px solid rgba(201,162,74,0.3);
color: rgba(201,162,74,0.6);
font-size: 14px;
cursor: pointer;
/* Hover: */
border-color: rgba(201,162,74,0.6);
color: #f6d778;
```

**Modal body**:
```css
padding: 18px;
color: #e8e4d9;
font-family: 'Inter', sans-serif;
font-size: 13px;
line-height: 1.6;
```

**Modal footer** (action button row):
```css
padding: 14px 18px 18px;
border-top: 1px solid rgba(201,162,74,0.15);
display: flex;
gap: 10px;
justify-content: flex-end;
```

---

### Buttons

**Primary (brass)** — already documented above in §7 material recipes.

**Secondary / ghost button** (cancel, dismiss, less important action):
```css
padding: 10px 16px;
font-family: 'Cinzel', serif;
font-size: 11px;
font-weight: 700;
letter-spacing: 1.5px;
text-transform: uppercase;
color: rgba(201,162,74,0.7);
background: transparent;
border: 1px solid rgba(201,162,74,0.35);
border-radius: 4px;
cursor: pointer;
/* Hover: */
color: #f6d778;
border-color: rgba(201,162,74,0.65);
background: rgba(201,162,74,0.06);
```

**Destructive button** (delete, leave game):
```css
color: #e8a0a8;
background: rgba(168,24,36,0.1);
border: 1px solid rgba(168,24,36,0.45);
/* Same font/sizing as secondary */
/* Hover: */
background: rgba(168,24,36,0.2);
border-color: rgba(168,24,36,0.7);
```

**Icon button** (toolbar icons, gear, ?, close):
```css
width: 32px; height: 32px;
border-radius: 50%;
background: radial-gradient(circle at 30% 25%, rgba(255,255,255,0.08) 0%, rgba(0,0,0,0.3) 100%);
border: 1px solid rgba(201,162,74,0.35);
color: rgba(201,162,74,0.7);
display: flex; align-items: center; justify-content: center;
font-size: 14px;
cursor: pointer;
box-shadow: inset 0 1px 0 rgba(255,255,255,0.06), 0 2px 4px rgba(0,0,0,0.4);
/* Hover: */
border-color: rgba(201,162,74,0.65);
color: #f6d778;
box-shadow: inset 0 1px 0 rgba(255,255,255,0.08), 0 0 10px rgba(201,162,74,0.12);
```

---

### Tab / Segment Controls

**Dark wood tab bar** (Returning Player / New Player style):
```css
/* Container */
background: linear-gradient(180deg, #2a1608 0%, #140802 100%);
border: 1px solid #5a3f16;
border-radius: 4px;
overflow: hidden;
box-shadow: inset 0 1px 0 rgba(201,162,74,0.12), 0 2px 4px rgba(0,0,0,0.4);

/* Inactive tab */
font-family: 'Cinzel', serif;
font-size: 11px; font-weight: 700; letter-spacing: 1px;
color: rgba(201,162,74,0.5);
background: transparent;

/* Active tab */
background: linear-gradient(180deg, rgba(201,162,74,0.22) 0%, rgba(201,162,74,0.1) 100%);
color: #f6d778;
box-shadow: inset 0 1px 0 rgba(201,162,74,0.3);
text-shadow: 0 0 8px rgba(246,215,120,0.3);

/* Divider between tabs */
border-left: 1px solid #5a3f16;
```

---

### Toast / Notification

**In-game toast** (house rules, trick result, short-lived message):
```css
position: fixed;  /* or absolute within game container */
top: 60px;
left: 50%;
transform: translateX(-50%);
background: linear-gradient(180deg, #2a1c0c 0%, #1a1008 100%);
border: 1px solid rgba(201,162,74,0.45);
border-radius: 4px;
padding: 10px 18px;
color: #f6d778;
font-family: 'Cinzel', serif;
font-size: 11px;
letter-spacing: 1.5px;
text-align: center;
box-shadow: 0 4px 20px rgba(0,0,0,0.6), 0 0 0 1px rgba(0,0,0,0.8);
z-index: 100;
/* Animate in: */
animation: fadeIn 0.2s ease-out;
```

---

### List Items (Game List, Leaderboard rows)

**Standard list item** (game in lobby, player in leaderboard):
```css
padding: 10px 12px;
background: linear-gradient(180deg, rgba(255,255,255,0.03) 0%, transparent 100%),
            rgba(10,6,2,0.4);
border: 1px solid rgba(201,162,74,0.15);
border-radius: 3px;
margin-bottom: 6px;
/* Hover: */
background: rgba(201,162,74,0.06);
border-color: rgba(201,162,74,0.3);
```

**List item title text**:
```css
font-family: 'Merriweather', serif;
font-weight: 700;
font-size: 13px;
color: #fbf6e4;
```

**List item metadata / secondary text**:
```css
font-family: 'Inter', sans-serif;
font-size: 11px;
color: rgba(201,162,74,0.55);
```

---

### Score / Stat Plaques

**Score plaque** (US / THEM, match score boxes):
```css
background:
  linear-gradient(180deg, rgba(255,255,255,0.06) 0%, transparent 40%),
  linear-gradient(180deg, #2a1608 0%, #140802 100%);
border: 1px solid #5a3f16;
border-radius: 4px;
padding: 3px 10px 4px;
min-width: 52px;
box-shadow: inset 0 1px 0 rgba(201,162,74,0.2), 0 2px 4px rgba(0,0,0,0.5);
text-align: center;

/* Label (US / THEM) */
font-size: 8px; letter-spacing: 1.5px; font-weight: 700;
color: rgba(201,162,74,0.65);

/* Value */
font-family: 'Merriweather', serif;
font-weight: 900; font-size: 16px; line-height: 1;
/* US team color:   #5dd084, text-shadow 0 0 6px rgba(93,208,132,0.4) */
/* THEM team color: #ef7c74, text-shadow 0 0 6px rgba(239,124,116,0.35) */
```

---

### Status Badges

**General badge** (small label pill — dealer, disconnected, active):
```css
font-family: 'Cinzel', serif;
font-size: 8px; font-weight: 700; letter-spacing: 1px;
padding: 2px 6px;
border-radius: 3px;
text-transform: uppercase;
```

**Dealer badge** (D):
```css
background: radial-gradient(circle at 30% 25%, #f4f0dc, #d8cfa8);
border: 1.5px solid #6b5a32;
color: #4a3818;
box-shadow: inset 0 1px 0 rgba(255,255,255,0.6), 0 1px 3px rgba(0,0,0,0.5);
```

**Disconnected badge**:
```css
background: rgba(168,24,36,0.15);
border: 1px solid rgba(168,24,36,0.5);
color: #e8a0a8;
```

**Active / your-turn highlight** (nameplate pulse):
```css
background: linear-gradient(180deg, rgba(240,200,90,0.28), rgba(180,140,40,0.18));
border-color: #f6d778;
color: #fbe69a;
animation: activeBreathe 1.6s ease-in-out infinite;

@keyframes activeBreathe {
  0%, 100% { box-shadow: 0 0 0 0   rgba(246,215,120,0.55), 0 3px 8px rgba(0,0,0,0.5); }
  50%       { box-shadow: 0 0 0 5px rgba(246,215,120,0.02), 0 3px 8px rgba(0,0,0,0.5); }
}
```

---

### Scrollable Content Areas

When modal/panel content overflows, the scroll container:
```css
overflow-y: auto;
/* Custom scrollbar on webkit */
scrollbar-width: thin;
scrollbar-color: rgba(201,162,74,0.3) transparent;
/* ::-webkit-scrollbar { width: 4px; } */
/* ::-webkit-scrollbar-thumb { background: rgba(201,162,74,0.3); border-radius: 2px; } */
/* ::-webkit-scrollbar-track { background: transparent; } */
```

---

## 7c. Mobile Constraints — Phone-First Rules

The app runs on a phone screen. Every mockup and implementation must be validated at **390×844px** (iPhone 14 size — the design baseline). All rules below are non-negotiable.

---

### Viewport & Layout

**The phone is the canvas.** There is no desktop layout — the app is a single-column vertical stack that fills the screen.

```
Max usable width:   390px  (no horizontal scroll ever)
Max usable height:  844px  (but subtract ~50px for browser chrome on Android)
Safe usable height: ~790px before assuming scroll is needed
```

**Root container must always be:**
```css
min-height: 100dvh;   /* dvh = dynamic viewport height, accounts for mobile browser bars */
/* fallback: */ min-height: 100vh;
overflow-x: hidden;
```

**Scrolling strategy by screen:**
| Screen | Expected behavior |
|--------|-----------------|
| Login (returning) | No scroll — fits in one screen |
| Login (register) | Scrollable — avatar picker makes it tall |
| Lobby | Scrollable — game list grows |
| WaitingRoom | No scroll |
| Game table | No scroll — fixed layout, fills screen |
| Modals | Scroll inside modal — body scrolls, header/footer fixed |

---

### Touch Targets

Every tappable element must meet minimum touch size. This is the #1 source of usability failure on phone.

```
Minimum tap target:  44×44px  (Apple HIG / Google Material standard)
Comfortable target:  48×48px
```

**Checklist:**
- Buttons: `min-height: 44px`, full width on phone (`width: 100%`)
- Icon buttons: `width: 44px; height: 44px` minimum (even if visually smaller, pad with transparent area)
- Tab buttons: `padding: 12px` minimum (not 8px)
- List items: `min-height: 44px; padding: 12px`
- Avatar tiles in picker: `min-height: 44px` — use a 4-column grid, not 5-column (5 is too small at 390px)
- Close (×) button on modals: `width: 44px; height: 44px` — place in top-right corner, not tiny inline

---

### Font Sizes

```
Absolute minimum body text:    12px  (anything smaller is unreadable on phone)
Preferred minimum body text:   13px
Labels / captions:             11px minimum
Tiny badges / pip labels:      9px minimum — ONLY for non-critical decoration
Input placeholder text:        14px (iOS zooms in if input font-size < 16px — avoid zoom)
Input value text:              16px minimum to prevent iOS auto-zoom
PIN input:                     24–28px (large, centered, needs to be clearly legible)
```

**Critical:** `font-size: 16px` on `<input>` elements prevents iOS Safari from zooming the viewport when the field is tapped. If the text looks too big, reduce it visually with `transform: scale()` or adjust padding instead.

In React (inline styles), apply to all text inputs:
```javascript
style={{ fontSize: '16px' }}
```

---

### Keyboard Behavior

When a text input or PIN field is focused on mobile, the OS keyboard rises and shrinks the viewport by ~300px. This means:

- **Login form (returning player):** Username + PIN + button = ~180px content. Fits above keyboard. ✓
- **Login form (register):** Full form is ~500px. Bottom half disappears behind keyboard. The button must remain accessible — consider `position: sticky; bottom: 0` on the button, or ensure the form scrolls so the active field is always visible.
- **Modals with inputs:** Same issue. Modal should scroll internally so the focused field is above the keyboard.
- **Never use `position: fixed` for inputs** — they get trapped behind the keyboard on some Android browsers.

**Safe pattern for forms that scroll:**
```css
/* Outer scroll container */
overflow-y: auto;
-webkit-overflow-scrolling: touch;
padding-bottom: 20px;  /* extra space so button clears keyboard */
```

---

### Modal Sizing

Modals must never overflow the screen height.

```css
/* Modal container max dimensions */
max-width: 420px;
width: calc(100% - 32px);   /* 16px margin each side */
max-height: 85dvh;           /* leaves room for backdrop and safe area */
/* fallback: */ max-height: 85vh;
overflow: hidden;             /* clip the frame */

/* Modal body (scrollable content inside) */
overflow-y: auto;
-webkit-overflow-scrolling: touch;
/* Max height = modal max-height minus header (~52px) minus footer (~60px) */
max-height: calc(85dvh - 112px);
```

**Never make a modal taller than `90vh`.** On a 667px iPhone SE, 90vh = 600px — leaves almost no backdrop visible and feels like a full page, not a dialog.

---

### Horizontal Spacing

```
Screen edge padding:    16px minimum each side (no content touching the edge)
Panel/card padding:     20–24px horizontal
Input padding:          12px horizontal
Button padding:         16px horizontal
```

At 390px wide:
- A panel with 16px margin each side = 358px wide
- Inputs at 100% width fill the panel
- A 5-column avatar grid at 358px = ~65px per tile. Too small for touch (below 44px). Use 4 columns = ~82px per tile ✓

---

### Safe Area Insets (Notch / Home Bar)

On modern phones (iOS with Dynamic Island, Android with gesture nav bar), content can be obscured at top and bottom.

```css
/* Apply to root container */
padding-top: env(safe-area-inset-top);
padding-bottom: env(safe-area-inset-bottom);

/* Or on fixed/sticky elements: */
bottom: max(16px, env(safe-area-inset-bottom));
```

In the current app (single HTML file, browser-based), `env(safe-area-inset-*)` works in mobile Safari and Chrome. At minimum, ensure the primary action button is never behind the home indicator bar.

---

### Practical Checklist for Every Screen Mockup

Before handing off a mockup for implementation, verify at 390×844px:

- [ ] No horizontal overflow (set browser dev tools to 390px width)
- [ ] All tap targets ≥ 44px height
- [ ] All input `font-size` ≥ 16px (to prevent iOS zoom)
- [ ] Primary action button visible without scrolling on login/short screens
- [ ] Scrollable screens scroll smoothly (add `overflow-y: auto` to container)
- [ ] Modals fit within `85vh` with internal scroll for long content
- [ ] No text below 12px (except purely decorative badges)
- [ ] Avatar grids use 4 columns max, not 5
- [ ] Version badge / floating elements clear the safe area

---

## 8. Cyberpunk Design Tokens

From `cyberpunk theme/design_handoff_45s_cyberpunk/README.md`:

### Colors
```
--bg:         #020509    deepest background
--bg-mid:     #060d18    surface layer
--cyan:       #00e5ff    primary neon, black suits
--mag:        #ff00cc    secondary neon, team-them
--amber:      #ff8c00    active/playable/dealer
--green:      #00ff88    team-us
--suit-red:   #ff1a75    red card suits
--suit-blk:   #00e5ff    black card suits
--team-us:    #00ff88
--team-them:  #ff00cc
--txt:        #c0ddf0    primary text
--txt-dim:    #3a5f78    muted text
```

### Typography
```
Orbitron        — brand, scores, bid badge, dealer (700, 900)
Share Tech Mono — nameplates, labels, card corners (400)
Inter           — body, suit glyphs (400, 500, 600)
```

---

## 10. Design Rules (Non-Negotiable)

1. **Compass layout for anything NSEW**: Any UI element that represents North/South/East/West seats — seat pickers, waiting room, player position indicators — MUST use a compass layout. North at top center, South at bottom center, West at left, East at right. Never use a 2×2 grid or list. Use CSS Grid with named areas:
```css
grid-template-areas:
  ". north ."
  "west  .  east"
  ". south .";
grid-template-columns: 1fr auto 1fr;
```

---

## 9. Known Gotchas

1. **Firebase array corruption**: Firebase can corrupt JS arrays into objects with numeric keys. Always use `FirebaseAPI.ensureArray()` when reading `hands` from Firebase.

2. **backdrop-filter on nameplates**: Used in Cyberpunk theme. Works in browser. If porting to React Native, replace with semi-opaque solid backgrounds.

3. **Single-file React with Babel**: No build step. Syntax errors silently break the whole app. After any edit, load in browser and check console before committing.

4. **Version number is mandatory**: `const VERSION = 'X.Y.Z'` near top of `<script>` block. Must increment on every change. Also update `versionHistory` array in `WhatsNewModal`.

5. **Inline styles vs CSS classes**: Most game-table components use `cp-card` CSS class. Most lobby/auth screens use 100% inline styles. Theme CSS works easily for table; for lobby you need `getThemeTokens()` or inline conditionals.

6. **Card `.face-up` class**: Applied when a card is revealed face-up during the kitty/draw phase. Each theme must style this — it's easy to miss. Without it, the card looks identical to a face-down card.

7. **Fan layout only for Cyberpunk**: `cardLayout: 'fan'` in THEMES config triggers FAN_CONFIG-based transforms. Irish uses flat layout. If adding a third theme with fan, add to the conditional check in hand rendering.

8. **Theme persistence**: Stored at `users/${uid}/settings/theme` in Firebase. Loaded on login. Falls back to `'irish'` if not set.

9. **Kitty phase = 8 cards**: After winning the bid and taking the kitty, player temporarily holds 8 cards. Both flat and fan layouts must handle this gracefully. For large counts (>6), switch `Card` to `mid` size: `mid={myHand.length > 6}`.

10. **Deploy = copy**: `cp index-themes.html index.html` before every git push. Both files must be in the commit.
