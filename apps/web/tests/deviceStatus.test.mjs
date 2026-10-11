import test from 'node:test';
import assert from 'node:assert/strict';
import { canPauseDevice, canStartDevice, deviceStatus, isSharing } from '../src/deviceStatus.ts';
const device = (extra = {}) => ({ online: true, enabled: true, session_expires_at: 110, ...extra });

test('sharing requires online status and a live session according to server time', () => {
  assert.equal(isSharing(device(), 100), true);
  for (const extra of [{ online: false }, { enabled: false }, { session_expires_at: 100 }, { session_expires_at: undefined }]) {
    assert.equal(isSharing(device(extra), 100), false);
  }
  assert.equal(isSharing(device(), NaN), false);
  assert.equal(deviceStatus(device(), NaN), 'Checking session…');
  assert.equal(deviceStatus(device({ session_expires_at: undefined }), 100), 'Checking session…');
  assert.equal(deviceStatus(device({ session_expires_at: 100 }), 100), 'Session ended');
  assert.equal(deviceStatus(device({ online: false, active_task_id: 'stale-task' }), 100), 'Offline');
});

test('only the current browser may restart an offline worker', () => {
  assert.equal(canStartDevice(device({ online: false }), false), false);
  assert.equal(canStartDevice(device({ online: false }), true), true);
  assert.equal(canStartDevice(device(), false), true);
});

test('an offline session can still be paused, while expiry invites a new explicit start', () => {
  assert.equal(canPauseDevice(device({ online: false }), 100), true);
  assert.equal(canPauseDevice(device({ session_expires_at: 100 }), 100), false);
  assert.equal(canPauseDevice(device({ enabled: false }), 100), false);
});
