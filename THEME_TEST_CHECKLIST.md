# 45s Theme Test Checklist

Run through this on a phone after implementing a new theme. Check every item before calling it done.
Each item is a regression that occurred during Irish Card Room development (v2.26–v2.27).

---

## Lobby

- [ ] Topbar: logo, title, version number all visible
- [ ] Version number tappable → opens release notes modal
- [ ] All 3 tabs present and tappable (Games / Leaderboard / Online)
- [ ] Game list scrolls; Create Game button visible WITHOUT scrolling
- [ ] Tabs stay fixed when list scrolls (do not scroll with content)
- [ ] Open game: shows seat count ("2 of 4 seated")
- [ ] Playing game: shows "In progress" + human player names below
- [ ] Finished game: shows player names + "Done" badge — NO "In progress" or "Finished" sub-text
- [ ] Leaderboard renders with rank/avatar/name
- [ ] Online strip shows players; ghost users (idle >5 min) cleaned up
- [ ] Avatar tap → Stats modal (correct themed design)
- [ ] Gear → Preferences modal (themed, contains theme tile selector)
- [ ] Profile Settings does NOT contain theme tiles (they live in Preferences only)

---

## Waiting Room

- [ ] Compass grid layout (N top, S bottom, W left, E right)
- [ ] Start Game button fully visible without scrolling on small phone screen
- [ ] Seat cards show avatar + username
- [ ] AI fills empty seats on Start

---

## Deal Animation (new round starts)

- [ ] Animation plays for ALL 4 players (not just me)
- [ ] Sequence: 3 cards to each player in deal order, then kitty 3-card center reveal, then 2 cards to each
- [ ] Cards fly FROM the dealer's compass direction
- [ ] 150ms stagger between cards — looks like cards being dealt, not instant pop
- [ ] Kitty (3 face-down cards) appears in center table AFTER first 12 cards
- [ ] Bid buttons are LOCKED during deal (4500ms window)
- [ ] NO bid flash animations appear while deal is still playing

---

## Bidding

- [ ] Bid buttons appear only after deal animation completes
- [ ] Bid flash fires at correct compass position for each player who bids
- [ ] Bid flash text format: "20♥" / "PASS" / "BAGGED"
- [ ] Bagged indicator shows in red

---

## Trump Select

- [ ] Diamond announce fires centered over the table circle (not offset)
- [ ] Diamond announce arrow points toward bid winner's compass seat
- [ ] Kitty flies toward the bid winner when trump is chosen
- [ ] Kitty disappears after flying (not left on table)

---

## Discard → Draw

- [ ] E/W player name and card area does NOT shift during discard
- [ ] My draw animation: cards slide in one at a time, 200ms apart
- [ ] All 3 opponents animate when they draw — cards slide from their direction
- [ ] Cards clearly arrive separately (not all simultaneously)
- [ ] Drawn card count (+N pill) shows correctly for all seats

---

## Playing Phase (most regressions happen here)

- [ ] E/W player names do NOT jump at any point during the round
- [ ] E/W stable at: deal complete, first bid, trump set, first card played, mid-round, last card played
- [ ] Last-trick strip appears after trick 1 completes
- [ ] Last-trick strip does NOT cause layout jump when it first appears
- [ ] No layout jump between tricks as strip updates
- [ ] Trick cards in center rail are absolutely positioned (don't push other content)
- [ ] Follow-suit toast appears when required

---

## ShowHandsModal (View Round button)

- [ ] All 4 players shown with name + avatar + bid badge
- [ ] North and South: mid-size cards, large center suit, corner suit HIDDEN
- [ ] East and West: small cards side-by-side, large center suit, corner suit HIDDEN
- [ ] All 10 E/W cards fit on screen without overflow
- [ ] Trick number badge on each card
- [ ] Led-trick card has brass border highlight
- [ ] Drawn cards: blue dot. Kitty cards: gold dot.
- [ ] Close button works

---

## Round End / Game Over

- [ ] Round-end modal is fully themed (no old green/white design)
- [ ] Game-over modal is fully themed
- [ ] Scores correct

---

## Stats / Badges Modal

- [ ] Bottom-sheet design (slides up, dark bg, brass border-top)
- [ ] Single scroll — NO tabs
- [ ] 12 stats in grid
- [ ] Badge circles 44px round, correct earned/locked styling
- [ ] Tapping a badge opens FLOATING CENTERED modal overlay — NOT inline expansion
- [ ] Close button works

---

## Preferences Modal

- [ ] Fully themed
- [ ] Theme tiles visible and switch themes
- [ ] House rules checkboxes themed (not default browser checkboxes)

---

## Leave Game Flow

- [ ] Exit button visible on game table screen
- [ ] Tapping exit shows THEMED confirm modal — NOT browser system dialog
- [ ] Cancel returns to game; Confirm returns to lobby

---

## Transitions (no flash of wrong UI)

- [ ] Start Game → game table: waiting room stays visible until table mounts (no flash of old green screen)
- [ ] No system dialogs appear anywhere (window.confirm, window.alert)
- [ ] Release notes auto-shows on first load after version update
