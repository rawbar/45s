// For each colliding username, pick the uid with the most gamesPlayed
// (tiebreak: gamesWon, then uid asc) and rewrite /auth/{username} to that uid.
// pinHashes are identical across collisions so any of them verifies the PIN.

const admin = require('firebase-admin');
admin.initializeApp({ databaseURL: 'https://fir-nbpt-default-rtdb.firebaseio.com' });

(async () => {
  const usersSnap = await admin.database().ref('users').get();
  const users = usersSnap.val() || {};
  const byName = {};
  for (const uid of Object.keys(users)) {
    const u = users[uid] || {};
    const name = (u.username || '').toLowerCase().trim();
    if (!name || !u.pinHash) continue;
    (byName[name] = byName[name] || []).push({ uid, ...u });
  }
  for (const name of Object.keys(byName)) {
    const candidates = byName[name];
    if (candidates.length < 2) continue;
    // Verify all share the same pinHash; if not, refuse to auto-resolve.
    const hashes = new Set(candidates.map(c => c.pinHash));
    if (hashes.size > 1) {
      console.log('SKIP', name, '— differing pinHashes, manual review needed');
      continue;
    }
    const best = [...candidates].sort((a, b) => {
      const ag = (a.stats && a.stats.gamesPlayed) || 0;
      const bg = (b.stats && b.stats.gamesPlayed) || 0;
      if (ag !== bg) return bg - ag;
      const aw = (a.stats && a.stats.gamesWon) || 0;
      const bw = (b.stats && b.stats.gamesWon) || 0;
      if (aw !== bw) return bw - aw;
      return a.uid < b.uid ? -1 : 1;
    })[0];
    const dest = admin.database().ref('auth/' + name);
    const cur = (await dest.get()).val() || {};
    if (cur.uid === best.uid) {
      console.log('OK', name, '-> already', best.uid);
      continue;
    }
    await dest.set({ uid: best.uid, pinHash: best.pinHash });
    console.log('FIXED', name, ':', cur.uid, '->', best.uid);
  }
  process.exit(0);
})();
