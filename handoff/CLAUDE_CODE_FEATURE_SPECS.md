# 45s Multiplayer - Feature Specifications for Claude Code

**Current Version:** v2.6.1  
**Baseline File:** `45s_v2.6.1_SETTINGS_MODAL.html`  
**Target Environment:** Claude Code (agentic coding)

---

## CRITICAL: Development Best Practices

### Before Making ANY Code Changes:
1. ✅ Use `view` tool to see exact section before editing
2. ✅ Use `str_replace` tool when possible (more reliable than sed)
3. ✅ Validate syntax after EVERY change
4. ✅ Check for stray lines, unclosed brackets, duplicate closures
5. ✅ Test incrementally - one feature at a time
6. ✅ File has CRLF line endings - check with `cat -A` if issues

### Common Pitfalls to Avoid:
- ❌ Using sed with line numbers without viewing first
- ❌ Leaving stray lines from old code
- ❌ Assuming structure without verifying
- ❌ Making multiple changes without validation
- ❌ Not checking bracket/brace balance

---

## PROJECT CONTEXT

### Current State (v2.6.1):
- ✅ Working multiplayer game with Firebase
- ✅ User accounts with PIN authentication
- ✅ 24 fantasy-themed avatars
- ✅ Settings modal for profile changes
- ✅ Lobby with game creation/joining
- ✅ Full gameplay (bidding, trump, discarding, playing)
- ✅ Round-end and game-over screens
- ✅ Mobile-friendly UI (mostly)

### What's Missing:
These features were attempted previously but never worked properly. Adding them back incrementally with testing.

---

# FEATURE 1: Connected Players Display

**Priority:** Phase 1 - High  
**Complexity:** Medium  
**Estimated Time:** 1-2 hours  
**Status:** Not implemented in v2.6.1

## Overview
Show real-time connection status of players in the lobby. Display who's online, their avatars, and connection state.

## Current Behavior
- Lobby shows list of games
- No indication of which users are online
- No live player presence tracking
- Games show player slots but no real-time status

## Desired Behavior
- Display "Online Players" section in lobby
- Show avatar + username for each connected player
- Green dot indicator for online status
- Update in real-time as players connect/disconnect
- Show total online count

## Technical Implementation

### Firebase Structure
Add presence tracking using Firebase Realtime Database:

```javascript
// Path: /presence/{userId}
{
  userId: "user123",
  username: "PlayerName",
  avatar: "wizard",
  online: true,
  lastSeen: 1704844800000,  // timestamp
  connectedAt: 1704844700000  // timestamp
}
```

### Where to Add Code

**Location:** LobbyScreen component (around line 2280 in v2.6.1)

**1. Add presence state:**
```javascript
const [onlinePlayers, setOnlinePlayers] = useState({});
```

**2. Add presence tracking useEffect:**
```javascript
useEffect(() => {
  // Set this user as online
  const presenceRef = database.ref(`presence/${userId}`);
  const userPresenceData = {
    userId: userId,
    username: playerName,
    avatar: playerAvatar,
    online: true,
    lastSeen: Date.now(),
    connectedAt: Date.now()
  };
  
  // Set online status
  presenceRef.set(userPresenceData);
  
  // Update lastSeen every 30 seconds
  const heartbeatInterval = setInterval(() => {
    presenceRef.update({ lastSeen: Date.now() });
  }, 30000);
  
  // Set offline when disconnecting
  presenceRef.onDisconnect().update({
    online: false,
    lastSeen: Date.now()
  });
  
  // Listen to all online players
  const allPresenceRef = database.ref('presence');
  const presenceListener = allPresenceRef.on('value', (snapshot) => {
    const data = snapshot.val() || {};
    setOnlinePlayers(data);
  });
  
  return () => {
    clearInterval(heartbeatInterval);
    presenceRef.update({ online: false, lastSeen: Date.now() });
    allPresenceRef.off('value', presenceListener);
  };
}, [userId, playerName, playerAvatar]);
```

