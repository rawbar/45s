# 45s Card Game - COMPLETE UI DESIGN SPECIFICATION v3.5.9

**Purpose:** This is the authoritative reference for ALL UI design decisions. Every future build MUST conform to this specification unless explicitly documented changes are approved.

**Source:** Version 3.5.9 (final single-player version before multiplayer)

---

## TABLE OF CONTENTS

1. [Global Styles & Layout](#1-global-styles--layout)
2. [Header Bar](#2-header-bar)
3. [Message Bar](#3-message-bar)
4. [Player Positions & Layout](#4-player-positions--layout)
5. [Center Table (Circle)](#5-center-table-circle)
6. [Card Component](#6-card-component)
7. [UI Components](#7-ui-components)
8. [Button Area](#8-button-area)
9. [Last Trick Display](#9-last-trick-display)
10. [Score Table](#10-score-table)
11. [Show Hands Modal](#11-show-hands-modal)
12. [Colors & Typography](#12-colors--typography)
13. [Spacing & Sizing Standards](#13-spacing--sizing-standards)
14. [Animation Behaviors](#14-animation-behaviors)

---

## 1. GLOBAL STYLES & LAYOUT

### HTML/Body
```css
* { 
  box-sizing: border-box; 
  margin: 0; 
  padding: 0; 
}

body { 
  font-family: 'Palatino Linotype', Palatino, Georgia, serif; 
  overflow: hidden; 
  position: fixed; 
  width: 100%; 
  height: 100%; 
}

html, body, #root { 
  height: 100%; 
}
```

### Main Container
```javascript
{
  height: '100%',
  display: 'flex',
  flexDirection: 'column',
  background: 'linear-gradient(135deg, #1a472a 0%, #0d2818 50%, #0a1f12 100%)',
  padding: '4px',
  fontFamily: 'Arial, sans-serif',
  color: '#e8e4d9'
}
```

**Critical:** 
- Background is a 3-stop gradient (green to dark green to very dark green)
- Padding is 4px on all sides
- Font is Arial, NOT Palatino (body uses Palatino but game uses Arial)

---

## 2. HEADER BAR

### Container
```javascript
{
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  padding: '4px 8px',
  background: 'rgba(0,0,0,0.3)',
  borderRadius: '6px',
  marginBottom: '4px'
}
```

### Layout (3 sections)

**Left: Game Title + Version**
```javascript
<div style={{ fontSize: '14px', fontWeight: 'bold', color: '#d4af37' }}>
  45s <span style={{ fontSize: '8px', color: '#666' }}>v{VERSION}</span>
</div>
```
- Title: "45s" in gold (#d4af37), 14px, bold
- Version: "v3.5.9" in gray (#666), 8px

**Middle: Help Button**
```javascript
<div style={{
  width: '20px',
  height: '20px',
  borderRadius: '50%',
  border: '1px solid #d4af37',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  color: '#d4af37',
  fontSize: '12px',
  cursor: 'pointer',
  fontWeight: 'bold'
}}>?</div>
```
- Circle button, 20px diameter
- Gold border and text (#d4af37)
- Contains "?" in 12px bold

**Right: Score Display**
```javascript
<div style={{ fontSize: '12px' }}>
  <span style={{ color: '#4caf50' }}>Us:{scores[0]}</span> | 
  <span style={{ color: '#f44336' }}>Them:{scores[1]}</span>
</div>
```
- "Us" in green (#4caf50)
- "Them" in red (#f44336)
- 12px font
- Separated by " | "

**Critical:**
- NO other elements in header
- Exact 3-item layout: Title | Help | Scores
- Fixed height maintained by container

---

## 3. MESSAGE BAR

### Container
```javascript
{
  height: '24px',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: 'rgba(0,0,0,0.4)',
  borderRadius: '4px',
  fontSize: '12px',
  color: '#ffd700',
  marginBottom: '4px'
}
```

**Critical:**
- FIXED height of 24px (prevents layout shift)
- Always present, even when empty
- Gold text (#ffd700)
- 12px font
- Dark background (rgba(0,0,0,0.4))

---

## 4. PLAYER POSITIONS & LAYOUT

### Player Mapping (NEVER CHANGES)
```
Position 0 = P1 = South  = You (bottom)
Position 1 = P2 = West   = Left side
Position 2 = P3 = North  = Partner (top)
Position 3 = P4 = East   = Right side
```

### Overall Game Area Container
```javascript
{
  flex: 1,
  display: 'flex',
  flexDirection: 'column',
  minHeight: 0
}
```

---

### NORTH PLAYER (Position 2 - Partner)

**Container:**
```javascript
{
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  gap: '2px',
  padding: '2px 0'
}
```

**Top Row (Name + Dealer + Cards Drawn):**
```javascript
<div style={{ display: 'flex', alignItems: 'center', gap: '4px', height: '16px' }}>
  <span style={{ fontSize: '11px', color: '#aaa' }}>{PLAYER_NAMES[2]}</span>
  <div style={{ width: '40px', display: 'flex', justifyContent: 'center' }}>
    {dealer === 2 && <DealerBadge />}
  </div>
  <CardsDrawnIndicator count={drawn[2]} />
</div>
```
- Name: 11px, #aaa
- Dealer badge: 40px container, centered
- Cards drawn: +X indicator

**Cards Row:**
```javascript
<div style={{ display: 'flex', gap: '1px' }}>
  {hands[2].map((_, i) => <Card key={i} card={{}} faceDown small />)}
</div>
```
- Cards: 1px gap between
- All face down
- Small size (30x42px)

**Bottom Row (Bid + Tricks Won):**
```javascript
<div style={{ display: 'flex', alignItems: 'center', gap: '4px', height: '20px' }}>
  <div style={{ minWidth: '40px', display: 'flex', justifyContent: 'center' }}>
    {bidInd(2)}
  </div>
  <div style={{ minWidth: '60px', display: 'flex', justifyContent: 'center' }}>
    <TricksWonDisplay count={playerTricks[2]} hasHighTrump={highTrumpInfo.player === 2} />
  </div>
</div>
```
- Bid: 40px min width
- Tricks: 60px min width
- Height: 20px

---

### MIDDLE ROW CONTAINER

```javascript
{
  flex: 1,
  display: 'flex',
  alignItems: 'center',
  minHeight: 0
}
```

Contains: West player + Center table + East player

---

### WEST PLAYER (Position 1 - P2)

**Container:**
```javascript
{
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  gap: '2px',
  width: '50px'
}
```

**Elements (top to bottom):**
1. Name: `fontSize: '10px', color: '#aaa'`
2. Dealer badge area: `height: '14px'`
3. Cards (vertical): `display: 'flex', flexDirection: 'column', gap: '1px'`
4. Cards drawn: `height: '14px'`
5. Bid: `height: '18px', minWidth: '40px'`
6. Tricks won: `height: '20px'`

**Critical:**
- Fixed width: 50px
- Vertical card layout
- All elements centered

---

### CENTER TABLE (CIRCLE)

**Outer Container:**
```javascript
{
  flex: 1,
  display: 'flex',
  justifyContent: 'center',
  alignItems: 'center'
}
```

**Circle:**
```javascript
{
  width: '150px',
  height: '150px',
  display: 'flex',
  justifyContent: 'center',
  alignItems: 'center',
  background: 'rgba(0,0,0,0.3)',
  borderRadius: '50%',
  border: '2px solid rgba(212,175,55,0.3)',
  position: 'relative'
}
```

**Trump Suit Display (ALWAYS VISIBLE behind cards):**
```javascript
{
  position: 'absolute',
  fontSize: '64px',
  color: (trumpSuit === '♥' || trumpSuit === '♦') ? '#f44336' : '#fff',
  opacity: 0.3,
  zIndex: 0
}
```
- Red (#f44336) for hearts/diamonds
- White (#fff) for spades/clubs
- 64px font size
- 0.3 opacity
- Behind trick cards (zIndex: 0)

**Trick Card Positions:**
```javascript
const positions = [
  { bottom: '4px', left: '50%', transform: 'translateX(-50%)' },  // Position 0 (South)
  { left: '4px', top: '50%', transform: 'translateY(-50%)' },     // Position 1 (West)
  { top: '4px', left: '50%', transform: 'translateX(-50%)' },     // Position 2 (North)
  { right: '4px', top: '50%', transform: 'translateY(-50%)' }     // Position 3 (East)
];
```

**CRITICAL:**
- Cards are 4px from edge (NOT 80px or 10px)
- Position index matches player index directly
- Player 0's card at bottom, Player 1 at left, etc.

**Round Score Display (during playing/trick-end):**
```javascript
{
  position: 'absolute',
  bottom: '-16px',
  fontSize: '10px',
  color: '#aaa'
}
// Shows: {roundPts[0]}-{roundPts[1]}
```
- Below circle by 16px
- 10px font, gray (#aaa)

---

### EAST PLAYER (Position 3 - P4)

**Container:**
```javascript
{
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  gap: '2px',
  width: '50px'
}
```

**Same structure as West player:**
1. Name: 10px, #aaa
2. Dealer badge: 14px height
3. Cards (vertical): flex column, 1px gap
4. Cards drawn: 14px height
5. Bid: 18px height, 40px min width
6. Tricks won: 20px height

---

### SOUTH PLAYER (Position 0 - You)

**Container:**
```javascript
{
  padding: '4px 0'
}
```

**Top Row (Tricks + Name + Dealer + Bid + Cards Drawn):**
```javascript
<div style={{
  display: 'flex',
  justifyContent: 'center',
  alignItems: 'center',
  gap: '4px',
  marginBottom: '4px',
  height: '20px'
}}>
  <div style={{ minWidth: '60px', display: 'flex', justifyContent: 'center' }}>
    <TricksWonDisplay count={playerTricks[0]} hasHighTrump={highTrumpInfo.player === 0} />
  </div>
  <span style={{ fontSize: '11px', color: '#aaa' }}>{PLAYER_NAMES[0]}</span>
  <div style={{ width: '40px', display: 'flex', justifyContent: 'center' }}>
    {dealer === 0 && <DealerBadge />}
  </div>
  <div style={{ minWidth: '50px', display: 'flex', justifyContent: 'center' }}>
    {bidInd(0)}
  </div>
  <CardsDrawnIndicator count={drawn[0]} />
</div>
```

**Hand Display:**
```javascript
<div style={{
  display: 'flex',
  justifyContent: 'center',
  gap: '2px',
  minHeight: '68px'
}}>
  {hands[0].map((c, i) => (
    <Card 
      key={c.id}
      card={c}
      onClick={() => /* click handler */}
      selected={selected.includes(i)}
      playable={playable.includes(i)}
      disabled={/* logic */}
      wasDrawn={drawnCards.has(c.id)}
    />
  ))}
</div>
```
- 2px gap between cards (NOT 1px like opponents)
- minHeight: 68px (matches regular card height)
- Cards are NOT small (48x68px)

---

## 5. CENTER TABLE (CIRCLE)

See section 4 for complete circle specifications.

**Summary:**
- Diameter: 150px x 150px
- Border: 2px solid rgba(212,175,55,0.3) - semi-transparent gold
- Background: rgba(0,0,0,0.3) - semi-transparent black
- Trump: 64px, 0.3 opacity, behind cards (z-index: 0)
- Trick cards: 4px from edge, z-index: 1

---

## 6. CARD COMPONENT

### Card Sizes
```javascript
// Small cards (opponents + modals + trick cards)
small: { width: '30px', height: '42px' }

// Regular cards (your hand)
regular: { width: '48px', height: '68px' }
```

### Base Style
```javascript
{
  width: small ? '30px' : '48px',
  height: small ? '42px' : '68px',
  borderRadius: '4px',
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  cursor: disabled ? 'default' : 'pointer',
  transition: 'all 0.1s',
  fontFamily: 'Arial, sans-serif',
  userSelect: 'none',
  flexShrink: 0,
  position: 'relative'
}
```

### Face Down Card
```javascript
{
  background: 'linear-gradient(135deg, #1e3a5f 0%, #0d1b2a 100%)',
  border: '1px solid #2d5a87'
}
```
- Blue gradient background
- Blue border
- No content shown

### Face Up Card - States

**Normal (not selected, not playable):**
```javascript
{
  background: '#fff',
  border: '1px solid #ccc',
  boxShadow: '0 1px 3px rgba(0,0,0,0.15)',
  transform: 'none',
  opacity: disabled && !playable ? 0.6 : 1
}
```

**Selected (during discard phase):**
```javascript
{
  background: '#fffde7',  // Light yellow
  border: '2px solid #ffc107',  // Amber border
  boxShadow: '0 2px 6px rgba(0,0,0,0.3)',
  transform: 'translateY(-2px)',  // Lifts up slightly
  opacity: 1
}
```

**Playable (valid move):**
```javascript
{
  background: '#fff',
  border: '2px solid #2196f3',  // Blue border
  boxShadow: '0 2px 6px rgba(0,0,0,0.3)',
  transform: 'translateY(-2px)',  // Lifts up slightly
  opacity: 1
}
```

**Disabled (not your turn or invalid):**
```javascript
{
  opacity: 0.6,
  cursor: 'default'
}
```

### Card Content

**Rank:**
```javascript
<div style={{
  color: (card.suit === '♥' || card.suit === '♦') ? '#c62828' : '#212121',
  fontSize: small ? '12px' : '15px',
  fontWeight: 'bold',
  lineHeight: 1
}}>
  {card.rank}
</div>
```
- Red (#c62828) for hearts/diamonds
- Black (#212121) for spades/clubs
- 12px (small) or 15px (regular)
- Bold weight

**Suit:**
```javascript
<div style={{
  color: (card.suit === '♥' || card.suit === '♦') ? '#c62828' : '#212121',
  fontSize: small ? '16px' : '22px',
  lineHeight: 1
}}>
  {card.suit}
</div>
```
- Same color logic as rank
- 16px (small) or 22px (regular)

**Drawn Indicator (blue dot in bottom-right):**
```javascript
<div style={{
  position: 'absolute',
  bottom: '2px',
  right: '2px',
  width: '5px',
  height: '5px',
  borderRadius: '50%',
  background: '#1565c0'
}} />
```
- Only shown if wasDrawn prop is true
- 5px diameter blue circle
- Bottom-right corner, 2px offset

---

## 7. UI COMPONENTS

### DealerBadge
```javascript
<span style={{
  padding: '1px 3px',
  background: '#d4af37',
  color: '#000',
  borderRadius: '2px',
  fontSize: '8px',
  fontWeight: 'bold'
}}>DEALER</span>
```
- Gold background
- Black text
- 8px font, bold
- Text: "DEALER"

### CardsDrawnIndicator
```javascript
<span style={{
  fontSize: '9px',
  color: '#ffd700'
}}>+{displayCount}</span>
```
- Gold text (#ffd700)
- 9px font
- Format: "+0", "+5", etc.

### TricksWonDisplay

**Container (only shown if count > 0):**
```javascript
<div style={{ display: 'flex', gap: '1px' }}>
  {Array.from({ length: count }, (_, i) => (
    <TrickMarker key={i} isHighTrump={hasHighTrump && i === 0} />
  ))}
</div>
```
- 1px gap between markers
- First marker is special if hasHighTrump

**TrickMarker (regular):**
```javascript
<div style={{
  width: '14px',
  height: '18px',
  borderRadius: '2px',
  background: 'linear-gradient(135deg, #1e3a5f 0%, #0d1b2a 100%)',
  border: '1px solid #2d5a87'
}} />
```
- Blue gradient (matches face-down cards)
- 14x18px rectangle

**TrickMarker (high trump):**
```javascript
<div style={{
  width: '14px',
  height: '18px',
  borderRadius: '2px',
  background: 'linear-gradient(135deg, #8b0000 0%, #5c0000 100%)',
  border: '1px solid #ff6666'
}} />
```
- Red gradient (dark red to darker red)
- Red border (#ff6666)

### Bid Indicators (bidInd function)

**Pass:**
```javascript
<span style={{
  padding: '2px 4px',
  background: '#555',
  color: '#aaa',
  borderRadius: '3px',
  fontSize: '10px'
}}>Pass</span>
```

**Bid (non-winner):**
```javascript
<span style={{
  padding: '2px 4px',
  background: '#555',
  color: '#aaa',
  borderRadius: '3px',
  fontSize: '10px'
}}>{bid}</span>
```
- Gray background/text
- Shows bid number (15, 20, 25, 30)

**Bid Winner:**
```javascript
<span style={{
  padding: '2px 4px',
  background: '#2196f3',
  color: '#fff',
  borderRadius: '3px',
  fontSize: '10px'
}}>{bid}{trumpSuit}</span>
```
- Blue background (#2196f3)
- White text
- Shows bid + trump suit symbol

**Bagged Bid Winner:**
```javascript
<span style={{
  padding: '2px 4px',
  background: '#c62828',
  color: '#fff',
  borderRadius: '3px',
  fontSize: '10px'
}}>{bid}{trumpSuit} BAGGED</span>
```
- Red background (#c62828)
- White text
- Shows "BAGGED" after trump

---

## 8. BUTTON AREA

### Container
```javascript
<div style={{
  display: 'flex',
  justifyContent: 'center',
  gap: '4px',
  flexWrap: 'wrap',
  padding: '4px 0',
  minHeight: '36px'
}}>
```
- Fixed min-height: 36px (prevents layout shift)
- 4px gap between buttons
- Wraps if needed
- Centered

### Button Types

**Bid Buttons (15, 20, 25, 30):**
```javascript
// Enabled
{
  padding: '6px 12px',
  fontSize: '12px',
  background: '#2196f3',
  color: '#fff',
  border: 'none',
  borderRadius: '4px',
  opacity: 1
}

// Disabled (bid <= highBid)
{
  padding: '6px 12px',
  fontSize: '12px',
  background: '#555',
  color: '#fff',
  border: 'none',
  borderRadius: '4px',
  opacity: 0.5
}
```

**Pass Button:**
```javascript
{
  padding: '6px 12px',
  fontSize: '12px',
  background: '#c9a227',  // Yellow-gold
  color: '#000',
  border: 'none',
  borderRadius: '4px'
}
```
- CRITICAL: Yellow background, black text

**Trump Select Buttons (♠ ♥ ♦ ♣):**
```javascript
{
  padding: '6px 14px',
  fontSize: '18px',
  background: 'rgba(0,0,0,0.5)',
  color: (s === '♥' || s === '♦') ? '#f44336' : '#fff',
  border: '1px solid #d4af37',
  borderRadius: '4px'
}
```
- 18px suit symbols
- Red for hearts/diamonds
- White for spades/clubs
- Gold border

**Discard Button:**
```javascript
{
  padding: '6px 16px',
  fontSize: '12px',
  background: '#4caf50',  // Green
  color: '#fff',
  border: 'none',
  borderRadius: '4px'
}
// Text: "Discard (X)" where X is selected count
```

**Show Hands Button:**
```javascript
{
  padding: '6px 16px',
  fontSize: '12px',
  background: '#666',
  color: '#fff',
  border: 'none',
  borderRadius: '4px'
}
```

**Next Button (round-end):**
```javascript
{
  padding: '6px 16px',
  fontSize: '12px',
  background: '#d4af37',  // Gold
  color: '#000',
  border: 'none',
  borderRadius: '4px'
}
```

**New Game Button:**
```javascript
{
  padding: '6px 16px',
  fontSize: '12px',
  background: '#d4af37',  // Gold
  color: '#000',
  border: 'none',
  borderRadius: '4px'
}
```

**Start Button (initial dealing):**
```javascript
{
  padding: '10px 24px',
  fontSize: '14px',
  background: '#d4af37',  // Gold
  color: '#000',
  border: 'none',
  borderRadius: '6px',
  fontWeight: 'bold'
}
```
- Larger than other buttons
- Bold text

---

## 9. LAST TRICK DISPLAY

### Container
```javascript
<div style={{
  height: '44px',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center'
}}>
```
- FIXED height: 44px (prevents layout shift)
- Always present, even when empty

### Content (when lastTrick exists)
```javascript
<div style={{
  display: 'flex',
  alignItems: 'center',
  gap: '2px',
  padding: '2px',
  background: 'rgba(0,0,0,0.2)',
  borderRadius: '4px'
}}>
  <span style={{ fontSize: '9px', color: '#aaa' }}>Last:</span>
  {lastTrick.cards.map((tc, i) => (
    <Card key={i} card={tc.card} small disabled />
  ))}
</div>
```
- Shows "Last:" label (9px, gray)
- Shows 4 small cards
- 2px gap between elements
- Dark background

---

## 10. SCORE TABLE

### Component Structure
```javascript
<div style={{
  background: 'rgba(0,0,0,0.4)',
  borderRadius: '4px',
  padding: '4px',
  fontSize: '10px'
}}>
```

### Collapse Toggle (if > 2 rounds)
```javascript
<div style={{
  textAlign: 'center',
  color: '#aaa',
  cursor: 'pointer',
  fontSize: '9px'
}}>
  {expanded ? '▼ less' : `▲ +${roundHistory.length - maxVis}`}
</div>
```

### Table
```javascript
<table style={{
  width: '100%',
  borderCollapse: 'collapse',
  textAlign: 'center'
}}>
  <thead>
    <tr>
      <th style={{ padding: '1px 2px', borderBottom: '1px solid rgba(255,255,255,0.2)' }}>R</th>
      <th colSpan="2" style={{ padding: '1px 2px', borderBottom: '1px solid rgba(255,255,255,0.2)', color: '#4caf50' }}>US</th>
      <th colSpan="2" style={{ padding: '1px 2px', borderBottom: '1px solid rgba(255,255,255,0.2)', color: '#f44336' }}>THEM</th>
    </tr>
  </thead>
  <tbody>
    {/* Each row */}
    <tr>
      <td style={{ padding: '1px 2px' }}>{roundNumber}</td>
      <td style={{ padding: '1px 2px', color: '#4caf50' }}>
        {score < 0 ? `(${Math.abs(score)})` : score}
      </td>
      <td style={{ padding: '1px 2px', color: '#4caf50', fontWeight: 'bold' }}>
        {totalScore}
      </td>
      <td style={{ padding: '1px 2px', color: '#f44336' }}>
        {score < 0 ? `(${Math.abs(score)})` : score}
      </td>
      <td style={{ padding: '1px 2px', color: '#f44336', fontWeight: 'bold' }}>
        {totalScore}
      </td>
    </tr>
  </tbody>
</table>
```

**Key Details:**
- Headers: R, US (2 cols), THEM (2 cols)
- US columns: green text (#4caf50)
- THEM columns: red text (#f44336)
- Round scores: parentheses for negative
- Total scores: bold
- Default shows last 2 rounds
- Click to expand/collapse

---

## 11. SHOW HANDS MODAL

### Modal Overlay
```javascript
<div style={{
  position: 'fixed',
  top: 0,
  left: 0,
  right: 0,
  bottom: 0,
  background: 'rgba(0,0,0,0.85)',
  zIndex: 100,
  display: 'flex',
  justifyContent: 'center',
  alignItems: 'center',
  padding: '8px'
}}>
```

### Modal Content
```javascript
<div style={{
  background: 'linear-gradient(135deg, #1a472a 0%, #0d2818 100%)',
  border: '2px solid #d4af37',
  borderRadius: '8px',
  width: '100%',
  maxWidth: '400px',
  padding: '12px',
  display: 'flex',
  flexDirection: 'column',
  gap: '12px'
}}>
```

### Header
```javascript
<div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
  <span style={{ fontSize: '14px', fontWeight: 'bold', color: '#d4af37' }}>
    Hands After Draw <span style={{ fontSize: '10px', color: '#888' }}>v{VERSION}</span>
    <div style={{ fontSize: '9px', color: '#888', fontWeight: 'normal' }}>
      [P1:5 P2:5 P3:5 P4:5]
    </div>
  </span>
  <div style={{
    width: '24px',
    height: '24px',
    border: '1px solid #aaa',
    borderRadius: '4px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: '#aaa',
    fontSize: '16px',
    cursor: 'pointer'
  }}>✕</div>
</div>
```

### Trump Display
```javascript
<div style={{ textAlign: 'center', fontSize: '12px', color: '#aaa' }}>
  Trump: <span style={{
    fontSize: '18px',
    color: (trumpSuit === '♥' || trumpSuit === '♦') ? '#f44336' : '#fff'
  }}>{trumpSuit}</span>
</div>
```

### Help Text
```javascript
<div style={{ textAlign: 'center', fontSize: '9px', color: '#888' }}>
  Cards in play order • Gold border = led trick • Blue dot = drawn card
</div>
```

### Player Layout (CRITICAL ORDER)

**Top: Partner (Position 2 - North)**
```javascript
{renderHand(2, 'Partner')}
```

**Middle Row: P2 and P4**
```javascript
<div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
  {renderHand(1, 'P2')}  // Left - West
  {renderHand(3, 'P4')}  // Right - East
</div>
```

**Bottom: You (Position 0 - South)**
```javascript
{renderHand(0, 'You')}
```

**CRITICAL:**
- Player 2 (North/Partner) at TOP
- Player 1 (West/P2) at LEFT
- Player 3 (East/P4) at RIGHT
- Player 0 (South/You) at BOTTOM

### Individual Hand Display

**Container:**
```javascript
<div style={{
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  gap: '4px'
}}>
```

**Name Row:**
```javascript
<div style={{
  display: 'flex',
  alignItems: 'center',
  gap: '4px',
  fontSize: '11px',
  color: '#aaa'
}}>
  <span>{label}</span>
  {isDealer && <DealerBadge />}
  <span style={{ color: '#ffd700' }}>+{drawnCount}</span>
</div>
```

**Bid Display:**
```javascript
// Non-winner:
<span style={{
  padding: '2px 4px',
  background: '#555',
  borderRadius: '3px',
  fontSize: '10px',
  color: '#aaa'
}}>
  {bid === 0 ? 'Pass' : bid}
</span>

// Winner (not bagged):
<span style={{
  padding: '2px 4px',
  background: '#2196f3',
  borderRadius: '3px',
  fontSize: '10px',
  color: '#fff'
}}>
  {bid}{trumpSuit}
</span>

// Winner (bagged):
<span style={{
  padding: '2px 4px',
  background: '#c62828',
  borderRadius: '3px',
  fontSize: '10px',
  color: '#fff'
}}>
  {bid}{trumpSuit} BAGGED
</span>
```

**Cards (in play order):**
```javascript
<div style={{
  display: 'flex',
  gap: '2px',
  flexWrap: 'wrap',
  justifyContent: 'center'
}}>
  {sortedHand.map((c, i) => {
    const ledTrick = /* card led its trick */;
    return (
      <div key={i} style={{ position: 'relative' }}>
        <div style={{
          border: ledTrick ? '2px solid #d4af37' : 'none',
          borderRadius: '4px'
        }}>
          <Card card={c} small disabled wasDrawn={wasDrawn} />
        </div>
        {trickNum && (
          <div style={{
            position: 'absolute',
            top: '-6px',
            right: '-6px',
            width: '14px',
            height: '14px',
            borderRadius: '50%',
            background: ledTrick ? '#d4af37' : '#666',
            color: ledTrick ? '#000' : '#fff',
            fontSize: '9px',
            fontWeight: 'bold',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            {trickNum}
          </div>
        )}
      </div>
    );
  })}
</div>
```

**Card Features:**
- Cards sorted by play order
- Gold border if card led trick
- Trick number badge (top-right)
- Blue dot if drawn card

---

## 12. COLORS & TYPOGRAPHY

### Color Palette

**Primary Colors:**
```
Gold:              #d4af37  (dealer badge, borders, headers)
Green (Us):        #4caf50  (our team score)
Red (Them):        #f44336  (their team score)
Blue (Action):     #2196f3  (playable cards, bid buttons, bid winner)
Yellow (Pass):     #c9a227  (pass button background)
```

**Card Colors:**
```
Red suits:         #c62828  (hearts, diamonds)
Black suits:       #212121  (spades, clubs)
Card background:   #fff
Selected card:     #fffde7  (light yellow)
```

**UI Colors:**
```
Background gradient: linear-gradient(135deg, #1a472a 0%, #0d2818 50%, #0a1f12 100%)
Message bar:       rgba(0,0,0,0.4)
Header bar:        rgba(0,0,0,0.3)
Text (normal):     #e8e4d9
Text (dimmed):     #aaa
Text (dark gray):  #888, #666
Drawn indicator:   #1565c0  (blue)
Gold text:         #ffd700
```

**Trick Markers:**
```
Regular:           linear-gradient(135deg, #1e3a5f 0%, #0d1b2a 100%)
High trump:        linear-gradient(135deg, #8b0000 0%, #5c0000 100%)
```

### Typography

**Fonts:**
```
Body:              'Palatino Linotype', Palatino, Georgia, serif
Game UI:           'Arial, sans-serif'
```

**Font Sizes:**
```
Version:           8px
Trick markers:     9px (text)
Cards drawn:       9px
Score table:       10px (body), 9px (collapse toggle)
Bid indicators:    10px
Player names:      11px (North/South), 10px (East/West)
Messages:          12px
Buttons:           12px (most), 14px (Start)
Headers:           14px
Card rank:         15px (regular), 12px (small)
Card suit:         22px (regular), 16px (small)
Trump display:     64px
```

---

## 13. SPACING & SIZING STANDARDS

### Gaps Between Elements
```
Cards in hand (yours):        2px
Cards in hand (opponents):    1px
Trick markers:                1px
UI components (general):      4px
Button area buttons:          4px
Modal sections:               12px
```

### Padding
```
Main container:               4px (all sides)
Header bar:                   4px 8px (vert horiz)
Message bar:                  (none - uses flex center)
Button area:                  4px 0 (vert horiz)
Score table:                  4px
Modal content:                12px
Table cells:                  1px 2px
```

### Fixed Heights (CRITICAL for preventing layout shift)
```
Message bar:                  24px
North player info row:        16px
North player bid/tricks:      20px
West/East dealer area:        14px
West/East cards drawn:        14px
West/East bid area:           18px
West/East tricks area:        20px
South player info row:        20px
South player hand:            minHeight: 68px
Button area:                  minHeight: 36px
Last trick area:              44px
```

### Component Sizes
```
Circle diameter:              150px x 150px
Circle border:                2px
Card (small):                 30px x 42px
Card (regular):               48px x 68px
Dealer badge:                 ~40px wide container
Help button:                  20px diameter
Close button (modal):         24px x 24px
Trick marker:                 14px x 18px
Drawn indicator dot:          5px diameter
Trick number badge:           14px diameter
```

### Borders
```
Circle:                       2px solid rgba(212,175,55,0.3)
Cards (normal):               1px solid #ccc
Cards (selected/playable):    2px solid
Face down cards:              1px solid #2d5a87
Modal:                        2px solid #d4af37
Table header:                 1px solid rgba(255,255,255,0.2)
```

### Border Radius
```
Circle:                       50%
Cards:                        4px
Buttons (most):               4px
Start button:                 6px
Header bar:                   6px
Message bar:                  4px
Badges:                       2px-3px
Modal:                        8px
Drawn indicator:              50%
Trick number badge:           50%
```

---

## 14. ANIMATION BEHAVIORS

### Card Selection (Discard Phase)
```javascript
transition: 'all 0.1s'
transform: selected ? 'translateY(-2px)' : 'none'
```
- Lifts card up by 2px when selected
- 0.1s transition for smooth movement

### Card Playability Indicator
```javascript
transition: 'all 0.1s'
transform: playable ? 'translateY(-2px)' : 'none'
border: '2px solid #2196f3'
boxShadow: '0 2px 6px rgba(0,0,0,0.3)'
```
- Same lift as selection
- Blue border appears
- Shadow appears

### Trick Collection Animation
```javascript
// Winner position calculation
const winPos = (w) => ({
  0: { x: 0, y: 80 },    // South
  1: { x: -80, y: 0 },   // West
  2: { x: 0, y: -80 },   // North
  3: { x: 80, y: 0 }     // East
}[w]);

// Applied to cards
{
  transition: isAnimating ? 'all 0.4s ease' : 'none',
  transform: isAnimating 
    ? `translate(${winPos.x}px, ${winPos.y}px) scale(0.2)` 
    : pos.transform,
  opacity: isAnimating ? 0 : 1
}
```
- 0.4s duration
- Cards move toward winner
- Scale down to 0.2 (20%)
- Fade to opacity 0

---

## 15. CRITICAL IMPLEMENTATION RULES

### DO NOT CHANGE
1. **Player positions:** P0=South, P1=West, P2=North, P3=East
2. **Circle size:** 150px x 150px
3. **Card positioning:** 4px from circle edge
4. **Fixed heights:** Message bar (24px), Button area (36px), Last trick (44px)
5. **Color scheme:** Gold #d4af37, Green #4caf50, Red #f44336
6. **Font sizes:** Trump (64px), Cards (15/12px rank, 22/16px suit)
7. **Card sizes:** Small (30x42), Regular (48x68)
8. **ShowHandsModal order:** Top=P2, Left=P1, Right=P3, Bottom=P0

### ALWAYS INCLUDE
1. Trump suit ALWAYS visible in circle (behind cards)
2. Drawn indicator (blue dot) on drawn cards
3. High trump indicator (red marker) on first trick marker
4. Dealer badge placement
5. Cards drawn indicator (+X)
6. Bid indicators with proper colors
7. All fixed-height containers

### NEVER DO
1. Change player visual positions
2. Remove fixed heights (causes layout shift)
3. Change card distance from circle (must be 4px)
4. Remove trump display from circle
5. Change button colors (especially Pass = yellow)
6. Add elements to header bar
7. Change ShowHandsModal player order

---

## 16. PHASE-SPECIFIC UI STATES

### Phase: 'dealing'
- **Buttons:** Start button only (10px 24px padding, 14px font, bold, gold)
- **Message:** "Click Start to begin"
- **Cards:** All face down
- **Circle:** Empty

### Phase: 'bidding'
- **Buttons:** [15] [20] [25] [30] [Pass] (only when currentPlayer === 0)
- **Message:** "P1 bids..." or "Your turn to bid"
- **Bid indicators:** Show as players bid
- **Cards:** All face down except yours (face up, not playable)

### Phase: 'trump-select'
- **Buttons:** Four suit buttons (18px symbols)
- **Message:** "Select trump suit"
- **Cards:** Face down except yours
- **Circle:** Empty

### Phase: 'discarding'
- **Buttons:** "Discard (X)" button (green, shows selected count)
- **Message:** "Select X cards to discard" or "P2 discarding..."
- **Cards:** Yours are selectable (click toggles selected state)
- **Selected cards:** Yellow background (#fffde7), amber border
- **Circle:** Empty

### Phase: 'playing'
- **Buttons:** None
- **Message:** "P1's turn" or "Your turn"
- **Cards:** Playable cards have blue border, lift on hover
- **Circle:** Shows trump suit + trick cards
- **Last trick:** Shows previous 4 cards

### Phase: 'trick-end'
- **Buttons:** None
- **Message:** "P2 wins the trick!"
- **Circle:** Shows winning cards (briefly, then animates)
- **Animation:** Cards move toward winner, scale down, fade
- **Tricks won:** Update immediately

### Phase: 'round-end'
- **Buttons:** [Show Hands] [Next]
- **Message:** Shows round result, scores
- **Cards:** All face down
- **Circle:** Shows round score below (e.g., "5-0")
- **Last trick:** Still visible

### Phase: 'game-over'
- **Buttons:** [Show Hands] [New Game]
- **Message:** "Us win 120-45!" or "Them win..."
- **Circle:** Shows final game score
- **Score table:** Shows all rounds

---

## 17. RESPONSIVE BEHAVIOR

### 3.5.9 Approach
- **Fixed layout:** Designed for single size (400px max width)
- **No media queries:** All sizing is absolute
- **Mobile:** Viewport meta tag prevents zooming
  ```html
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  ```
- **Overflow:** Hidden on body (position: fixed, width/height: 100%)

### Future Multiplayer Considerations
When adding responsive design for multiplayer lobby/waiting room:
1. Keep game table layout EXACTLY as 3.5.9
2. Only modify lobby/waiting room for mobile
3. Use window.innerWidth checks, not CSS media queries (to match React inline styles)
4. Maintain all fixed heights to prevent layout shift
5. Keep button sizes consistent across breakpoints

---

## 18. ACCESSIBILITY NOTES

### Current State (3.5.9)
- **Keyboard:** No keyboard controls
- **Screen readers:** No ARIA labels
- **Focus indicators:** Default browser focus only
- **Color contrast:** Good (tested visually)
- **Touch targets:** Buttons are adequate (min 40px height)

### Future Improvements (if needed)
- Add keyboard shortcuts for bidding (1-4, P)
- Add ARIA labels for screen readers
- Add focus indicators for keyboard navigation
- Ensure touch targets are min 44x44px on mobile

---

## 19. VERSION HISTORY & CHANGELOG

### v3.5.9 (Final Single-Player)
- Consistent P1-P4 labeling
- All UI elements finalized
- Layout optimization complete
- This is the reference version for all multiplayer builds

### Key Features Locked In
1. 150px circle with 4px card spacing
2. Trump always visible behind cards
3. Fixed-height containers
4. Exact color scheme
5. Player position mapping
6. ShowHandsModal layout
7. All component specifications

---

## 20. TESTING CHECKLIST

Use this checklist when implementing UI changes:

### Layout Tests
- [ ] Header shows: Title | Help | Scores
- [ ] Message bar is 24px height (fixed)
- [ ] Player positions: South (0), West (1), North (2), East (3)
- [ ] Circle is 150px x 150px
- [ ] Trump suit visible in circle at 64px, 0.3 opacity
- [ ] Cards are 4px from circle edge
- [ ] Button area is 36px min height
- [ ] Last trick area is 44px height

### Component Tests
- [ ] Small cards are 30x42px
- [ ] Regular cards are 48x68px
- [ ] Dealer badge appears correctly
- [ ] Cards drawn indicator shows "+X"
- [ ] Trick markers: 14x18px, blue (red if high trump)
- [ ] Bid indicators show correct colors
- [ ] Drawn cards have blue dot (5px)

### Color Tests
- [ ] Gold (#d4af37) used for headers, badges, borders
- [ ] Green (#4caf50) for "Us" score
- [ ] Red (#f44336) for "Them" score
- [ ] Blue (#2196f3) for playable cards, bid winner
- [ ] Yellow (#c9a227) for Pass button
- [ ] Card suits: Red (#c62828) or Black (#212121)

### Interaction Tests
- [ ] Cards lift 2px when selected/playable
- [ ] Selected cards have yellow bg + amber border
- [ ] Playable cards have blue border
- [ ] Pass button is yellow with black text
- [ ] Trick collection animates correctly
- [ ] ShowHandsModal player order: Top=P2, L=P1, R=P3, B=P0

### Layout Shift Tests
- [ ] No layout shift during bidding phase
- [ ] No layout shift when buttons change
- [ ] No layout shift when last trick appears/disappears
- [ ] No layout shift when score table expands

---

## 21. QUICK REFERENCE

### Most Commonly Changed (RESIST CHANGES)
1. **Card distance from circle:** MUST be 4px
2. **Circle size:** MUST be 150px x 150px
3. **Player positions:** NEVER change mapping
4. **Pass button color:** MUST be yellow (#c9a227)
5. **Trump display:** ALWAYS visible, 64px, 0.3 opacity
6. **ShowHandsModal order:** NEVER change

### Most Important Fixed Heights
```
Message bar:    24px
Button area:    36px (min)
Last trick:     44px
South info:     20px
```

### Most Important Gaps
```
Your cards:     2px
Other cards:    1px
Buttons:        4px
Circle cards:   4px from edge
```

### Most Important Colors
```
Gold:           #d4af37
Green (Us):     #4caf50
Red (Them):     #f44336
Blue (Action):  #2196f3
Yellow (Pass):  #c9a227
```

---

## FINAL NOTE

**This document is the single source of truth for all 45s UI design decisions.**

When building multiplayer features:
1. Keep the game table EXACTLY as specified here
2. Only add new UI for lobby/waiting room/user accounts
3. Reference this document for ALL styling decisions
4. Never deviate without documenting why

**If you must change something, update this document first.**

---

**Document Version:** 1.0  
**Based On:** 45s v3.5.9  
**Created:** January 2026  
**Last Updated:** January 2026  
**Status:** LOCKED - Reference Only

---

## 22. VERSION NUMBER FORMAT

**Added:** January 2026 (after v2.5.5 audit)

### Requirements

**Format:** `vX.Y.Z`
**Maximum Length:** 8 characters
**Examples:**
- ✅ `v2.5.6`
- ✅ `v11.2.3`
- ✅ `v1.0.0`
- ❌ `2.5.5-PROPER-FIX` (too long)
- ❌ `v2.5.4-DESIGN-SPEC` (too long)
- ❌ `v2.5.4-DESIGN-SPEC-MULTIPLAYER` (way too long)

### Rationale
Long version strings interfere with header layout and readability on mobile devices.

### Display
```javascript
// In header
<span style={{ fontSize: '8px', color: '#666' }}>v{VERSION}</span>

// Do NOT add suffixes
// ❌ WRONG: v{VERSION}-MULTIPLAYER
// ✅ RIGHT: v{VERSION}
```

### Versioning Strategy
**Semantic Versioning:**
- Major: Breaking changes
- Minor: New features
- Patch: Bug fixes

**Example:**
- v2.5.6 → Bug fixes to layout
- v2.6.0 → Add new feature
- v3.0.0 → Major rewrite

### Critical
This is part of Section 2 (Header Bar) compliance. Version string is tested as part of header bar verification.
