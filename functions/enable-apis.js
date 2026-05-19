// One-shot: enable APIs needed for Cloud Functions deploy using the SA key.
const { GoogleAuth } = require('google-auth-library');

const PROJECT_ID = 'fir-nbpt';
const APIS = [
  'cloudbilling.googleapis.com',
  'cloudbuild.googleapis.com',
  'cloudfunctions.googleapis.com',
  'artifactregistry.googleapis.com',
  'run.googleapis.com',
  'eventarc.googleapis.com',
  'pubsub.googleapis.com',
  'storage.googleapis.com',
  'firebaseextensions.googleapis.com',
];

async function main() {
  const auth = new GoogleAuth({
    scopes: ['https://www.googleapis.com/auth/cloud-platform'],
  });
  const client = await auth.getClient();
  for (const api of APIS) {
    const url = `https://serviceusage.googleapis.com/v1/projects/${PROJECT_ID}/services/${api}:enable`;
    try {
      const res = await client.request({ url, method: 'POST' });
      console.log(api, '->', res.status, res.data && res.data.name ? 'op:' + res.data.name : 'done');
    } catch (e) {
      console.log(api, 'FAIL', e.code || '', e.message);
      if (e.response && e.response.data) console.log('  body:', JSON.stringify(e.response.data));
    }
  }
}
main().catch(e => { console.error(e); process.exit(1); });