**3. Add UI section in lobby (after header, before games list):**
```javascript
{/* Online Players */}
<div style={{
  background: 'white',
  borderRadius: '12px',
  padding: '20px',
  marginBottom: '20px',
  boxShadow: '0 4px 16px rgba(0,0,0,0.2)'
}}>
  <h2 style={{ marginBottom: '16px', color: '#1a5f3f' }}>
    Online Players ({Object.values(onlinePlayers).filter(p => p.online).length})
  </h2>
  <div style={{
    display: 'flex',
    flexWrap: 'wrap',
    gap: '12px'
  }}>
    {Object.values(onlinePlayers)
      .filter(player => player.online)
      .map(player => (
        <div
          key={player.userId}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 12px',
            background: '#f5f5f5',
            borderRadius: '8px',
            border: player.userId === userId ? '2px solid #2d8f5f' : '2px solid transparent'
          }}
        >
          <div style={{
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            background: '#4caf50'
          }} />
          <div style={{ fontSize: '24px' }}>
            {getAvatarById(player.avatar).emoji}
          </div>
          <span style={{ fontSize: '14px', color: '#333' }}>
            {player.username}
            {player.userId === userId && ' (You)'}
          </span>
        </div>
      ))}
  </div>
</div>
```

### Cleanup Logic
Add automatic cleanup of stale presence records (offline > 5 minutes):

```javascript
// In lobby mount useEffect
const cleanupStalePresence = async () => {
  const fiveMinutes = 5 * 60 * 1000;
  const now = Date.now();
  const presenceSnapshot = await database.ref('presence').once('value');
  const allPresence = presenceSnapshot.val() || {};
  
  for (const [uid, data] of Object.entries(allPresence)) {
    if (!data.online && (now - data.lastSeen) > fiveMinutes) {
      await database.ref(`presence/${uid}`).remove();
    }
  }
};

cleanupStalePresence();
```

### Testing Checklist
- [ ] Open in two browsers, verify both show as online
- [ ] Close one browser, verify it goes offline
- [ ] Refresh page, verify reconnects properly
- [ ] Check Firebase console shows presence data
- [ ] Verify stale records cleanup after 5 minutes
- [ ] Test with 3+ players simultaneously

### Known Issues from Previous Attempts
- Unknown - feature was attempted but details not documented
- Likely issues: presence not clearing properly, Firebase rules, race conditions

### Firebase Security Rules Needed
```json
{
  "presence": {
    "$userId": {
      ".read": true,
      ".write": "$userId === auth.uid"
    }
  }
}
```

---

# FEATURE 2: Game Cleanup - Unknown Start Dates

**Priority:** Phase 1 - High  
**Complexity:** Low-Medium  
**Estimated Time:** 30-60 minutes  
**Status:** Partial implementation in v2.6.1

## Overview
Remove or hide games from lobby that have unknown, invalid, or missing start dates. Prevent corrupted game entries from cluttering the lobby.

## Current Behavior
- Some cleanup exists (line 2289-2322 in v2.6.1)
- Cleans games inactive > 15 minutes
- Uses `createdAt` OR `gameState.lastActivity` timestamp
- May not handle missing/null timestamps properly

## Issues to Fix
```javascript
// Current code (line 2298-2313)
let timestamp = null;
if (game.gameState && game.gameState.lastActivity) {
  timestamp = game.gameState.lastActivity;
} else if (game.createdAt) {
  timestamp = game.createdAt;
}

if (timestamp) {  // ⚠️ PROBLEM: skips games with no timestamp
  const inactiveTime = now - timestamp;
  if (inactiveTime > fifteenMinutes) {
    await database.ref(`lobby/games/${gameId}`).remove();
  }
}
```

## Desired Behavior
- Remove games with no timestamp at all
- Remove games with invalid timestamps (not a number, negative, future date)
- Remove games older than 24 hours regardless of activity
- Show error message if corruption detected
- Log cleanup actions for debugging

## Technical Implementation

### Enhanced Cleanup Logic

**Location:** LobbyScreen useEffect (line 2289 in v2.6.1)

**Replace existing cleanup with:**

