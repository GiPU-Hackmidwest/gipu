import test from 'node:test';
import assert from 'node:assert/strict';
import { CameraPermissionError, listenForGridLinks, scanGridLink, secureSessionStore, secureStorage } from '../src/android.ts';

function memory() {
  const data = new Map();
  return { data, getItem: key => data.get(key) ?? null, setItem: (key, value) => data.set(key, String(value)), removeItem: key => data.delete(key) };
}

function fakeSecure() {
  const data = new Map();
  return { data, get: async key => data.get(key) ?? null, set: async (key, value) => { data.set(key, value); }, delete: async key => { data.delete(key); } };
}

const session = { token: 't', name: 'Guest', server: 'https://g.example', userId: 'u1' };
const invite = 'gipu://join?grid=https%3A%2F%2Fg.example&code=secret-join';
const link = 'gipu://link?grid=https%3A%2F%2Fg.example&code=ABCD2345XY';

test('secure storage maps to the Kotlin plugin commands', async () => {
  const calls = [];
  const store = secureStorage(async (command, args) => { calls.push([command, args]); return { value: '', found: false }; });
  assert.equal(await store.get('k'), null);
  await store.set('k', 'v');
  await store.delete('k');
  assert.deepEqual(calls.map(c => c[0]), ['plugin:secure-storage|get_secret', 'plugin:secure-storage|set_secret', 'plugin:secure-storage|delete_secret']);
  assert.deepEqual(calls[1][1], { key: 'k', value: 'v' });
});

test('an earlier localStorage session moves into secure storage once', async () => {
  const secure = fakeSecure(), legacy = memory();
  legacy.setItem('pocketgrid.session.v1', JSON.stringify(session));
  const store = secureSessionStore(secure, legacy);
  assert.deepEqual(await store.load(), session);
  assert.equal(legacy.getItem('pocketgrid.session.v1'), null);
  assert.deepEqual(JSON.parse(secure.data.get('pocketgrid.session.v1')), session);
  await store.clear();
  assert.equal(await store.load(), null);
});

test('saving never leaves a plaintext copy behind', async () => {
  const secure = fakeSecure(), legacy = memory();
  legacy.setItem('pocketgrid.session.v1', JSON.stringify({ ...session, token: 'old' }));
  await secureSessionStore(secure, legacy).save(session);
  assert.equal(legacy.data.size, 0);
});

test('grid links are delivered once across both channels and reloads, without storing codes', async () => {
  const seen = memory(), received = [];
  let push;
  const api = { onOpenUrl: async handler => { push = handler; return () => {}; }, getCurrent: async () => [invite] };
  await listenForGridLinks(api, value => received.push(value), seen);
  push([invite, link, 'https://example.com', 'gipu://pay?x=1']);
  await listenForGridLinks(api, value => received.push(value), seen); // A reload sees the launch URL again.
  assert.deepEqual(received.map(value => value.kind), ['join', 'link']);
  assert.ok(![...seen.data.values()].join().includes('secret-join'));
});

function scanner({ permission = 'granted', request = 'granted', result, error } = {}) {
  const calls = [];
  return {
    calls,
    checkPermissions: async () => permission,
    requestPermissions: async () => { calls.push('request'); return request; },
    scan: async options => { calls.push(options); if (error) throw error; return { content: result }; },
    cancel: async () => { calls.push('cancel'); },
  };
}

function overlay() {
  const view = { events: [], show: onCancel => { view.events.push('show'); view.cancel = onCancel; }, hide: () => view.events.push('hide') };
  return view;
}

test('a scan asks for the camera first and returns the parsed link', async () => {
  const api = scanner({ permission: 'prompt', result: link }), view = overlay();
  assert.deepEqual(await scanGridLink(api, 'QR_CODE', view), { kind: 'link', server: 'https://g.example', code: 'ABCD2345XY' });
  assert.deepEqual(api.calls, ['request', { windowed: true, formats: ['QR_CODE'] }]);
  assert.deepEqual(view.events, ['show', 'hide']);
});

test('denied camera access, cancellation and foreign codes are reported distinctly', async () => {
  await assert.rejects(scanGridLink(scanner({ permission: 'denied', request: 'denied' }), 'QR_CODE', overlay()), CameraPermissionError);
  const view = overlay();
  assert.equal(await scanGridLink(scanner({ error: 'cancelled' }), 'QR_CODE', view), null);
  assert.deepEqual(view.events, ['show', 'hide']);
  await assert.rejects(scanGridLink(scanner({ result: 'https://example.com' }), 'QR_CODE', overlay()), /not a GiPU/);
});

test('Cancel ends a scan even though the plugin never settles it', async () => {
  const api = { ...scanner(), scan: () => new Promise(() => {}) }, view = overlay();
  const pending = scanGridLink(api, 'QR_CODE', view);
  await new Promise(resolve => setTimeout(resolve, 0));
  view.cancel();
  assert.equal(await pending, null);
  assert.deepEqual(view.events, ['show', 'hide']);
});


test('loading a secure session removes any stale plaintext copy', async () => {
  const secure = fakeSecure(), legacy = memory();
  secure.data.set('pocketgrid.session.v1', JSON.stringify(session));
  legacy.setItem('pocketgrid.session.v1', JSON.stringify({ ...session, token: 'old' }));
  assert.deepEqual(await secureSessionStore(secure, legacy).load(), session);
  assert.equal(legacy.data.size, 0);
});

test('secure storage failures do not silently migrate or clear the session', async () => {
  const legacy = memory();
  legacy.setItem('pocketgrid.session.v1', JSON.stringify(session));
  const secure = { ...fakeSecure(), set: async () => { throw new Error('save failed'); }, delete: async () => { throw new Error('clear failed'); } };
  const store = secureSessionStore(secure, legacy);
  await assert.rejects(store.load(), /save failed/);
  assert.ok(legacy.getItem('pocketgrid.session.v1'));
  await assert.rejects(store.clear(), /clear failed/);
  assert.ok(legacy.getItem('pocketgrid.session.v1'));
});


test('a failed cold-link read releases the warm-link listener', async () => {
  let stopped = false;
  await assert.rejects(listenForGridLinks({ onOpenUrl: async () => () => { stopped = true; }, getCurrent: async () => { throw new Error('unavailable'); } }, () => {}, memory()), /unavailable/);
  assert.equal(stopped, true);
});

test('aborting a pending camera scan settles it and restores the page', async () => {
  const api = { ...scanner(), scan: () => new Promise(() => {}) }, view = overlay();
  const controller = new AbortController();
  const pending = scanGridLink(api, 'QR_CODE', view, controller.signal);
  await new Promise(resolve => setTimeout(resolve, 0));
  controller.abort();
  assert.equal(await pending, null);
  assert.ok(api.calls.includes('cancel'));
  assert.deepEqual(view.events, ['show', 'hide']);
});
