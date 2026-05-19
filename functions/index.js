// 45s server-side PIN auth.
//
// pinHash lives ONLY under /auth/{usernameLower} which is .read:false /
// .write:false in RTDB rules — clients can never read or write it. These
// callables (running with Admin privileges) are the only way to verify or
// set a PIN, so the hash is never exposed to brute force off a public read.
//
// hashPin MUST stay byte-identical to the client's hashPin() in index.html:
//   SHA-256( username.toLowerCase().trim() + pin )  (hex)
// so already-migrated hashes verify unchanged (no user PIN reset needed).

const { onCall, HttpsError } = require('firebase-functions/v2/https');
const admin = require('firebase-admin');
const crypto = require('crypto');

admin.initializeApp();

function hashPin(username, pin) {
  return crypto
    .createHash('sha256')
    .update(String(username).toLowerCase().trim() + String(pin), 'utf8')
    .digest('hex');
}

const MAX_FAILS = 8;          // failures allowed within the window
const WINDOW_MS = 10 * 60000; // 10 min sliding window
const LOCK_MS = 10 * 60000;   // lockout duration after too many fails

// Online brute-force throttle (server-only node /authThrottle/{u}).
async function checkThrottle(u) {
  const ref = admin.database().ref('authThrottle/' + u);
  const rec = (await ref.get()).val() || {};
  const now = Date.now();
  if (rec.lockedUntil && rec.lockedUntil > now) {
    throw new HttpsError('resource-exhausted',
      'Too many attempts. Try again later.');
  }
  return { ref, rec, now };
}

async function recordFail(ref, rec, now) {
  let fails = (rec.fails || 0) + 1;
  let firstFailAt = rec.firstFailAt || now;
  if (now - firstFailAt > WINDOW_MS) { fails = 1; firstFailAt = now; }
  const upd = { fails, firstFailAt };
  if (fails >= MAX_FAILS) {
    upd.lockedUntil = now + LOCK_MS;
    upd.fails = 0;
    upd.firstFailAt = now;
  }
  await ref.set(upd);
}

exports.verifyPin = onCall({ region: 'us-central1' }, async (req) => {
  const username = req.data && req.data.username;
  const pin = req.data && req.data.pin;
  if (!username || pin === undefined || pin === null || pin === '') {
    throw new HttpsError('invalid-argument', 'username and pin required');
  }
  const u = String(username).toLowerCase().trim();
  const { ref, rec, now } = await checkThrottle(u);

  const snap = await admin.database().ref('auth/' + u + '/pinHash').get();
  const stored = snap.val();
  if (!stored) {
    await recordFail(ref, rec, now);
    throw new HttpsError('not-found', 'Invalid username or PIN.');
  }
  if (hashPin(username, pin) !== stored) {
    await recordFail(ref, rec, now);
    throw new HttpsError('permission-denied', 'Invalid username or PIN.');
  }
  await ref.remove(); // success clears the throttle
  const uidSnap = await admin.database().ref('auth/' + u + '/uid').get();
  return { ok: true, uid: uidSnap.val() || null };
});

// Account creation writes the PIN hash here (write-once: cannot overwrite
// an existing account's PIN, so a username cannot be hijacked).
exports.registerPin = onCall({ region: 'us-central1' }, async (req) => {
  const username = req.data && req.data.username;
  const pin = req.data && req.data.pin;
  const uid = req.data && req.data.uid;
  if (!username || pin === undefined || pin === null || pin === '' || !uid) {
    throw new HttpsError('invalid-argument', 'username, pin, uid required');
  }
  const u = String(username).toLowerCase().trim();
  const ref = admin.database().ref('auth/' + u);
  const existing = (await ref.get()).val();
  if (existing && existing.pinHash) {
    throw new HttpsError('already-exists', 'That username is taken.');
  }
  await ref.set({ uid: String(uid), pinHash: hashPin(username, pin) });
  return { ok: true };
});