```javascript
const cleanupOldGames = async () => {
  const now = Date.now();
  const fifteenMinutes = 15 * 60 * 1000;
  const twentyFourHours = 24 * 60 * 60 * 1000;
  
  const gamesSnapshot = await database.ref('lobby/games').once('value');
  const allGames = gamesSnapshot.val() || {};
  
  let deletedCount = 0;
  let corruptedCount = 0;
  
  for (const [gameId, game] of Object.entries(allGames)) {
    let shouldDelete = false;
    let reason = '';
    
    // Get timestamp
    let timestamp = null;
    if (game.gameState && game.gameState.lastActivity) {
      timestamp = game.gameState.lastActivity;
    } else if (game.createdAt) {
      timestamp = game.createdAt;
    }
    
    // Check for missing timestamp
    if (!timestamp || timestamp === null || timestamp === undefined) {
      shouldDelete = true;
      reason = 'missing timestamp';
      corruptedCount++;
    }
    // Check for invalid timestamp (not a number)
    else if (typeof timestamp !== 'number' || isNaN(timestamp)) {
      shouldDelete = true;
      reason = 'invalid timestamp (NaN)';
      corruptedCount++;
    }
    // Check for impossible timestamp (negative or far future)
    else if (timestamp < 0 || timestamp > (now + 86400000)) {  // +1 day in future
      shouldDelete = true;
      reason = 'impossible timestamp';
      corruptedCount++;
    }
    // Check for old games (>24 hours)
    else if ((now - timestamp) > twentyFourHours) {
      shouldDelete = true;
      reason = `old game (${Math.floor((now - timestamp) / 3600000)} hours)`;
    }
    // Check for inactive games (>15 minutes)
    else if ((now - timestamp) > fifteenMinutes) {
      shouldDelete = true;
      reason = `inactive (${Math.floor((now - timestamp) / 60000)} minutes)`;
    }
    
    if (shouldDelete) {
      console.log(`🗑️ Deleting game ${gameId}: ${reason}`);
      try {
        await database.ref(`lobby/games/${gameId}`).remove();
        deletedCount++;
      } catch (err) {
        console.error(`Failed to delete game ${gameId}:`, err);
      }
    }
  }
  
  if (deletedCount > 0) {
    console.log(`✅ Cleaned up ${deletedCount} game(s) (${corruptedCount} corrupted)`);
  }
  
  if (corruptedCount > 0) {
    setError(`Found and removed ${corruptedCount} corrupted game(s)`);
    // Clear error after 5 seconds
    setTimeout(() => setError(null), 5000);
  }
};
```

### Additional Validation on Game Creation

**Location:** handleCreateGame function (line 2347 in v2.6.1)

**Add validation:**
```javascript
const handleCreateGame = async () => {
  setLoading(true);
  setError(null);
  try {
    const gameId = generateGameId();
    const gameName = newGameName.trim() || gameId;
    const now = Date.now();
    
    // Validate timestamp
    if (!now || isNaN(now) || now < 0) {
      throw new Error('Failed to generate valid timestamp');
    }
    
    console.log('Creating game:', gameId, gameName, 'at', new Date(now).toISOString());
    
    await database.ref(`lobby/games/${gameId}`).set({
      name: gameName,
      status: 'waiting',
      creatorId: userId,
      createdAt: now,  // Ensure valid number
      lastActivity: now,  // Ensure valid number
      players: {}
    });

    console.log('Game created successfully');
    setShowCreateGame(false);
    setNewGameName('');
  } catch (err) {
    console.error('Error creating game:', err);
    setError('Failed to create game: ' + err.message);
  } finally {
    setLoading(false);
  }
};
```

### Testing Checklist
- [ ] Create game, verify has valid timestamps
- [ ] Manually corrupt game in Firebase (set createdAt: null)
- [ ] Verify lobby cleanup removes it
- [ ] Set createdAt to negative number, verify cleanup
- [ ] Set createdAt to far future, verify cleanup
- [ ] Set createdAt to string "invalid", verify cleanup
- [ ] Create old game (24+ hours), verify cleanup
- [ ] Verify error message shows when corruption found
- [ ] Check console logs show cleanup details

### Known Issues from Previous Attempts
- Unknown - feature was attempted but details not documented
- Likely issues: Firebase data corruption, async timing, cleanup not running

---

# FEATURE 3: Lobby Mobile Scrolling

**Priority:** Phase 2 - Medium  
**Complexity:** Low  
**Estimated Time:** 30 minutes  
**Status:** Not implemented in v2.6.1

