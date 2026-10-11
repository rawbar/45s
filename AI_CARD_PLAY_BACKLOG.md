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

---

## BACKLOG: Bidder leads last trump on trick 4 instead of offsuit (reported 2026-10-10)

**Status:** Not started. To be picked up after the v2.31.141/142 rollout settles.

**Screenshot hand** (Round Summary, v2.31.142, hand 1 of the game; screenshot saved by the user, not in repo):
- Trump ♦, bid 20 by AI Player 2 (dealer, "D"). Final: bidder's team 20, defenders 10.
- Bidder led trump on tricks 1-4: 5♦, A♦, 9♦, then 6♦ on trick 4. He still held 2♣ as his last card.
- Defender Robr (human) took trick 4 with A♥ (trump) over the 6♦, then led K♣ on trick 5.
- **User's call:** bidder should have led the offsuit 2♣ on trick 4 and would have scored 25 instead of 20.

**My unverified analysis (check before acting):**
- On trick 4 the bidder had exactly 1 trump (6♦, not boss: A♥ still unaccounted) + 1 offsuit. This is the case the existing "ENDGAME TRUMP TIMING" block in `chooseCardToPlay` is meant to handle (lead offsuit to force out an opponent's trump when an opponent is likely to still hold one).
- **Suspected off-by-one:** that block is gated `trickNum >= 4 && trumps.length === 1 && nonTrumps.length === 1`. In the JS, `trickNum` is 0-indexed (the INTEL log prints `trick ${trickNum + 1}`), so a hand with 2 cards left is `trickNum === 3`. The gate can then never be true (with `trickNum >= 4` the hand has 1 card). The Python simulator (`improved_ai.py`, `round_runner.py`) uses a 1-indexed `trick_num`, so there the same rule works as intended. If confirmed, this rule is dead code in the live game and the rig results for it do not apply to what players see.
- It is not obvious how the 2♣ lead scores 25 (Robr held both K♣ and A♥; with 2♣ led he can win with K♣ and still hold A♥ for trick 5). Replay the exact hands in the simulator before deciding what the right rule is.

**Next steps:**
1. Confirm the 0- vs 1-index mismatch in `chooseCardToPlay` and any other rules ported from the Python rig (`trickNum` gates in `index.html` vs `trick_num` in the rig).
2. Replay this exact deal in the rig, comparing "lead 6♦" vs "lead 2♣" on trick 4.
3. If the endgame rule is dead, fix the index (rig-test first), then re-check this hand.
