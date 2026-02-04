# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

45s is a multiplayer card game (traditional Irish trick-taking game) implemented as a single-file React application with Firebase Realtime Database for multiplayer synchronization.

## Deployment

**IMPORTANT:** Unless otherwise specified, all new builds must be deployed to `index.html` in the main repo. This is the file served by GitHub Pages. The working file may have a versioned name (e.g., `45s_v2.7.0.html`) but must be copied to `index.html` before pushing.

## Version Reference

- **v3.5.9** = Gold standard single-player version (reference for UI and AI strategy)
- **v2.14.1** = Current multiplayer version

Filenames vary but version number is authoritative. Any file labeled with the same version is identical.

## Gold Standard: v3.5.9

The single-player v3.5.9 is the **GOLD REFERENCE STANDARD** for:
- All UI standards (documented in `45s_UI_DESIGN_SPECIFICATION.md`)
- Strategy logic (Monte Carlo AI, heuristics, bidding)

**When fixing bugs or discrepancies in multiplayer, always compare against v3.5.9.**

## Current State: v2.14.1

- Game table layout is correct and matches design spec
- Core gameplay works (bidding, trump, discarding, playing, scoring)
- User accounts with PIN authentication
- 24 fantasy-themed avatars
- Settings modal for profile changes
- Firebase real-time sync working

**Known issue:** AI code exists in multiplayer but is **NOT BEING UTILIZED** correctly. The `GameSimulator` class and related functions are present but not wired up the same way as v3.5.9. Future work: compare v3.5.9 implementation and update multiplayer to use AI properly.

## Feature Backlog (Priority Order)

From `handoff/CLAUDE_CODE_FEATURE_SPECS.md`:

| # | Feature | Time | Risk | Status |
|---|---------|------|------|--------|
| 2 | Game Cleanup (invalid timestamps) | 30 min | Low | ✅ Done (v2.7.0) |
| 3 | Lobby Mobile Scrolling | 30 min | Low | ✅ Done (v2.8.x) |
| 4 | Button Positioning (Mobile) | 30 min | Low | ✅ Done (v2.8.x) |
| 8 | Clear trump display at round start | 15 min | Low | ✅ Done (v2.11.0) |
| 13 | Hide bid display until player has bid or passed | 15 min | Low | ✅ Done (v2.11.0) |
| 14 | Bagging logic (dealer auto-bid 15 + red BAGGED indicator) | 1-2 hrs | Medium | Done (v2.15.0) |
| 1 | Connected Players Display | 1-2 hrs | Medium | ✅ Done (v2.10.1) |
| 7 | Round-by-Round Score Modal | 1-2 hrs | Medium | Not done |
| 9 | Create AI Design Specification Doc | 1 hr | Low | Not done |
| 10 | Utilize getHighestRemainingTrump() strategically | 1-2 hrs | Medium | Not done |
| 11 | Utilize knownOutOfTrump for strategic decisions | 2-3 hrs | Medium | Not done |
| 12 | Utilize bidderLostTrick for strategy adjustments | 1-2 hrs | Medium | Not done |
| 6 | Heuristics AI Strategy | 2-4 hrs | High | ✅ Done (v2.9.0) |
| 5 | Monte Carlo AI (wire up properly) | 4-8 hrs | Very High | ✅ Done (v2.9.0) |
| 15 | WaitingRoom: West/East positions reversed | 15 min | Low | ✅ Done (v2.11.0) |
| 16 | Remove "(you)" text from online players (blue bg is sufficient) | 5 min | Low | ✅ Done (v2.11.0) |
| 17 | Move version number below "45s" title (smaller font, not overlapping) | 5 min | Low | ✅ Done (v2.11.0) |
| 18 | Player stats tracking (games played, won, lost, win%, streak) | 2-3 hrs | Medium | ✅ Done (v2.11.0) |
| 19 | Leaderboard - top 10 by win% (min 5 games to qualify) | 1-2 hrs | Medium | ✅ Done (v2.12.0) |

**Recommended approach:** Start with low-risk features to build confidence, save AI work for last.

## Tech Stack

- **Single HTML file** with embedded JSX (transpiled via Babel in-browser)
- **React 18** (loaded from CDN, production build)
- **Firebase Realtime Database** for multiplayer state sync
- **Inline styles** (no CSS framework) - must follow design spec exactly

## Architecture

### Application State Flow
```
LoginScreen → LobbyScreen → WaitingRoom → GameWrapper → MultiplayerGameTable
```

### Key Components

