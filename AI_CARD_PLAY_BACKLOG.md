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

**Root cause (found 2026-10-10 by reading the code; confirmed by the user's hunch that Robr's renege was counted as "out of trump"):**
- Robr reneged with the A♥ on trick 2 (played 4♣ on the bidder's A♦ lead) and again on trick 3 (7♥ on the 9♦ lead). The trump-tracking code (`index.html` ~17040-17075 and ~17905-17925, the two trick-resolution blocks) correctly notes he "may hold A♥" (`knownVoids[p].trump = 'reneging'`) but ALSO sets `knownOutOfTrump[p] = true` ("backward compat").
- Robr's partner AI Player 1 was likewise flagged on trick 3 (threw 10♠ on a trump lead while A♥ was still unaccounted for).
- On trick 4, `_allVoidHardFlag` in the bidder-lead block (`chooseCardToPlay`, ~6513) treats `knownOutOfTrump` as a HARD void for every opponent, so the ALL-VOID rule fired: "opponents are out of trump, lead the lowest trump, guaranteed win" -> bidder led 6♦ into Robr's A♥.
- The v2.31.137 ALLVOID-DEDUCTION-GUARD (`_estimateContradicted`) does not help here: it only runs when `!_allVoidHardFlag`, on the assumption that the hard flag is "already reliable". It is not reliable when the flag came from a renege.
- This pre-empts the ENDGAME TRUMP TIMING rule, so that rule never got a chance on this hand.

**Proposed fix (needs rig test first):** make the hard flag count only genuine voids (`knownVoids[i].trump === true`), not `'reneging'`. A renege flag means "has at most the unplayed 5 / J / A♥", so while any of those is unaccounted for the ALL-VOID shortcut must not fire. Check the Python simulator (`improved_ai.py` `known_oot`) for the same shortcut; if it sets the flag the same way, rig results for ALL-VOID already include this bug.

**Secondary suspect (separate, lower priority):**
- The ENDGAME TRUMP TIMING gate is `trickNum >= 4 && trumps.length === 1 && nonTrumps.length === 1`. JS `trickNum` is 0-indexed, so with 2 cards in hand `trickNum === 3` and the gate is never true. The Python rig uses a 1-indexed `trick_num`, where it works. Verify, then fix the index (rig-test first).

**Open question:** it is still not clear the 2♣ lead scores 25 on this exact deal (Robr held both K♣ and A♥, so he can win with K♣ and keep the A♥). Replay the deal in the rig for lead-6♦ vs lead-2♣ before treating "25" as the target.

**Next steps:**
1. Replay this deal and confirm the ALL-VOID shortcut fires on trick 4 (the decision log or the "ALL-VOID: P.. leading" console line will show it).
2. Add a rig challenger that restricts the hard flag to true voids, and run primary 20k + held-out.
3. Fix the 0/1-index gate on the endgame rule separately, with its own rig run.
