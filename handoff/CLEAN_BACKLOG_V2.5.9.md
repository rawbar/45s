# 45s Multiplayer - Clean Backlog from v2.5.9

**BASELINE:** v2.5.9 (uploaded January 9, 2026)  
**STATUS:** Working game, no critical bugs  
**APPROACH:** Add features incrementally with testing phases

---

## 🎯 CURRENT STATE (v2.5.9)

### ✅ What Works:
- Core gameplay (bidding, trump, discarding, playing)
- Round-end and game-over overlays
- ShowHandsModal with correct player order
- Last Trick display
- Score Table (collapsible)
- Layout matches design spec (flexbox, players at edges)
- Trump always visible
- All dimensions correct per design spec
- Us/Them scores display correctly on game-over ✅

### ❌ What's Missing (To Be Added Back):
Everything listed in "Features to Add Back" section below

---

## 🔴 IMMEDIATE FIXES NEEDED

### 1. Remove Lobby Button from Round-End ⚠️
**Priority:** HIGH  
**Status:** Bug in v2.5.9

**Current State:**
- Round-end overlay has: `[View Round] [Lobby] [Next Round]`
- Game-over overlay has: `[View Round] [Lobby] [New Game]`

**Should Be:**
- Round-end overlay: `[View Round] [Next Round]` (NO Lobby)
- Game-over overlay: `[View Round] [Lobby] [New Game]` (Lobby stays)

**Reason:**  
Lobby button should ONLY appear on final game-over screen, not between rounds.

**Location:** Line ~6022-6035 in v2.5.9  
**Estimate:** 2 minutes  
**Risk:** None

---

## 📋 FEATURES TO ADD BACK (In Priority Order)

These were attempted previously but never worked properly. Will be added back incrementally with testing.

---

### PHASE 1: Lobby Improvements (30-60 min)

#### 2. Connected Players Display
**Status:** Not implemented in v2.5.9  
**Description:** Show which players are connected in lobby  
**Features:**
- Real-time connection status
- Player names/avatars
- Online indicators
- "Waiting for players..." messages

**Previous Issues:** Unknown (was attempted but failed)  
**Testing Required:** Full multiplayer flow

---

#### 3. Game Cleanup - Unknown Start Dates
**Status:** Not implemented in v2.5.9  
**Description:** Remove/hide games from lobby that have unknown or invalid start dates  
**Features:**
- Filter out corrupted game entries
- Clean up stale games
- Prevent joining broken games

**Previous Issues:** Unknown (was attempted but failed)  
**Testing Required:** Edge cases, Firebase data validation

---

#### 4. Fantasy-Themed Player Icons
**Status:** Not implemented in v2.5.9 (using generic avatars)  
**Description:** Replace current player icon set with fantasy-themed icons  
**Features:**
- New icon set (wizard, warrior, rogue, cleric, etc.)
- Avatar picker in lobby
- Icons display in game

**Previous Issues:** Unknown (was attempted but failed)  
**Assets Needed:** Icon images/files  
**Testing Required:** Visual consistency, mobile display

---

### PHASE 2: Lobby Mobile UI Fixes (30-60 min)

#### 5. Lobby Mobile Scrolling
**Status:** Not implemented in v2.5.9  
**Description:** Lobby content doesn't scroll on mobile, causing elements to be cut off  
**Issues:**
- Content extends beyond viewport
- No scrolling enabled
- Bottom elements inaccessible

**Previous Issues:** Unknown (was attempted but failed)  
**Testing Required:** Multiple mobile screen sizes

---

#### 6. Lobby Button Positioning (Mobile)
**Status:** Not implemented in v2.5.9  
**Description:** Buttons cut off at bottom of screen on mobile  
**Issues:**
- Join/Create buttons not visible
- Can't tap buttons
- Layout doesn't adapt to mobile viewport

**Previous Issues:** Unknown (was attempted but failed)  
**Testing Required:** iPhone, Android, various sizes

---

#### 7. Next Screen Mobile Issues
**Status:** Not documented - need details  
**Description:** Issues with screen after lobby (game setup? player selection?)  
**Issues:** Need specifics from user

**Previous Issues:** Unknown  
**Testing Required:** TBD

---

### PHASE 3: AI Strategy Improvements (2-4 hours)

#### 8. Monte Carlo AI Strategy
**Status:** Not implemented in v2.5.9  
**Description:** Multiplayer AI not using Monte Carlo simulation that 3.5.9 uses  
**Impact:** Dumb play, poor decisions  
**Example Issues:**
- Partner plays J♠, then partner plays 5♠ taking trick away
- Doesn't consider partner's likely holdings
- Doesn't simulate outcomes
- Plays random legal cards instead of strategic ones

