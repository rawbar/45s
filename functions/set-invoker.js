// Add allUsers as roles/run.invoker on the two Cloud Run services backing
// our onCall functions. Web clients can't call them without this.
const { GoogleAuth } = require('google-auth-library');

const PROJECT_ID = 'fir-nbpt';
const REGION = 'us-central1';
const SERVICES = ['verifypin', 'registerpin'];

async function main() {
  const auth = new GoogleAuth({
    scopes: ['https://www.googleapis.com/auth/cloud-platform'],
  });
  const client = await auth.getClient();
  for (const svc of SERVICES) {
    const base = `https://run.googleapis.com/v2/projects/${PROJECT_ID}/locations/${REGION}/services/${svc}`;
    try {
      const cur = await client.request({ url: base + ':getIamPolicy' });
      const policy = cur.data || {};
      const bindings = policy.bindings || [];
      const invoker = bindings.find(b => b.role === 'roles/run.invoker');
      if (invoker) {
        if (!invoker.members.includes('allUsers')) invoker.members.push('allUsers');
      } else {
        bindings.push({ role: 'roles/run.invoker', members: ['allUsers'] });
      }
      policy.bindings = bindings;
      const upd = await client.request({
        url: base + ':setIamPolicy',
        method: 'POST',
        data: { policy },
      });
      console.log(svc, '->', upd.status, 'OK');
    } catch (e) {
      console.log(svc, 'FAIL', e.code || '', e.message);
      if (e.response && e.response.data) console.log('  body:', JSON.stringify(e.response.data));
    }
  }
}
main().catch(e => { console.error(e); process.exit(1); });
