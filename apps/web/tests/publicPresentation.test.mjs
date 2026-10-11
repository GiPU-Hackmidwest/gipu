import test from 'node:test';
import assert from 'node:assert/strict';
import { privateSnapshot, gridCounts, activityLabel, creditLabel, visibleImages, imageLabel } from '../src/publicPresentation.ts';
import { shouldNotifyEvent } from '../src/eventNotifications.ts';

const snapshot = {
  user: { id: 'me' }, jobs: [{ id: 'my-job', owner_id: 'me' }, { id: 'their-job', owner_id: 'them', prompt: 'Private prompt' }],
  devices: [{ id: 'mine', owner_id: 'me' }, { id: 'foreign-device', owner_id: 'them', name: 'Pi' }],
  events: [
    { id: 1, user_id: 'me', kind: 'device_paused' },
    { id: 2, user_id: 'them', job_id: 'my-job', kind: 'task_started', message: 'Pi is doing private work' },
    { id: 3, user_id: 'them', job_id: 'their-job', kind: 'job_completed', message: 'Private prompt' },
    { id: 4, kind: 'routing_updated', message: 'Unknown private history' },
  ],
};

test('legacy snapshots render only owned requests/devices and relevant activity', () => {
  const result = privateSnapshot(snapshot);
  assert.deepEqual(result.jobs.map(job => job.id), ['my-job']);
  assert.deepEqual(result.devices.map(device => device.id), ['mine']);
  assert.deepEqual(result.events.map(event => event.id), [1, 2]);
  assert.equal(snapshot.jobs.length, 2);
});

test('public activity and credit labels never interpolate server messages or unknown kinds', () => {
  assert.equal(activityLabel(snapshot.events[1]), 'Work started');
  assert.equal(activityLabel({ kind: 'Pi-private-image', message: 'Secret' }), 'Activity updated');
  assert.equal(creditLabel('private-job-id'), 'Credit update');
  assert.equal(activityLabel({ kind: 'constructor' }), 'Activity updated');
  assert.equal(creditLabel('__proto__'), 'Credit update');
});

test('counts come only from aggregate contract, with missing/invalid values unknown', () => {
  assert.equal(gridCounts(snapshot), null);
  assert.equal(gridCounts({ ...snapshot, grid: { connected: -1, ready_to_create: 2, ready_to_finish: 3 } }), null);
  const grid = { connected: 20, ready_to_create: 7, ready_to_finish: 12 };
  assert.deepEqual(gridCounts({ ...snapshot, grid }), grid);
});

test('verified image wins per variant and stage never implies verification', () => {
  const generated = { task_id: 'g', variant: 0, stage: 'generated', verified: false };
  const verified = { task_id: 'f', variant: 0, stage: 'verified', verified: true };
  assert.deepEqual(visibleImages([verified, generated]), [verified]);
  assert.equal(imageLabel(generated), 'Verifying…');
  assert.equal(imageLabel(verified), 'Ready');
  assert.equal(imageLabel({ stage: 'image_finalize' }), 'Verification unavailable');
});

test('completion alerts reject unrelated jobs and do not replay foreign earnings', () => {
  const jobs = new Set(['my-job']);
  assert.equal(shouldNotifyEvent({ kind: 'job_completed', job_id: 'their-job', user_id: 'them' }, 'me', jobs), false);
  assert.equal(shouldNotifyEvent({ kind: 'job_completed', job_id: 'my-job' }, 'me', jobs), true);
  assert.equal(shouldNotifyEvent({ kind: 'credits_earned', job_id: 'my-job', user_id: 'them' }, 'me', jobs), false);
});


test('legacy activity excludes foreign and unattributed earnings even on an owned request', () => {
  const events = [
    { id: 1, kind: 'credits_earned', job_id: 'my-job', user_id: 'them' },
    { id: 2, kind: 'credits_earned', job_id: 'my-job' },
    { id: 3, kind: 'credits_earned', job_id: 'their-job', user_id: 'me' },
    { id: 4, kind: 'task_started', job_id: 'my-job', user_id: 'them' },
  ];
  assert.deepEqual(privateSnapshot({ ...snapshot, events }).events.map(event => event.id), [3, 4]);
});
