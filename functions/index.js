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
const { defineSecret } = require('firebase-functions/params');
const admin = require('firebase-admin');
const crypto = require('crypto');
const { RtcTokenBuilder, RtcRole } = require('agora-token');

admin.initializeApp();

// Agora token mint secret — value lives in Secret Manager as AGORA_APP_CERT.
// Anyone with this can mint tokens for any channel/user, so it must never
// reach the client or git.
const AGORA_APP_CERT = defineSecret('AGORA_APP_CERT');
const AGORA_APP_ID = '5a005fca7bf0401c9df7fd6665a99c28';

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

// Mint an Agora RTC token bound to (channel, uid). The channel name and uid
// sanitisation MUST match the client's VoiceChat.join() in index.html exactly,
// otherwise the token won't verify when the client presents it to Agora.
//
// Verification policy: the caller must be a player in /games/{gameId}. That
// data is publicly readable, so this only narrows abuse to "must claim a real
// player slot in a real live game" — App Check (once enforced) will close
// the residual hole by attesting that the caller is a real app instance.
exports.getVoiceToken = onCall(
  { region: 'us-central1', secrets: [AGORA_APP_CERT] },
  async (req) => {
    const gameId = req.data && req.data.gameId;
    const uid = req.data && req.data.uid;
    if (!gameId || !uid) {
      throw new HttpsError('invalid-argument', 'gameId and uid required');
    }

    const playerSnap = await admin.database()
      .ref('games/' + gameId + '/players/' + uid).get();
    if (!playerSnap.exists()) {
      throw new HttpsError('permission-denied', 'Not a player in this game');
    }

    const channel = (String(gameId).replace(/^-+/, '').slice(0, 64)) || 'default';
    const cleanUid = String(uid).replace(/^-+/, '').slice(0, 64);
    const ttlSec = 60 * 60; // 1h — long enough for a full game, short enough to bound abuse
    const privilegeExpire = Math.floor(Date.now() / 1000) + ttlSec;

    const token = RtcTokenBuilder.buildTokenWithUserAccount(
      AGORA_APP_ID,
      AGORA_APP_CERT.value(),
      channel,
      cleanUid,
      RtcRole.PUBLISHER,
      ttlSec,
      privilegeExpire,
    );

    return { token, channel, uid: cleanUid, expiresAt: privilegeExpire * 1000 };
  },
);
