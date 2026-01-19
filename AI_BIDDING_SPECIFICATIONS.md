# AI Bidding Specifications

## Training Data Source
- 500,000 iteration neural network training
- 20,000 test run sample for statistics below

## Bid Success Rates (Empirical)

| Bid | Attempts | Made | Success Rate |
|-----|----------|------|--------------|
| 15  | 24,339   | 21,213 | **87.2%** |
| 20  | 62,328   | 45,645 | **73.2%** |
| 25  | 142,015  | 73,908 | **52.0%** |
| 30  | 416,045  | 100,988 | **24.3%** |

### Interpretation
- **Bid 15**: Very safe, almost always makes
- **Bid 20**: Still reliable, ~3 in 4 succeed
- **Bid 25**: Coin flip - only bid with strong hand
- **Bid 30**: High risk - only 1 in 4 succeed, requires exceptional hand

## Key Card Impact on Success

| Condition | Bids | Success Rate | Delta |
|-----------|------|--------------|-------|
| With 5 of trump | 154,728 | **51.5%** | +18.4% |
| Without 5 of trump | 489,999 | 33.1% | baseline |
| With J of trump | 146,256 | **45.9%** | +10.9% |
| Without J of trump | 498,471 | 35.0% | baseline |

### Key Finding
> "Bidding 30 too aggressively generally results in getting set."

## Recommended Bidding Thresholds

Based on empirical data, AI should:

1. **Bid 15**: With 2+ trump including any face card
2. **Bid 20**: With 3+ trump OR 2 trump including 5/J/A
3. **Bid 25**: Only with 4+ trump OR 3 trump including 5 of trump
4. **Bid 30**: Only with 5 of trump AND Jack of trump AND 2+ other trump
   - Even then, expect ~50% success at best
   - Never bid 30 without the 5 of trump

## Implementation Notes

The `decideBid()` function should:
1. Count trump cards in hand
2. Identify presence of 5 of trump (most important)
3. Identify presence of Jack of trump (second most important)
4. Apply conservative thresholds based on above data
5. Prefer lower bids when marginal - the data shows overbidding loses games

## Card Value Rankings for Bidding

1. **5 of trump** - Most valuable (+18.4% success)
2. **Jack of trump** - Second most valuable (+10.9% success)
3. **Ace of Hearts** - Always trump, reliable trick
4. **Ace of trump** - High value but beatable by 5/J/AH
5. **King/Queen of trump** - Moderate value
6. **Low trump** - Filler, helps follow suit

## Version History
- Created: v2.12.0
- Data source: 45s-mega-trainer neural network training runs