## Overview
Enable scrolling in lobby on mobile devices. Currently content extends beyond viewport with no way to scroll.

## Current Behavior
- Lobby content overflows on small screens
- No scrolling enabled
- Bottom elements (games list, create button) cut off
- User cannot access all content

## Desired Behavior
- Full lobby content scrollable on mobile
- Smooth scrolling
- Header stays visible (optional - can scroll too)
- No content cut off
- Works on iOS and Android

## Technical Implementation

### Current Lobby Container

**Location:** LobbyScreen return statement (line 2473 in v2.6.1)

**Current structure:**
```javascript
return (
  <div style={{
    minHeight: '100vh',
    overflow: 'auto',  // ⚠️ This should work but might not
    padding: '20px',
    position: 'relative'
  }}>
```

### Fix: Ensure Proper Scrolling

**Option 1: Force overflow-y scroll**
```javascript
<div style={{
  minHeight: '100vh',
  height: '100vh',  // NEW: Fixed height
  overflowY: 'auto',  // NEW: Explicit vertical scroll
  overflowX: 'hidden',  // NEW: Prevent horizontal scroll
  padding: '20px',
  position: 'relative',
  WebkitOverflowScrolling: 'touch'  // NEW: iOS smooth scrolling
}}>
```

**Option 2: Flexbox approach**
```javascript
<div style={{
  display: 'flex',
  flexDirection: 'column',
  height: '100vh',
  overflow: 'hidden'
}}>
  {/* Header - fixed */}
  <div style={{ flexShrink: 0 }}>
    {/* Header content */}
  </div>
  
  {/* Scrollable content */}
  <div style={{
    flex: 1,
    overflowY: 'auto',
    overflowX: 'hidden',
    padding: '20px',
    WebkitOverflowScrolling: 'touch'
  }}>
    {/* Games list, etc */}
  </div>
</div>
```

### Mobile Viewport Meta Tag

**Location:** HTML head (top of file, around line 5-10)

**Verify this exists:**
```html
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
```

If missing, add it.

### Testing Checklist
- [ ] Test on iPhone (Safari)
- [ ] Test on Android (Chrome)
- [ ] Test on small screen (iPhone SE size)
- [ ] Test on large screen (iPhone Pro Max)
- [ ] Verify all content accessible
- [ ] Verify smooth scrolling
- [ ] Check no horizontal scroll appears
- [ ] Test with many games in list (10+)

### Known Issues from Previous Attempts
- Unknown - feature was attempted but details not documented
- Likely issues: CSS conflicts, position: relative, iOS Safari quirks

---

# FEATURE 4: Lobby Button Positioning (Mobile)

**Priority:** Phase 2 - Medium  
**Complexity:** Low  
**Estimated Time:** 30 minutes  
**Status:** Not implemented in v2.6.1

## Overview
Buttons at bottom of lobby are cut off on mobile screens. Cannot tap Join/Create buttons.

## Current Behavior
- Create Game button may be off-screen
- Join buttons in game list may be cut off
- User cannot access functionality
- Related to scrolling issue

## Desired Behavior
- All buttons visible and tappable
- Adequate spacing around buttons
- No content overlap
- Touch targets at least 44px (iOS guideline)

## Technical Implementation

### Button Spacing

**Location:** Create Game button area (around line 2550 in v2.6.1)

**Current:**
```javascript
<button
  style={{
    padding: '12px 24px',
    fontSize: '16px',
    // ...
  }}
>
  Create New Game
</button>
```

**Add bottom margin/padding:**
```javascript
<div style={{
  marginTop: '20px',
  marginBottom: '40px',  // NEW: Extra space at bottom
  paddingBottom: '20px'  // NEW: Additional padding
}}>
  <button
    style={{
      padding: '14px 28px',  // NEW: Larger touch target
      fontSize: '16px',
      minHeight: '44px',  // NEW: iOS minimum
      width: '100%',  // NEW: Full width on mobile
      maxWidth: '400px',  // Limit on desktop
      // ...
    }}
  >
    Create New Game
  </button>
</div>
```

### Game List Item Buttons

**Location:** GameListItem component (line 2730 in v2.6.1)

