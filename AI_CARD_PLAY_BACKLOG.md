# AI Card Play Strategy Backlog

**Created:** v2.17.17
**Status:** Research/Planning Phase

---

## Overview

Improve AI card play decisions by tracking and using information about:
1. Number of cards each player drew
2. What cards players throw (reveals minimum trump quality)
3. Who is out of trump (threw offsuit on trump lead)
4. Positional play (who plays after you)

---

## What We Can Track

| Information | How We Know | Example |
|-------------|-------------|---------|
| Out of trump | Threw offsuit on trump lead | Player 3 threw 8♣ when spades led |
| Min trump quality | Card thrown on partner's 5 | Partner threw 6♠ → has "better than 6♠" |
| Trump remaining (count) | Drew X, played Y | Drew 3, played 1 = 1 trump left |
| Cards drawn | Tracked in `drawn[]` array | Player drew 4 = weak starting hand |

---

## 5-of-Trump Leading Strategy

### Strong Hand Exception (just lead the 5)
- 5+J + 2-3 more trump
- 5 + 2 trump + K offsuit
- Any dominant hand where analysis isn't needed

### When to Lead 5 Based on Draw Counts

| Partner Drew | Opponents Drew | Strategy |
|--------------|----------------|----------|
| 4 | 4, 4 | Lead 5 (2:1 odds pulling high trump from opponents) |
| 3 or less | 4, 4 | Lead 5, then low offsuit to set up partner's high trump |
| 4 | 0-2, 0-2 | HOLD 5 - opponents have strong trump |
| 3 or less | 0-2, 0-2 | Risky - evaluate carefully |

### Reading Partner's Throw on Your 5

**Key Insight:** Partner throws their WORST trump. We don't know what they have, only that their remaining trump BEATS what they threw.

| Partner Threw | We Know |
|---------------|---------|
| 6♠ | Remaining trump beats 6♠ (could be 7, 8, J, AH - unknown) |
| 9♠ | Remaining trump beats 9♠ |
| Low card | They have something better (but we don't know what) |

---

## Strategic Decisions Using Tracked Info

### When to Save High Trump (J or AH)

**Scenario:** Opponent leads 6♠, you have J or AH
- You KNOW partner has "at least 4♠" (threw 6♠ earlier, took 3 cards)
- You KNOW player 3 is OUT of trump (threw offsuit previously)
- Partner plays LAST

**Decision:** Throw offsuit, save your J/AH. Partner's "4♠ or better" wins this trick.

### When to Play High Trump

- You're last to play, OR
- Partner already played, OR
- All remaining players are out of trump, OR
- Current winning card beats partner's known minimum

### Partner Setup Plays

1. You won trick with 5, partner threw 9♠
2. Partner has "better than 9♠" remaining
3. Lead LOW offsuit → if opponents are out, partner trumps with their high card
4. If opponent trumps, they use up their trump, partner may still beat it

---

## Implementation Notes

### Data Structures Needed

```javascript
// Track minimum trump quality per player
// -1 = unknown, 0 = out of trump, 1-102 = minimum rank they can beat
const minTrumpQuality = [−1, −1, −1, −1];

// Track if player is out of trump
const outOfTrump = [false, false, false, false];

// Existing: cards drawn per player
const drawn = [0, 0, 0, 0];
```

### Logic Flow

1. **On trump lead:** If player throws offsuit → mark outOfTrump[player] = true
2. **On 5 lead:** Track what each player throws → update minTrumpQuality
3. **When deciding play:**
   - Check who plays after me
   - Check if partner can beat current winner (based on minTrumpQuality)
   - Check if remaining opponents are out of trump
   - Save high cards when partner can win

---

## Edge Cases to Handle

1. **Partner threw high card (J/AH) on your 5**
   - Might be signaling they have the OTHER high card
   - Or they might have nothing left
   - Track remaining count to disambiguate

2. **Multiple rounds of information**
   - Round 1: Partner threw 6♠, has "better than 6♠"
   - Round 3: Partner threw 9♠, now has "better than 9♠"
   - Update minimum quality as we learn more

3. **Reneging detection**
   - If player throws offsuit when they should have trump → flag for review
   - (Rare but possible in casual play)

---

## Testing Scenarios

1. Partner drew 3, opponents drew 4, 4 → Lead 5, verify partner throws worst
2. You have J, partner has known "beats 8♠", opponent leads 9♠ → Verify AI throws offsuit
3. Opponent out of trump, partner plays last → Verify AI saves high trump
4. Endgame with known trump distribution → Verify optimal play

---

## Priority

**Medium-High** - This would significantly improve AI play quality, especially in close games where efficient trump management matters.

---

## Related Files

- `index.html` - `chooseCardToPlay()` function (~line 1450)
- `index.html` - `estimateOpponentTrump()` function (~line 1429)
- `index-singleplayer-gold-v3.5.9.html` - Reference implementation

---

## Notes from Discussion

- Don't assume specific cards - only track minimums
- "Partner threw 6♠" means remaining trump BEATS 6♠, could be 7 or could be J
- Positional awareness is key - who plays after you matters
- Save high trump when partner can win without your help
- This builds on existing `drawn[]` and `knownOutOfTrump[]` infrastructure
