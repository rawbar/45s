// Inspect the colliding users: which uid has stats / recent activity?
const admin = require('firebase-admin');
admin.initializeApp({ databaseURL: 'https://fir-nbpt-default-rtdb.firebaseio.com' });

const colliding = ['danfay', 'jack2112', 'nnvb220'];

(async () => {
  const usersSnap = await admin.database().ref('users').get();
  const users = usersSnap.val() || {};
  const byName = {};
  for (const uid of Object.keys(users)) {
    const u = users[uid] || {};
    const name = (u.username || '').toLowerCase().trim();
    if (!byName[name]) byName[name] = [];
    byName[name].push({ uid, ...u });
  }
  for (const n of colliding) {
    console.log('\n=== ' + n + ' ===');
    for (const u of byName[n] || []) {
      const stats = u.stats || {};
      console.log(u.uid, 'games:', stats.gamesPlayed || 0,
        'won:', stats.gamesWon || 0,
        'avatar:', u.avatar,
        'hash:', (u.pinHash || '').slice(0, 8) + '...');
    }
  }
  process.exit(0);
})();