**Ensure buttons are large enough:**
```javascript
<button
  style={{
    padding: '10px 20px',
    minHeight: '44px',  // NEW: iOS minimum
    minWidth: '80px',  // NEW: Minimum width
    fontSize: '14px',
    // ...
  }}
>
  Join
</button>
```

### Safe Area Insets (iOS)

**Add CSS for notch/home indicator:**
```javascript
<div style={{
  paddingBottom: 'max(20px, env(safe-area-inset-bottom))',  // NEW
  paddingLeft: 'env(safe-area-inset-left)',  // NEW
  paddingRight: 'env(safe-area-inset-right)',  // NEW
}}>
```

### Testing Checklist
- [ ] Test on iPhone with notch
- [ ] Test on Android with gesture navigation
- [ ] Verify all buttons tappable
- [ ] Check buttons don't overlap
- [ ] Verify minimum 44px touch targets
- [ ] Test landscape orientation
- [ ] Check safe area insets work

### Known Issues from Previous Attempts
- Unknown - feature was attempted but details not documented
- Likely issues: viewport height calculations, safe areas, button z-index

---

# FEATURE 5: Monte Carlo AI Strategy

**Priority:** Phase 3 - High  
**Complexity:** VERY HIGH  
**Estimated Time:** 4-8 hours  
**Status:** Not implemented in v2.6.1

## Overview
Add Monte Carlo simulation to AI decision-making. Currently AI plays randomly/simply. Need strategic play like in single-player version 3.5.9.

## Current Behavior
- AI makes legal moves but not strategic
- Doesn't simulate outcomes
- Doesn't consider partner's hand
- Makes obvious mistakes (e.g., partner plays J♠, then AI plays 5♠ taking trick)

## Desired Behavior
- AI simulates N rollouts per decision
- Evaluates expected value of each move
- Considers partner communication
- Strategic trump usage
- Optimal 2nd/3rd/4th position play

## Reference Implementation
**File:** Single-player version 3.5.9 has working Monte Carlo AI  
**Location:** Look for functions like `simulateGame`, `mctsMove`, `rollout`

## Technical Implementation

### Current AI Location

**File:** v2.6.1  
**Function:** AI decision-making in game logic (search for "AI" or "computer player")  
**Likely around:** Lines 3500-4500 (game state management area)

### What Needs to be Added

**1. Monte Carlo simulation function:**
```javascript
function monteCarloMove(gameState, playerId, numRollouts = 50) {
  const legalMoves = getLegalMoves(gameState, playerId);
  if (legalMoves.length === 1) return legalMoves[0];
  
  const moveScores = {};
  
  for (const move of legalMoves) {
    let totalScore = 0;
    
    for (let i = 0; i < numRollouts; i++) {
      // 1. Create copy of game state
      const simState = cloneGameState(gameState);
      
      // 2. Apply candidate move
      applyMove(simState, playerId, move);
      
      // 3. Simulate rest of game with random play
      const result = simulateToEnd(simState, playerId);
      
      // 4. Score based on outcome
      totalScore += scoreResult(result, playerId);
    }
    
    moveScores[move] = totalScore / numRollouts;
  }
  
  // Return move with highest average score
  return Object.entries(moveScores)
    .sort(([, a], [, b]) => b - a)[0][0];
}
```

**2. Game simulation helper:**
```javascript
function simulateToEnd(gameState, originalPlayerId) {
  const state = cloneGameState(gameState);
  
  while (!isGameOver(state)) {
    const currentPlayer = state.currentPlayer;
    const moves = getLegalMoves(state, currentPlayer);
    
    // Random play for simulation
    const randomMove = moves[Math.floor(Math.random() * moves.length)];
    applyMove(state, currentPlayer, randomMove);
    
    if (isTrickComplete(state)) {
      resolveTrick(state);
    }
  }
  
  return state.finalScore;
}
```

**3. Scoring function:**
```javascript
function scoreResult(finalState, playerId) {
  const myTeam = playerId % 2;
  const myScore = finalState.scores[myTeam];
  const opponentScore = finalState.scores[1 - myTeam];
  
  // Score based on:
  // - Did we make our bid?
  // - Did we win?
  // - Point differential
  
  let score = myScore - opponentScore;
  
  if (finalState.bidWinner % 2 === myTeam) {
    // We bid
    if (myScore >= finalState.bidAmount) {
      score += 50;  // Bonus for making bid
    } else {
      score -= 100;  // Penalty for missing bid
    }
  }
  
  return score;
}
```

