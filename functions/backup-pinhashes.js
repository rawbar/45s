// Snapshot every /users/{uid}/{username,pinHash} pair to a local JSON file.
// Run before stripping legacy hashes; restore-pinhashes.js reads this back.
const admin = require('firebase-admin');
const fs = require('fs');
const path = require('path');

admin.initializeApp({ databaseURL: 'https://fir-nbpt-default-rtdb.firebaseio.com' });

(async () => {
  const snap = await admin.database().ref('users').get();
  const users = snap.val() || {};
  const out = [];
  for (const uid of Object.keys(users)) {
    const u = users[uid] || {};
    if (!u.pinHash) continue;
    out.push({ uid, username: u.username || null, pinHash: u.pinHash });
  }
  const target = path.join(__dirname, 'pinhash-backup.json');
  fs.writeFileSync(target, JSON.stringify({
    takenAt: new Date().toISOString(),
    count: out.length,
    entries: out,
  }, null, 2));
  console.log('Backed up', out.length, 'pinHash entries to', target);
  process.exit(0);
})().catch(e => { console.error(e); process.exit(1); });