**Previous Issues:** Unknown (was attempted but failed)  
**Complexity:** HIGH - AI logic is complex  
**Testing Required:** Extensive gameplay testing

---

#### 9. Heuristic AI Strategy
**Status:** Not implemented in v2.5.9  
**Description:** Multiplayer AI not using heuristics that 3.5.9 uses  
**Missing Logic:**
- Trump tracking per player
- Void detection
- Card counting
- Partner communication
- 2nd man low strategy
- 3rd man high strategy
- Setting opponents vs maximizing points

**Previous Issues:** Unknown (was attempted but failed)  
**Complexity:** HIGH  
**Testing Required:** Compare to 3.5.9 play quality

---

### PHASE 4: Other Features (TBD)

#### 10. Other Features Removed
**Status:** User mentioned "a LOT more than this"  
**Description:** Need complete list from user  
**Action Required:** User to provide full list of features attempted

---

## 🧪 TESTING APPROACH

### For Each Phase:
1. Implement feature in isolation
2. Test on desktop Chrome
3. Test on mobile (iOS and Android)
4. Test multiplayer with 2-4 players
5. **Verify no existing features broken**
6. Document any issues
7. Only proceed to next phase if stable

### Rollback Strategy:
- Keep v2.5.9 as known-good baseline
- If phase fails, revert to last working version
- Document what failed and why
- Adjust approach before retry

---

## ⏱️ TIME ESTIMATES

| Phase | Features | Est. Time | Complexity |
|-------|----------|-----------|------------|
| Fix 1 | Remove Lobby button | 2 min | Low |
| Phase 1 | Lobby improvements | 1-2 hours | Medium |
| Phase 2 | Mobile UI fixes | 1-2 hours | Medium |
| Phase 3 | AI strategy | 4-8 hours | High |
| Phase 4 | Other features | TBD | TBD |

**Total Estimated Time:** 8-15 hours (not including Phase 4)

---

## 🚨 RISKS

### Known Risks from Previous Attempts:
1. **Mobile UI:** Scrolling and positioning issues hard to debug
2. **AI Strategy:** Complex logic, hard to test thoroughly
3. **Multiplayer:** Real-time sync issues, race conditions
4. **Firebase:** Data corruption, cleanup logic

### Mitigation:
- Small incremental changes
- Test each change thoroughly before proceeding
- Keep working versions for rollback
- Document failures to avoid repeating

---

## 📝 QUESTIONS FOR USER

1. **Phase 1 Priority:** Which lobby feature is most important?
   - Connected players display?
   - Game cleanup?
   - Fantasy icons?

2. **Phase 2 Details:** What specific mobile issues exist on "next screen"?

3. **Phase 4:** What are the other features that were attempted and removed?

4. **AI Strategy:** Do you have the 3.5.9 AI code available for reference?

5. **Testing:** Can you test on real mobile devices? (iOS/Android)

---

## 🎯 RECOMMENDED NEXT STEPS

### Immediate (Today):
1. ✅ Confirm v2.5.9 as baseline
2. ✅ Document complete backlog (this file)
3. **Fix:** Remove Lobby button from round-end (2 min)
4. **Test:** Verify fix doesn't break anything
5. **Deploy:** v2.6.0 with that one fix

### Phase 1 (This Week):
1. **Choose:** Which lobby feature to tackle first
2. **Implement:** That feature only
3. **Test:** Desktop + mobile
4. **Review:** If stable, move to next feature

### Phase 2+ (Next Week):
Continue incrementally based on Phase 1 success.

---

## 💡 KEY LEARNINGS

### What Went Wrong Before:
- Trying to add too many features at once
- Not testing incrementally
- Complex features (AI) introduced instability
- Mobile issues hard to debug without device testing

### New Approach:
- ✅ One feature at a time
- ✅ Test thoroughly before proceeding
- ✅ Document failures
- ✅ Keep working baseline
- ✅ User testing at each phase

---

## 📊 VERSION HISTORY

| Version | Status | Notes |
|---------|--------|-------|
| 2.5.6 | ✅ | Layout rewrite, design spec compliance |
| 2.5.7 | ✅ | Added round-end/game-over overlays |
| 2.5.8 | ✅ | Added Last Trick, Score Table, fixed modal |
| 2.5.9 | ✅ | Fixed Us/Them, added Lobby buttons (BASELINE) |
| 2.6.0 | 🔜 | Remove Lobby from round-end (next) |

---

## ✅ CURRENT ACTION

**Status:** Awaiting user approval to proceed with Fix #1 (Remove Lobby button from round-end)

**No code changes made** - just documented backlog as requested.