### Integration Points

**1. Bidding AI:**
- Replace simple bid logic with Monte Carlo simulation
- Simulate outcomes of each bid amount
- Consider hand strength and partnership

**2. Trump Selection:**
- Simulate outcomes for each suit as trump
- Consider hand composition
- Consider likely partner holdings

**3. Discard Selection:**
- Simulate which discards lead to best outcomes
- Consider trump strength after discard

**4. Card Play:**
- This is the main use case
- Simulate from current trick state
- Consider all legal plays

### Performance Considerations

- Start with **5 rollouts** (fast, decent quality)
- Can increase to 50 rollouts for better play (slower)
- Add timeout to prevent freezing (max 2 seconds per move)
- Cache simulations for repeated states

### Testing Checklist
- [ ] AI makes reasonable bids
- [ ] AI doesn't underbid strong hands
- [ ] AI chooses good trump suits
- [ ] AI doesn't take partner's tricks unnecessarily
- [ ] AI leads appropriate cards
- [ ] AI plays strategically in 2nd/3rd/4th position
- [ ] Performance acceptable (moves < 2 seconds)
- [ ] Compare quality to 3.5.9 single-player AI

### Known Issues from Previous Attempts
- Feature was attempted but failed
- Likely issues:
  - Game state cloning not working correctly
  - Infinite loops in simulation
  - Performance too slow
  - Integration with Firebase real-time updates
  - Race conditions with game state

### Recommended Approach
1. **First:** Get Monte Carlo working in single-player mode locally
2. **Then:** Integrate with multiplayer/Firebase
3. **Test:** Extensively before deploying
4. **Consider:** Making it optional (enable/disable Monte Carlo AI)

---

# FEATURE 6: Heuristic AI Strategy

**Priority:** Phase 3 - High  
**Complexity:** HIGH  
**Estimated Time:** 2-4 hours  
**Status:** Not implemented in v2.6.1

## Overview
Add rule-based heuristics to improve AI play quality. Works alongside or instead of Monte Carlo.

## Desired Heuristics

### Trump Tracking
```javascript
const trumpTracker = {
  spades: { played: 0, total: 13, playersOut: [] },
  hearts: { played: 0, total: 13, playersOut: [] },
  diamonds: { played: 0, total: 13, playersOut: [] },
  clubs: { played: 0, total: 13, playersOut: [] }
};

function updateTrumpTracking(card, player) {
  // Track which players are void in which suits
  // Track how many of each suit played
  // Use for strategic play
}
```

### Void Detection
```javascript
function detectVoid(player, suit, history) {
  // If player didn't follow suit when they could have
  // Mark them as void in that suit
  // Use for future play decisions
}
```

### Card Counting
```javascript
function countRemainingCards(gameState) {
  // Track which high cards still in play
  // Track which trump still out
  // Use for probability calculations
}
```

### Partner Communication
```javascript
function interpretPartnerPlay(partnerCard, trickSoFar) {
  // If partner plays high card, may be showing strength
  // If partner plays low card, may be weak
  // Adjust strategy accordingly
}
```

### Position-Based Strategy

**2nd Man Low:**
```javascript
if (position === 1 && !trick.hasHighCard()) {
  // Play lowest card to let partner win
  return selectLowestCard(legalMoves);
}
```

**3rd Man High:**
```javascript
if (position === 2 && !partnerWinning(trick)) {
  // Try to win trick for partnership
  return selectHighestCard(legalMoves);
}
```

**4th Man:**
```javascript
if (position === 3) {
  if (partnerWinning(trick)) {
    // Partner winning, play lowest
    return selectLowestCard(legalMoves);
  } else {
    // Try to win if possible
    return selectWinningCard(legalMoves, trick) || selectLowestCard(legalMoves);
  }
}
```

### Setting vs Maximizing