| Component | Purpose |
|-----------|---------|
| `MultiplayerApp` | Root component, manages app state transitions |
| `LoginScreen` | User auth with username/PIN (SHA-256 hashed) |
| `LobbyScreen` | Create/join games, view game list (~line 2280) |
| `WaitingRoom` | Pre-game lobby, seat selection, AI filling |
| `GameWrapper` | Firebase sync, heartbeat, disconnect detection |
| `MultiplayerGameTable` | Main game UI and logic |
| `GameSimulator` | Monte Carlo AI class (exists but not utilized properly) |

### Player/Seat System
```
Position 0 = North  (Team 0)
Position 1 = East   (Team 1)
Position 2 = South  (Team 0) - Partners with North
Position 3 = West   (Team 1) - Partners with East
```
- Teams: positions 0,2 vs 1,3 (partners are 2 apart)
- Play order: North → East → South → West → North

### Game Phases
`dealing` → `bidding` → `trump-select` → `discarding` → `playing` → `trick-end` → `round-end` → `game-over`

## Critical Files

| File | Purpose |
|------|---------|
| v3.5.9 HTML | **GOLD STANDARD** - reference for UI and strategy |
| v2.6.1 HTML | Current multiplayer version |
| `45s_UI_DESIGN_SPECIFICATION.md` | **Authoritative UI spec** - all styling must match |
| `AI_BIDDING_SPECIFICATIONS.md` | **Bidding thresholds** - 70%+ success from 1.1M simulation tests |
| `AI_DESPERATION_BIDDING.md` | **Desperation strategy** - when opponent is about to win |
| `handoff/CLAUDE_CODE_FEATURE_SPECS.md` | Detailed specs for pending features |
| `handoff/V2_6_1_CURRENT_STATE.md` | What's working, what's missing |
| `SYNTAX_ERROR_PREVENTION.md` | Workflow for safe code edits |

## Development Guidelines

### UI Changes
**Always reference `45s_UI_DESIGN_SPECIFICATION.md`** before making any UI changes. Key locked values:
- Circle: 150px x 150px, cards 4px from edge
- Card sizes: small 30x42px, regular 48x68px
- Colors: Gold #d4af37, Green #4caf50, Red #f44336, Blue #2196f3
- Version format: `vX.Y.Z` (max 8 characters)

### Code Editing Safety
Per `SYNTAX_ERROR_PREVENTION.md`:
1. View exact section before editing
2. Use atomic string replacements when possible
3. Validate syntax after every change (bracket/brace balance)
4. Check for stray lines after multi-line edits

### Firebase Data Handling
Firebase can corrupt arrays into objects with numeric keys. The `FirebaseAPI.ensureArray()` helper handles this:
```javascript
// Always use when reading hands from Firebase
data.gameState.hands = FirebaseAPI.ensureArray(data.gameState.hands, [[], [], [], []]);
```

## Card Game Logic

**Trump ranking (highest to lowest):**
1. 5 of trump (rank 102)
2. Jack of trump (rank 101)
3. Ace of Hearts (always trump, rank 100)
4. Ace of trump (rank 99)
5. K, Q of trump (97-98)
6. Number cards (80+, order varies by suit color)

**Key functions:**
- `getTrumpRank(card, trumpSuit)` - Get trump ranking
- `getPlayableCards(hand, trumpSuit, ledCard, ledSuit)` - Legal moves
- `determineTrickWinner(trick, trumpSuit, startPlayer)` - Trick evaluation

## AI Strategy (Needs Work)

**Problem:** Multiplayer v2.6.1 has AI code but it's not being utilized like v3.5.9.

**To fix AI:**
1. Study how v3.5.9 calls `GameSimulator` and related functions
2. Find where multiplayer AI makes decisions
3. Wire up the same logic so AI plays strategically

**Key AI functions (exist but need proper integration):**
- `GameSimulator.chooseBestCard()` - Monte Carlo with 5 rollouts
- `chooseCardSimple()` - Heuristic card selection
- `decideBid()` - Bidding strategy
- `decideDiscard()` - Discard selection

## Testing

Open the HTML file directly in a browser. No build step required.

Debug mode: `const DEBUG = true;` at top of script.

Console log prefixes:
- `🔐 AUTH:` - Authentication
- `🎮 GAME:` - Game state
- `⏱️ TIMER:` - Timing
- `🤖 AI:` - AI decisions
- `📡 FIREBASE DEBUG:` - Firebase operations

## Version Numbering

Format: `vX.Y.Z` (semantic versioning)
- Major: Breaking changes
- Minor: New features
- Patch: Bug fixes

Current: `const VERSION = '2.17.6';`

**IMPORTANT:** Always update the version number upon ANY code change. This is mandatory.

**IMPORTANT:** When releasing a new version, ALWAYS update the `versionHistory` array in the `WhatsNewModal` component with the new version and changelog entry. This ensures users see what changed.
