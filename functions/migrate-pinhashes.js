// One-shot migration: copy each user's {username, pinHash} from /users/{uid}
// to /auth/{usernameLower} = {uid, pinHash}, which is what verifyPin reads.
//
// Idempotent: skips entries that already have a pinHash at the destination.
// Run twice safely.

const admin = require('firebase-admin');

admin.initializeApp({
  databaseURL: 'https://fir-nbpt-default-rtdb.firebaseio.com',
});

(async () => {
  const usersSnap = await admin.database().ref('users').get();
  const users = usersSnap.val() || {};
  let total = 0, migrated = 0, skippedNoHash = 0, skippedExists = 0, collisions = 0;

  for (const uid of Object.keys(users)) {
    total++;
    const u = users[uid] || {};
    const username = u.username;
    const pinHash = u.pinHash;
    if (!username || !pinHash) { skippedNoHash++; continue; }
    const key = String(username).toLowerCase().trim();
    const dest = admin.database().ref('auth/' + key);
    const existing = (await dest.get()).val();
    if (existing && existing.pinHash) {
      if (existing.uid !== uid) {
        console.log('COLLISION', key, 'existing uid', existing.uid, 'vs', uid);
        collisions++;
      } else {
        skippedExists++;
      }
      continue;
    }
    await dest.set({ uid: String(uid), pinHash: String(pinHash) });
    migrated++;
    console.log('OK', key, '->', uid);
  }

  console.log(`\nTotal users: ${total}`);
  console.log(`Migrated:    ${migrated}`);
  console.log(`Already had: ${skippedExists}`);
  console.log(`No hash/un:  ${skippedNoHash}`);
  console.log(`Collisions:  ${collisions}`);
  process.exit(0);
})().catch(e => { console.error(e); process.exit(1); });
