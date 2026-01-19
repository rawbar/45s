# AI Desperation Bidding Strategy

## Trigger Condition

Desperation mode activates when:
- **Winning team**: needs ≤30 points to win
- **Desperation team**: needs >30 points to win

## Core Principle

**NEVER allow a team needing ≤15 points to win the bid for 15.**

Force them to bid 20+ or bag them (dealer forced to take 15).

---

## Scenario 1: Winning Team HAS the Dealer

Bidding order example (if dealer is on winning team):
```
P1 (desperation) → P2 (winning) → P3 (desperation) → P4/Dealer (winning)
```

### Strategy for Desperation Team:

**After winning team bids 15 or 20:**
- Next desperation player MUST overbid automatically
- Bid 20 over their 15, bid 25 over their 20

**After winning team bids 25:**
- Let them have it, try to set them
- Don't bid 30 unless guaranteed hand

**If winning team hasn't bid yet (you're bidding before them):**

| Winning Team Needs | Desperation Action |
|-------------------|-------------------|
| ≤5 points | Pass and BAG THE DEALER, unless 75%+ chance of making 20+ |
| 6-10 points | Bid 20 if decent hand (70%+ success), else pass and bag dealer |
| 11-15 points | Bid 20 NO MATTER WHAT - cannot let them win for 15 |
| 16-20 points | Bid aggressively, overbid any 15 from winning team |
| 21-30 points | Normal desperation rules apply |

### Bag the Dealer Strategy

If all desperation team players pass, the dealer (on winning team) is forced to bid 15.
- This gives desperation team a chance to SET them
- Better than letting them easily win a 15 bid

---

## Scenario 2: Winning Team Does NOT Have the Dealer (Bids First)

Bidding order example (if dealer is on desperation team):
```
P1 (winning) → P2 (desperation) → P3 (winning) → P4/Dealer (desperation)
```

### Strategy:

**If P1 (winning team) bids 15:**
- P2 (desperation): If have 5 of ANY suit → bid 20
- P2 (desperation): If terrible hand → pass, let partner (P4) take bid
- NEVER let 15 stand if winning team needs ≤15

**If P1 (winning team) passes:**
- P2 (desperation): If have 5 → bid 20
- P2 (desperation): Otherwise bid normally but ADD 5 to bid
- P2 (desperation): If terrible hand → pass, hope partner (P4) has better

**If P3 (winning team) bids 20 AND it would win them the game:**
- P4 (desperation/dealer): Bid 25 REGARDLESS of cards
- Keep the game alive at all costs

---

## Decision Matrix

### When to Overbid Regardless of Hand

| Situation | Action |
|-----------|--------|
| Winning team needs ≤15, they bid 15 | ALWAYS bid 20 |
| Winning team needs ≤20, they bid 20 | Bid 25 if you're the last chance |
| Winning team has dealer, needs ≤15 | Bid 20 before they can bid |

### When to Pass and Bag

| Situation | Action |
|-----------|--------|
| Winning team needs ≤5, has dealer | Pass (bag them) unless 75%+ for 20 |
| Winning team needs 6-10, has dealer | Pass if hand is terrible, else bid 20 |
| Partner already bid, you have nothing | Pass, support partner |

---

## Implementation Notes

### Key Variables Needed:
```javascript
const myTeam = getTeam(playerIndex);
const oppTeam = 1 - myTeam;
const myTeamNeeds = 120 - teamScores;
const oppTeamNeeds = 120 - oppScores;

const oppAboutToWin = oppTeamNeeds <= 30 && myTeamNeeds > 30;
const oppCanWinWith15 = oppTeamNeeds <= 15;
const oppCanWinWith20 = oppTeamNeeds <= 20;
const oppHasDealer = getTeam(dealer) === oppTeam;

// Check if opponent has already bid
const oppHasBid = /* check if any opponent position has bid > 0 */;
const oppBidAmount = /* highest bid from opponent team */;
```

### Bid Order Awareness:
- Need to know if we're bidding BEFORE or AFTER winning team members
- Need to know if our partner has already bid/passed
- Need to know dealer position relative to teams

---

## Examples

### Example 1: Opponent needs 15, has dealer
- Score: Us 85, Them 105
- They need 15, we need 35
- Their player bids 15
- **Action**: Bid 20 NO MATTER WHAT

### Example 2: Opponent needs 10, has dealer
- Score: Us 75, Them 110
- They need 10, we need 45
- We're first to bid, have decent hand
- **Action**: Bid 20 if 70%+ success, else pass to bag dealer

### Example 3: Opponent needs 5, has dealer
- Score: Us 60, Them 115
- They need 5, we need 60
- **Action**: Pass and bag dealer (they'll likely fail at forced 15)

### Example 4: Opponent needs 20, bids 20
- Score: Us 90, Them 100
- They need 20, we need 30
- Opponent bids 20 (would win game)
- We're last to bid
- **Action**: Bid 25 REGARDLESS of hand

---

## Priority Order

1. If opponent needs ≤15 and bid 15 → MUST overbid to 20
2. If opponent bid would win game → overbid if last chance
3. If opponent has dealer and needs ≤15 → bid 20 preemptively
4. If opponent has dealer and needs ≤5 → consider bagging
5. Otherwise → apply normal bidding with +5 aggression boost
