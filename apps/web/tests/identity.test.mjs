import test from 'node:test';
import assert from 'node:assert/strict';
import { gridLinkPayload, joinGrid, linkQrPayload, normalizeServer, parseGridLink, redeemLinkCode, signInWithGridLink, webSessionStore } from '../src/identity.ts';

function fakeClient(server, token = '') {
  const calls = [];
  return {
    calls, server, token,
    async request(path, body, method) {
      calls.push({ path, body, method });
      return { token: 'new-token', session_id: 's1', user: { id: 'u1', name: 'Guest 4F2K' }, balance: 93 };
    },
  };
}

test('invite and link payloads round-trip through the QR text', () => {
  for (const link of [
    { kind: 'join', server: 'https://grid.example.com', code: 'pocketgrid demo&x=1' },
    { kind: 'link', server: 'http://192.168.1.20:8787', code: 'ABCD2345XY' },
  ]) assert.deepEqual(parseGridLink(gridLinkPayload(link)), link);
});

test('link codes are normalized and checked against the alphabet', () => {
  assert.equal(parseGridLink('gipu://link?grid=https%3A%2F%2Fg.example&code=abcd-2345-xy').code, 'ABCD2345XY');
  assert.equal(parseGridLink('gipu://link?grid=https%3A%2F%2Fg.example&code=ABCD2345X0'), null);
  assert.equal(parseGridLink('gipu://link?grid=https%3A%2F%2Fg.example&code=ABC'), null);
});

test('foreign schemes, unknown actions and bad grid addresses are rejected', () => {
  for (const text of [
    'https://join?grid=https%3A%2F%2Fg.example&code=x',
    'gipu://pay?grid=https%3A%2F%2Fg.example&code=x',
    'gipu://join?grid=javascript%3Aalert(1)&code=x',
    'gipu://join?grid=https%3A%2F%2Fg.example%2Fpath&code=x',
    'gipu://join?code=x',
    'gipu://join?grid=https%3A%2F%2Fg.example',
    'not a url',
  ]) assert.equal(parseGridLink(text), null, text);
});

test('a same-origin session builds its link QR from the page origin', () => {
  const payload = linkQrPayload('', { code: 'ABCD2345XY', expires_at: 0 }, 'https://grid.example.com');
  assert.deepEqual(parseGridLink(payload), { kind: 'link', server: 'https://grid.example.com', code: 'ABCD2345XY' });
  assert.throws(() => linkQrPayload('', { code: 'ABCD2345XY', expires_at: 0 }));
});

test('server addresses keep the existing http(s) rule', () => {
  assert.equal(normalizeServer(' https://g.example/ '), 'https://g.example');
  assert.equal(normalizeServer(''), '');
  assert.throws(() => normalizeServer('g.example'));
});

test('sign-in requests never carry an existing session token', async () => {
  await assert.rejects(joinGrid(fakeClient('https://g.example', 'old-token'), 'code'));
  await assert.rejects(redeemLinkCode(fakeClient('https://g.example', 'old-token'), 'ABCD2345XY'));
});

test('a link QR redeems against its own grid and keeps the account identity', async () => {
  const client = fakeClient('https://g.example');
  const session = await signInWithGridLink(client, { kind: 'link', server: 'https://g.example', code: 'ABCD2345XY' }, 'Pixel 8');
  assert.deepEqual(client.calls, [{ path: '/sessions/link', body: { code: 'ABCD2345XY', client_name: 'Pixel 8' }, method: undefined }]);
  assert.deepEqual(session, { token: 'new-token', name: 'Guest 4F2K', server: 'https://g.example', userId: 'u1' });
  assert.throws(() => signInWithGridLink(fakeClient('https://other.example'), { kind: 'join', server: 'https://g.example', code: 'x' }));
});

test('joining without a name lets the server assign one', async () => {
  const client = fakeClient('https://g.example');
  await joinGrid(client, 'pocketgrid-demo', '  ');
  assert.deepEqual(client.calls[0].body, { join_code: 'pocketgrid-demo' });
});

test('the web session store ignores corrupt values', async () => {
  const data = new Map();
  const storage = { getItem: key => data.get(key) ?? null, setItem: (key, value) => data.set(key, value), removeItem: key => data.delete(key) };
  const store = webSessionStore(storage);
  assert.equal(await store.load(), null);
  await store.save({ token: 't', name: 'n', server: '' });
  assert.deepEqual(await store.load(), { token: 't', name: 'n', server: '' });
  data.set('pocketgrid.session.v1', '{"token":1}');
  assert.equal(await store.load(), null);
  await store.clear();
  assert.equal(await store.load(), null);
});


test('grid addresses reject embedded credentials and invalid origins', () => {
  for (const value of ['https://user:secret@grid.example', 'https://grid.example:bad', 'https://\\other.example', 'https://grid.example/path']) {
    assert.throws(() => normalizeServer(value));
    assert.equal(parseGridLink(`gipu://join?grid=${encodeURIComponent(value)}&code=demo`), null);
  }
});
