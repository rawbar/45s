// Remove the legacy pinHash field from every /users/{uid} record.
// Run AFTER backup-pinhashes.js (pinhash-backup.json must exist).
// Restore via restore-pinhashes.js if anything breaks.
const admin = require('firebase-admin');
const fs = require('fs');
const path = require('path');

admin.initializeApp({ databaseURL: 'https://fir-nbpt-default-rtdb.firebaseio.com' });

(async () => {
  const file = path.join(__dirname, 'pinhash-backup.json');
  if (!fs.existsSync(file)) {
    console.error('Refusing to strip — no backup at', file);
    process.exit(2);
  }
  const backup = JSON.parse(fs.readFileSync(file, 'utf8'));
  console.log('Backup present:', backup.count, 'entries, taken', backup.takenAt);

  const snap = await admin.database().ref('users').get();
  const users = snap.val() || {};
  let stripped = 0, missing = 0;
  for (const uid of Object.keys(users)) {
    const u = users[uid] || {};
    if (!u.pinHash) { missing++; continue; }
    await admin.database().ref('users/' + uid + '/pinHash').remove();
    stripped++;
    console.log('  stripped users/' + uid);
  }
  console.log('Stripped:', stripped, ' (no-pinHash already:', missing + ')');
  process.exit(0);
})().catch(e => { console.error(e); process.exit(1); });
