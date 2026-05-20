// Restore pinHash fields from pinhash-backup.json back to /users/{uid}/pinHash.
// Use only if Step 2 (strip) needs to be reversed.
const admin = require('firebase-admin');
const fs = require('fs');
const path = require('path');

admin.initializeApp({ databaseURL: 'https://fir-nbpt-default-rtdb.firebaseio.com' });

(async () => {
  const file = path.join(__dirname, 'pinhash-backup.json');
  const data = JSON.parse(fs.readFileSync(file, 'utf8'));
  console.log('Restoring', data.entries.length, 'pinHash entries from', file);
  for (const e of data.entries) {
    await admin.database().ref('users/' + e.uid + '/pinHash').set(e.pinHash);
    console.log('  set users/' + e.uid + '/pinHash');
  }
  console.log('Done.');
  process.exit(0);
})().catch(e => { console.error(e); process.exit(1); });
