import test from 'node:test';
import assert from 'node:assert/strict';
import { connectAndStartContribution, reconcileAcknowledgedDevice } from '../src/contributionLifecycle.ts';
import { DesktopWorkerClient } from '../src/desktopWorker.ts';

const ready = { phase: 'connected', deviceId: 'owned-worker' };
function fixture(overrides = {}) {
  const calls = [];
  return { calls, options: {
    connect: async () => { calls.push('connect'); return ready; },
    status: async () => { calls.push('status'); return ready; },
    enable: async id => { calls.push(`enable:${id}`); },
    pause: async id => { calls.push(`pause:${id}`); },
    onStatus: () => {}, cancelled: () => false, wait: async () => {}, ...overrides,
  } };
}

test('one explicit start waits for native readiness before enabling its exact device', async () => {
  const { calls, options } = fixture({ connect: async () => ({ phase: 'starting' }) });
  assert.equal(await connectAndStartContribution(options), 'owned-worker');
  assert.deepEqual(calls, ['status', 'enable:owned-worker']);
});

test('cancelling while loading never enables a device', async () => {
  let cancelled = false;
  const { calls, options } = fixture({ connect: async () => ({ phase: 'starting' }), wait: async () => { cancelled = true; }, cancelled: () => cancelled });
  assert.equal(await connectAndStartContribution(options), null);
  assert.deepEqual(calls, []);
});

test('native failure and readiness timeout never authorize work', async () => {
  for (const worker of [{ phase: 'failed', message: 'Missing model' }, { phase: 'starting' }]) {
    let time = 0;
    const { calls, options } = fixture({ connect: async () => worker, status: async () => worker, clock: () => time++, timeoutMs: 1 });
    await assert.rejects(connectAndStartContribution(options), /Missing model|too long/);
    assert.deepEqual(calls, []);
  }
});

test('a late Start acknowledgment after Off is immediately paused', async () => {
  let cancelled = false;
  const { calls, options } = fixture({ enable: async () => { cancelled = true; }, cancelled: () => cancelled });
  assert.equal(await connectAndStartContribution(options), null);
  assert.deepEqual(calls, ['connect', 'pause:owned-worker']);
});

test('ambiguous Start failure attempts Pause and preserves the failure', async () => {
  const { calls, options } = fixture({ enable: async () => { throw new Error('Network lost'); } });
  await assert.rejects(connectAndStartContribution(options), /Network lost/);
  assert.deepEqual(calls, ['connect', 'pause:owned-worker']);
});

test('Leave fences a late enable and cleanup Pause before the next account connects', async () => {
  const calls = [];
  let releaseEnable;
  let cancelled = false;
  const client = new DesktopWorkerClient(async command => { calls.push(command); return ready; });
  const start = connectAndStartContribution({
    connect: () => client.connect({ projectRoot: '', server: '', sessionToken: 'old', backend: 'auto' }),
    status: () => client.status(), onStatus: () => {}, cancelled: () => cancelled,
    enable: async () => { calls.push('enable'); await new Promise(resolve => { releaseEnable = resolve; }); },
    pause: async () => { calls.push('late-pause'); },
  });
  await new Promise(resolve => setImmediate(resolve));
  cancelled = true;
  const stop = client.disconnect(async () => { await start; calls.push('cleanup-pause'); });
  const next = client.connect({ projectRoot: '', server: '', sessionToken: 'new', backend: 'auto' });
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(calls, ['connect_worker', 'enable', 'disconnect_worker']);
  releaseEnable();
  await Promise.all([stop, next]);
  assert.deepEqual(calls, ['connect_worker', 'enable', 'disconnect_worker', 'late-pause', 'cleanup-pause', 'connect_worker']);
});

test('acknowledged Start and Pause survive stale snapshots without offering a duplicate Start', () => {
  const off = { id: 'owned-worker', enabled: false };
  const on = { ...off, enabled: true, session_expires_at: 300 };
  assert.equal(reconcileAcknowledgedDevice(off, 100, { device: on, confirmedAt: null }), on);
  assert.equal(reconcileAcknowledgedDevice(off, 101, { device: on, confirmedAt: 102 }), on);
  assert.equal(reconcileAcknowledgedDevice(on, 101, { device: off, confirmedAt: 102 }), off);
});

test('new authoritative snapshots supersede acknowledgments for remote Pause and expiry', () => {
  const on = { id: 'owned-worker', enabled: true, session_expires_at: 300 };
  const paused = { ...on, enabled: false };
  const acknowledged = { device: on, confirmedAt: 102 };
  assert.equal(reconcileAcknowledgedDevice(paused, 102, acknowledged), paused);
  assert.equal(reconcileAcknowledgedDevice(paused, 301, acknowledged), paused);
  assert.equal(reconcileAcknowledgedDevice(undefined, 103, acknowledged), undefined);
});
