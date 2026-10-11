import test from 'node:test';
import assert from 'node:assert/strict';
import { initialJobSync, mergeJobResponses, reconcileSnapshot, retainJobResponse, snapshotIsCurrent } from '../src/jobSync.ts';

const job = (id, status = 'planning', extra = {}) => ({ id, status, tasks: [], ...extra });
const snapshot = jobs => ({ jobs, balance: 90, reserved: 10, earned: 0 });
const request = (sync, sequence) => ({ revision: sync.revision, sequence });

test('a pre-ack snapshot cannot hide an accepted job', () => {
  const before = initialJobSync();
  const read = request(before, 1);
  const accepted = job('new');
  const sync = retainJobResponse(before, accepted);
  assert.equal(reconcileSnapshot(sync, read, snapshot([])), null);
  assert.deepEqual(mergeJobResponses([], sync.retained), [accepted]);
  assert.equal(before.retained.size, 0, 'retention does not mutate earlier state');
});

test('refresh failure leaves the acknowledged job available without another write', () => {
  const accepted = job('new');
  const sync = retainJobResponse(initialJobSync(), accepted);
  const read = request(sync, 1);
  // A failed GET never calls reconcileSnapshot. Its error can be shown independently.
  assert.equal(snapshotIsCurrent(sync, read), true);
  assert.deepEqual(mergeJobResponses([], sync.retained), [accepted]);
  const recovered = reconcileSnapshot(sync, request(sync, 2), snapshot([job('new', 'running')]));
  assert.equal(recovered.snapshot.jobs[0].status, 'running');
  assert.equal(recovered.sync.retained.size, 0);
});

test('a fresh list omitting a retained job keeps it until that job is confirmed', () => {
  const accepted = job('new');
  const sync = retainJobResponse(initialJobSync(), accepted);
  const missing = reconcileSnapshot(sync, request(sync, 1), snapshot([job('other', 'queued')]));
  assert.deepEqual(missing.snapshot.jobs.map(job => job.id), ['new', 'other']);
  assert.equal(missing.sync.retained.size, 1);
  assert.equal(missing.snapshot.balance, 90, 'do not derive account balance from retained jobs');
  const confirmed = reconcileSnapshot(missing.sync, request(missing.sync, 2), snapshot([job('new', 'queued')]));
  assert.equal(confirmed.snapshot.jobs[0].status, 'queued');
  assert.equal(confirmed.sync.retained.size, 0);
});

test('pre-cancellation reads cannot revive a job even after a fresh snapshot confirms cancellation', () => {
  let sync = retainJobResponse(initialJobSync(), job('new'));
  const oldRead = request(sync, 1);
  const cancelled = job('new', 'cancelled', { receipt: { refund: 10 } });
  sync = retainJobResponse(sync, cancelled);
  const fresh = reconcileSnapshot(sync, request(sync, 2), snapshot([cancelled]));
  assert.equal(fresh.sync.retained.size, 0);
  assert.equal(reconcileSnapshot(fresh.sync, oldRead, snapshot([job('new', 'running')])), null);
  assert.equal(snapshotIsCurrent(fresh.sync, oldRead), false, 'old refresh errors are also ignored');
  assert.equal(fresh.snapshot.jobs[0].receipt.refund, 10);
});

test('a terminal response and its receipt cannot be replaced by active work', () => {
  const cancelled = job('new', 'cancelled', { receipt: { refund: 10 } });
  const sync = retainJobResponse(initialJobSync(), cancelled);
  const conflicting = reconcileSnapshot(sync, request(sync, 1), snapshot([job('new', 'planning')]));
  assert.deepEqual(conflicting.snapshot.jobs, [cancelled]);
  assert.equal(conflicting.sync.retained.size, 1);
});

test('later refresh completion wins over an older request in the same revision', () => {
  const sync = initialJobSync();
  const older = request(sync, 1);
  const newer = request(sync, 2);
  const fresh = reconcileSnapshot(sync, newer, snapshot([job('new', 'completed')]));
  assert.equal(reconcileSnapshot(fresh.sync, older, snapshot([job('new', 'running')])), null);
  assert.equal(snapshotIsCurrent(fresh.sync, older), false);
});

test('multiple acknowledged jobs are retained independently and never duplicated', () => {
  let sync = retainJobResponse(initialJobSync(), job('one'));
  sync = retainJobResponse(sync, job('two'));
  sync = retainJobResponse(sync, job('one', 'cancelled'));
  const fresh = reconcileSnapshot(sync, request(sync, 1), snapshot([job('two', 'queued'), job('other', 'running')]));
  assert.deepEqual(fresh.snapshot.jobs.map(job => [job.id, job.status]), [['one', 'cancelled'], ['two', 'queued'], ['other', 'running']]);
  assert.deepEqual([...fresh.sync.retained.keys()], ['one']);
});
