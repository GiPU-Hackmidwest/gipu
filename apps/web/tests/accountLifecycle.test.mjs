import test from 'node:test';
import assert from 'node:assert/strict';
import { stopAndSignOut } from '../src/accountLifecycle.ts';

test('logout waits for late enable and every worker Pause before revoke and clear', async () => {
  const calls = []; let release;
  const lateStart = new Promise(resolve => { release = resolve; });
  const finished = stopAndSignOut({ legacy: false, stops: [
    async () => { await lateStart; calls.push('browser-pause'); },
    async () => { calls.push('native-disconnect'); await lateStart; calls.push('native-pause'); },
  ], revoke: async () => { calls.push('revoke'); }, clear: async () => { calls.push('clear'); } });
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(calls, ['native-disconnect']);
  release(); await finished;
  assert.deepEqual(calls, ['native-disconnect', 'browser-pause', 'native-pause', 'revoke', 'clear']);
});

test('failed Pause still attempts other local cleanup but retains credentials', async () => {
  const calls = [];
  await assert.rejects(stopAndSignOut({ legacy: false, stops: [async () => { throw new Error('Offline'); }, async () => { calls.push('stop-native'); }],
    revoke: async () => { calls.push('revoke'); }, clear: async () => { calls.push('clear'); } }), /Offline/);
  assert.deepEqual(calls, ['stop-native']);
});

test('confirmed older coordinators sign out locally after stopping, without unsupported endpoint', async () => {
  const calls = [];
  await stopAndSignOut({ legacy: true, stops: [async () => { calls.push('pause'); }], revoke: async () => { throw new Error('404'); }, clear: async () => { calls.push('clear'); } });
  assert.deepEqual(calls, ['pause', 'clear']);
});

test('revoked credentials clear locally; network or server errors never count as revoked', async () => {
  for (const status of [401, 403, 500, undefined]) {
    let cleared = false;
    const error = Object.assign(new Error('Failure'), { status });
    const result = stopAndSignOut({ legacy: false, stops: [async () => { if (status === 401) throw error; }], revoke: async () => { throw error; }, clear: async () => { cleared = true; } });
    if (status === 401) await result; else await assert.rejects(result);
    assert.equal(cleared, status === 401);
  }
});
