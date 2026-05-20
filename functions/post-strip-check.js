// Confirm /users no longer holds any pinHash, and /auth still does.
const admin = require('firebase-admin');
admin.initializeApp({ databaseURL: 'https://fir-nbpt-default-rtdb.firebaseio.com' });

(async () => {
  const usersSnap = await admin.database().ref('users').get();
  const users = usersSnap.val() || {};
  const stillHasHash = Object.entries(users).filter(([, u]) => u && u.pinHash);
  console.log('/users count:', Object.keys(users).length,
              '— with pinHash:', stillHasHash.length);
  if (stillHasHash.length) {
    for (const [uid] of stillHasHash) console.log('  LEAK', uid);
  }
  const authSnap = await admin.database().ref('auth').get();
  const auth = authSnap.val() || {};
  console.log('/auth count:', Object.keys(auth).length,
              '— missing pinHash:', Object.entries(auth).filter(([, e]) => !e || !e.pinHash).length);
  process.exit(0);
})();