```javascript
function decideBidStrategy(hand, currentBid) {
  const teamCurrentScore = getTeamScore(myTeam);
  const opponentScore = getTeamScore(opponentTeam);
  
  if (opponentScore > 100 && teamCurrentScore < 100) {
    // We're behind - need to bid aggressively
    return aggressiveBid(hand);
  } else if (teamCurrentScore > 100) {
    // We're ahead - can play conservatively to "set" opponents
    return conservativeBid(hand);
  }
  
  return standardBid(hand);
}
```

## Implementation Location
- Same area as Monte Carlo AI
- Can be used together or separately
- Heuristics can guide Monte Carlo simulations
- Or heuristics can be used standalone for faster play

## Testing Checklist
- [ ] AI tracks trump correctly
- [ ] AI detects voids
- [ ] AI plays 2nd man low appropriately
- [ ] AI plays 3rd man high appropriately
- [ ] AI adjusts strategy based on score
- [ ] AI communicates with partner
- [ ] Compare to 3.5.9 quality

---

# GENERAL TESTING REQUIREMENTS

## For Each Feature:

### Development Testing:
1. Test locally first
2. Test with one feature at a time
3. Verify no regressions in existing features
4. Check console for errors
5. Validate Firebase data structure

### Mobile Testing:
1. Test on real iOS device (if possible)
2. Test on real Android device (if possible)
3. Test multiple screen sizes
4. Test landscape and portrait
5. Test touch interactions

### Multiplayer Testing:
1. Test with 2 players
2. Test with 4 players
3. Test player disconnection/reconnection
4. Test game state sync
5. Test Firebase race conditions

### Performance Testing:
1. Check page load time
2. Check Firebase query performance
3. Check AI move time (< 2 seconds)
4. Check memory usage
5. Test with slow network

---

# VERSION MANAGEMENT

## Version Numbering:
- Current: v2.6.1
- Each feature: increment minor version (2.7.0, 2.8.0, etc)
- Bug fixes: increment patch (2.6.2, 2.6.3, etc)

## Update VERSION constant:
```javascript
const VERSION = '2.7.0';  // Update this at top of file
```

## Files to Deliver:
1. Updated HTML file with version in filename
2. Changelog documenting changes
3. Test results / verification

---

# FIREBASE STRUCTURE REFERENCE

## Current Structure:
```
/users/{userId}
  - username: string
  - avatar: string
  - pinHash: string
  - createdAt: number

/lobby/games/{gameId}
  - name: string
  - status: "waiting" | "playing" | "finished"
  - creatorId: string
  - createdAt: number
  - lastActivity: number
  - players: {}

/games/{gameId}
  - gameState: {}
  - players: []
  - history: []
  - lastActivity: number
```

## To Be Added:
```
/presence/{userId}
  - userId: string
  - username: string
  - avatar: string
  - online: boolean
  - lastSeen: number
  - connectedAt: number
```

---

# DEPLOYMENT CHECKLIST

## Before Deploying Feature:
- [ ] Feature works locally
- [ ] No console errors
- [ ] Syntax validated
- [ ] Mobile tested
- [ ] Multiplayer tested
- [ ] Firebase rules updated (if needed)
- [ ] Documentation updated
- [ ] Version number incremented

## After Deployment:
- [ ] Verify in production
- [ ] Monitor Firebase usage
- [ ] Check for errors in console
- [ ] Get user feedback
- [ ] Document any issues

---

# CONTACT / QUESTIONS

If any specification unclear or needs more detail:
1. Check v2.6.1 source code for current implementation
2. Check single-player 3.5.9 for reference AI
3. Refer to SYNTAX_ERROR_PREVENTION.md for coding practices
4. Ask user (Rob) for clarification

---

# PRIORITY ORDER RECOMMENDATION

1. **Feature 2** - Game cleanup (30 min, low risk)
2. **Feature 1** - Connected players (1-2 hrs, medium risk)
3. **Feature 3** - Mobile scrolling (30 min, low risk)
4. **Feature 4** - Button positioning (30 min, low risk)
5. **Feature 6** - Heuristics (2-4 hrs, high risk)
6. **Feature 5** - Monte Carlo (4-8 hrs, very high risk)

Do mobile features together, do AI features together.

---

**END OF SPECIFICATIONS**

Good luck with Claude Code! 🚀
