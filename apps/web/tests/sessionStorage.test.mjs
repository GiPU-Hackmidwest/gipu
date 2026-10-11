import test from 'node:test';
import assert from 'node:assert/strict';
import { macSessionStore, legacySessionKey } from '../src/sessionStorageCore.ts';

const sample = { token: 'test-only', name: 'Guest', server: 'https://grid.example', userId: 'u1' };
function fixture({ current = null, legacy = sample, fail } = {}) {
  const data = new Map(legacy ? [[legacySessionKey, JSON.stringify(legacy)]] : []);
  const calls = [];
  const store = macSessionStore(async (command, args) => {
    calls.push(command);
    if (command === fail) throw new Error('Keychain unavailable');
    if (command === 'load_mac_session') return current;
    if (command === 'save_mac_session') current = args.session;
    if (command === 'clear_mac_session') current = null;
  }, { getItem: key => data.get(key) ?? null, removeItem: key => data.delete(key) });
  return { store, data, calls, current: () => current };
}

test('existing sign-in migrates only after Keychain acknowledges the save', async () => {
  const f = fixture();
  assert.deepEqual(await f.store.load(), sample);
  assert.deepEqual(f.current(), sample);
  assert.equal(f.data.has(legacySessionKey), false);
  assert.deepEqual(f.calls, ['load_mac_session', 'save_mac_session']);
});
test('failed secure migration retains the recoverable legacy token and rejects login', async () => {
  const f = fixture({ fail: 'save_mac_session' });
  await assert.rejects(f.store.load(), /Keychain/);
  assert.equal(f.data.has(legacySessionKey), true);
  assert.equal(f.current(), null);
});
test('Keychain read error never silently falls back to browser storage', async () => {
  const f = fixture({ fail: 'load_mac_session' });
  await assert.rejects(f.store.load(), /Keychain/);
  assert.deepEqual(f.calls, ['load_mac_session']);
});
test('secure session wins over an obsolete browser session', async () => {
  const newer = { ...sample, token: 'new-test-only' };
  const f = fixture({ current: newer });
  assert.deepEqual(await f.store.load(), newer);
  assert.equal(f.data.has(legacySessionKey), false);
});
test('clearing removes both stores and propagates Keychain failure', async () => {
  const f = fixture({ current: sample });
  await f.store.clear();
  assert.equal(f.current(), null);
  assert.equal(f.data.has(legacySessionKey), false);
  const broken = fixture({ current: sample, fail: 'clear_mac_session' });
  await assert.rejects(broken.store.clear(), /Keychain/);
  assert.deepEqual(broken.current(), sample);
});
