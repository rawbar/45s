# Theming Checklist — 45s

Tracks the full-game theming job. Irish Card Room first, Cyberpunk second.

Status legend: ⬜ Not started · 🎨 Mockup ready · ✅ Implemented · 🔒 Deferred

---

## Irish Card Room Theme

### Full-Page Screens
| # | Screen | Line | Irish Mockup | Irish Impl | Cyberpunk Mockup | Cyberpunk Impl | Notes |
|---|--------|------|:---:|:---:|:---:|:---:|-------|
| 1 | LoginScreen | ~4485 | ⬜ | ⬜ | 🔒 | 🔒 | Username/PIN auth, avatar |
| 2 | LobbyScreen | ~5060 | ⬜ | ⬜ | 🔒 | 🔒 | Game list, nav tabs |
| 3 | WaitingRoom | ~7311 | ⬜ | ⬜ | 🔒 | 🔒 | Seat selection, ready |
| 4 | MultiplayerGameTable | ~8565 | ✅ | ✅ | ✅ | ✅ | Cards + table done (v2.24+) |

### Modals / Dialogs
| # | Modal | Line | Irish Mockup | Irish Impl | Cyberpunk Mockup | Cyberpunk Impl | Notes |
|---|-------|------|:---:|:---:|:---:|:---:|-------|
| 5 | WhatsNewModal | ~3782 | ⬜ | ⬜ | 🔒 | 🔒 | Version history |
| 6 | HelpModal | ~3941 | ⬜ | ⬜ | 🔒 | 🔒 | Info & help |
| 7 | RulesModal | ~4041 | ⬜ | ⬜ | 🔒 | 🔒 | Tutorial + rules |
| 8 | ShowHandsModal | ~4335 | ⬜ | ⬜ | 🔒 | 🔒 | All player hands |
| 9 | House Rules Toast | ~11161 | ⬜ | ⬜ | 🔒 | 🔒 | In-game notification |

### Lobby Overlays
| # | Overlay | State var | Irish Mockup | Irish Impl | Cyberpunk Mockup | Cyberpunk Impl | Notes |
|---|---------|-----------|:---:|:---:|:---:|:---:|-------|
| 10 | Create Game Dialog | showCreateGame | ⬜ | ⬜ | 🔒 | 🔒 | |
| 11 | Game Options Panel | showGameOptions | ⬜ | ⬜ | 🔒 | 🔒 | House rules, speed |
| 12 | Settings Modal | showSettings | ⬜ | ⬜ | 🔒 | 🔒 | Profile settings |
| 13 | Avatar Picker | showAvatarPicker | ⬜ | ⬜ | 🔒 | 🔒 | 24 avatar grid |
| 14 | Theme Preview | showThemePreview | ⬜ | ⬜ | 🔒 | 🔒 | Full-screen preview |
| 15 | Player Stats Modal | showStatsModal | ⬜ | ⬜ | 🔒 | 🔒 | Games/wins/streak |
| 16 | Leaderboard Modal | showLeaderboard | ⬜ | ⬜ | 🔒 | 🔒 | Top 10 by win% |
| 17 | Preferences Modal | showPreferences | ⬜ | ⬜ | 🔒 | 🔒 | Speed, house rules, themes |

---

## Recommended Mockup Order (Irish Card Room)

1. **LoginScreen** — first impression, sets the tone for the whole design
2. **LobbyScreen** — most complex, most UI elements
3. **WaitingRoom** — simpler, but still needs wood/felt treatment
4. **Lobby Overlays (10–17)** — can be batched in one or two mockup sessions
5. **In-game Modals (5–9)** — mostly text content, consistent treatment

---

## Session Log

| Date | What was done | Version |
|------|--------------|---------|
| 2026-04-18 | Game table (cards + table surface) — Irish + Cyberpunk | v2.25.x |
| 2026-04-18 | Theme picker UI, unlock system, fan layout (5–8 cards) | v2.25.x |
| 2026-04-18 | Created this checklist + THEMING_IMPLEMENTATION_GUIDE.md | — |
