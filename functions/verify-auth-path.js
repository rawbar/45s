// Verify the new server-side auth path is in use.
// 1) /auth/{user} populated for the active accounts
// 2) Recent verifyPin executions in Cloud Logging
const admin = require('firebase-admin');
const { GoogleAuth } = require('google-auth-library');
admin.initializeApp({ databaseURL: 'https://fir-nbpt-default-rtdb.firebaseio.com' });

const PROJECT_ID = 'fir-nbpt';

(async () => {
  // (1) Show /auth entries we expect
  const auth = await admin.database().ref('auth').get();
  const obj = auth.val() || {};
  const names = Object.keys(obj).sort();
  console.log(`/auth has ${names.length} entries.`);
  for (const n of names) {
    const e = obj[n] || {};
    console.log('  ', n, '->', e.uid, e.pinHash ? '(hash:' + e.pinHash.slice(0,6)+'…)' : '');
  }

  // (2) Pull last 30 minutes of verifyPin / registerPin function logs
  const gauth = new GoogleAuth({ scopes: ['https://www.googleapis.com/auth/logging.read'] });
  const client = await gauth.getClient();
  const since = new Date(Date.now() - 30*60*1000).toISOString();
  const filter = [
    `resource.type="cloud_run_revision"`,
    `(resource.labels.service_name="verifypin" OR resource.labels.service_name="registerpin")`,
    `timestamp>="${since}"`,
  ].join(' AND ');
  const res = await client.request({
    url: 'https://logging.googleapis.com/v2/entries:list',
    method: 'POST',
    data: { resourceNames: [`projects/${PROJECT_ID}`], filter, orderBy: 'timestamp desc', pageSize: 50 },
  });
  const entries = (res.data && res.data.entries) || [];
  console.log(`\nRecent function log entries (last 30m): ${entries.length}`);
  for (const e of entries) {
    const svc = e.resource && e.resource.labels && e.resource.labels.service_name;
    const sev = e.severity || 'DEFAULT';
    const text = e.textPayload || (e.httpRequest && (e.httpRequest.requestMethod + ' ' + e.httpRequest.status)) || '';
    console.log(' ', e.timestamp, svc, sev, text.slice(0, 140));
  }
  process.exit(0);
})().catch(e => { console.error(e); process.exit(1); });
