# Quick Reference - Claude Code Handoff

**Project:** 45s Multiplayer Card Game  
**Current Version:** v2.6.1  
**Baseline File:** `45s_v2.6.1_SETTINGS_MODAL.html`  
**Environment:** Firebase Realtime Database + React (in single HTML file)

---

## 📦 FILES TO PROVIDE TO CLAUDE CODE

1. **`45s_v2.6.1_SETTINGS_MODAL.html`** - Current working version
2. **`CLAUDE_CODE_FEATURE_SPECS.md`** - Detailed specifications (this file)
3. **`SYNTAX_ERROR_PREVENTION.md`** - Coding best practices
4. **`CLEAN_BACKLOG_V2.5.9.md`** - Full backlog context

---

## 🎯 QUICK START FOR CLAUDE CODE

### Initial Prompt Template:
```
I'm working on a 45s multiplayer card game. Current version is v2.6.1.

Please implement [FEATURE NAME] according to the attached specifications.

Key requirements:
- Read SYNTAX_ERROR_PREVENTION.md before making ANY changes
- Use str_replace tool instead of sed when possible
- Validate syntax after every change
- Test incrementally

The feature spec is in CLAUDE_CODE_FEATURE_SPECS.md under "FEATURE X: [NAME]".
```

---

## 📋 FEATURES TO IMPLEMENT (In Order)

### Easy Wins (Do First):
1. **Game Cleanup** - 30 min, low risk
2. **Mobile Scrolling** - 30 min, low risk  
3. **Button Positioning** - 30 min, low risk

### Medium (Do Second):
4. **Connected Players** - 1-2 hrs, medium risk

### Hard (Do Last):
5. **Heuristics AI** - 2-4 hrs, high risk
6. **Monte Carlo AI** - 4-8 hrs, very high risk

---

## 🔧 TECHNICAL STACK

- **Frontend:** React (using Babel in browser)
- **Database:** Firebase Realtime Database
- **Auth:** Custom PIN-based (bcryptjs hashing)
- **Hosting:** Single HTML file (no build process)
- **Line Endings:** CRLF (Windows-style)

---

## 📍 KEY FILE LOCATIONS

```
Line 67-93:    AVATARS array (24 fantasy icons)
Line 95-97:    getAvatarById function
Line 1813:     LoginScreen component
Line 2280:     LobbyScreen component
Line 2289:     Game cleanup logic (needs enhancement)
Line 2730:     GameListItem component
Line 3500+:    Game logic (where AI lives)
Line 5652:     GameScreen component (main game)
```

---

## ⚠️ CRITICAL WARNINGS

### DON'T DO THIS:
- ❌ Use sed with line numbers without viewing first
- ❌ Make multiple changes without validation
- ❌ Assume code structure without checking
- ❌ Leave stray lines or unclosed brackets
- ❌ Skip syntax validation

### DO THIS:
- ✅ View section with `view` tool first
- ✅ Use `str_replace` tool when possible
- ✅ Validate after every change
- ✅ Check for CRLF issues if str_replace fails
- ✅ Test one feature at a time

---

## 🧪 TESTING CHECKLIST

### After Each Feature:
- [ ] No console errors
- [ ] Syntax validates
- [ ] Feature works as specified
- [ ] No regression in other features
- [ ] Mobile responsive (if applicable)
- [ ] Multiplayer sync works (if applicable)

### Before Final Delivery:
- [ ] Full game playthrough works
- [ ] Firebase data clean
- [ ] Version number updated
- [ ] Changelog created
- [ ] User can test easily

---

## 🔥 FIREBASE STRUCTURE

### Existing Paths:
```
/users/{userId}
  - username, avatar, pinHash, createdAt

/lobby/games/{gameId}
  - name, status, creatorId, createdAt, lastActivity, players

/games/{gameId}
  - gameState, players, history, lastActivity
```

### To Add:
```
/presence/{userId}
  - userId, username, avatar, online, lastSeen, connectedAt
```

---

## 📊 VERSION HISTORY

- **v2.5.9** - Baseline from user
- **v2.6.0** - Added fantasy icons, fixed lobby button
- **v2.6.1** - Added settings modal (current)
- **v2.7.0+** - Your features!

---

## 💡 SAMPLE PROMPTS FOR CLAUDE CODE

### Feature 1 - Connected Players:
```
Please implement Feature 1 (Connected Players Display) from CLAUDE_CODE_FEATURE_SPECS.md.

Requirements:
1. Add Firebase presence tracking
2. Show online players in lobby with avatars
3. Real-time updates as players connect/disconnect
4. Clean up stale presence records

Follow SYNTAX_ERROR_PREVENTION.md practices.
Start by viewing LobbyScreen component around line 2280.
```

### Feature 2 - Game Cleanup:
```
Please implement Feature 2 (Game Cleanup) from CLAUDE_CODE_FEATURE_SPECS.md.

Requirements:
1. Enhance existing cleanup logic at line 2289
2. Remove games with missing/invalid timestamps
3. Add better error handling and logging
4. Validate timestamps on game creation

This is a simple enhancement to existing code.
```

---

## 🎓 LEARNING RESOURCES

### If Claude Code Needs Context:
- 45s card game rules: It's a bidding/trick-taking game
- Firebase docs: https://firebase.google.com/docs/database
- React hooks: useState, useEffect for state management
- The game uses seats 0-3 (North, East, South, West)
- Teams are 0 (N/S) vs 1 (E/W)

---

## 🚨 EMERGENCY ROLLBACK

If feature breaks everything:
1. Revert to v2.6.1 baseline
2. Document what went wrong
3. Ask user (Rob) for guidance
4. Try smaller incremental approach

---

## 📞 SUCCESS CRITERIA

### Each Feature Complete When:
1. ✅ Works as specified
2. ✅ No console errors
3. ✅ Passes all test cases
4. ✅ No regression in other features
5. ✅ Documentation updated
6. ✅ User can test it

---

## 🎯 FINAL DELIVERABLES

For each feature, provide:
1. Updated HTML file (e.g., `45s_v2.7.0_FEATURE_NAME.html`)
2. Changelog (e.g., `V2_7_0_CHANGELOG.md`)
3. Test results summary
4. Any known issues/limitations

---

## 💬 QUESTIONS?

If anything unclear:
1. Check the detailed specs in CLAUDE_CODE_FEATURE_SPECS.md
2. Check current implementation in v2.6.1
3. Ask user (Rob) for clarification
4. Start with easier features to build confidence

---

**Good luck! The code is well-structured and the specs are detailed. You've got this! 🚀**
