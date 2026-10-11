import test from 'node:test';
import assert from 'node:assert/strict';
import { DesktopWorkerClient } from '../src/desktopWorker.ts';

test('disconnect waits for a pending native connect and runs before the next account connects', async () => {
  const calls = [];
  let finishFirst;
  const client = new DesktopWorkerClient(async (command, args) => {
    calls.push([command, args?.sessionToken]);
    if (calls.length === 1) await new Promise(resolve => { finishFirst = resolve; });
    return { phase: command === 'disconnect_worker' ? 'stopped' : 'starting' };
  });
  const first = client.connect({ projectRoot: '/prepared', server: 'https://grid.test', sessionToken: 'account-a', backend: 'auto' });
  const stopped = client.disconnect();
  const second = client.connect({ projectRoot: '/prepared', server: 'https://grid.test', sessionToken: 'account-b', backend: 'cpu' });
  await Promise.resolve();
  assert.deepEqual(calls, [['connect_worker', 'account-a']]);
  finishFirst();
  await Promise.all([first, stopped, second]);
  assert.deepEqual(calls, [['connect_worker', 'account-a'], ['disconnect_worker', undefined], ['connect_worker', 'account-b']]);
});

test('native failure does not prevent subsequent disconnect or retry', async () => {
  const calls = [];
  const client = new DesktopWorkerClient(async command => {
    calls.push(command);
    if (calls.length === 1) throw new Error('spawn failed');
    return { phase: 'stopped' };
  });
  await assert.rejects(client.connect({ projectRoot: '/missing', server: 'https://grid.test', sessionToken: 'account', backend: 'auto' }), /spawn failed/);
  assert.deepEqual(await client.disconnect(), { phase: 'stopped' });
  assert.deepEqual(calls, ['connect_worker', 'disconnect_worker']);
});

test('a delayed cleanup Pause cannot arrive after a new connection', async () => {
  const calls = [];
  let finishPause;
  const client = new DesktopWorkerClient(async command => {
    calls.push(command);
    return { phase: 'stopped', deviceId: 'old-device' };
  });
  const stopped = client.disconnect(async status => {
    assert.equal(status.deviceId, 'old-device');
    calls.push('pause-start');
    await new Promise(resolve => { finishPause = resolve; });
    calls.push('pause-finish');
  });
  const next = client.connect({ projectRoot: '/prepared', server: 'https://grid.test', sessionToken: 'account', backend: 'auto' });
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(calls, ['disconnect_worker', 'pause-start']);
  finishPause();
  await Promise.all([stopped, next]);
  assert.deepEqual(calls, ['disconnect_worker', 'pause-start', 'pause-finish', 'connect_worker']);
});
