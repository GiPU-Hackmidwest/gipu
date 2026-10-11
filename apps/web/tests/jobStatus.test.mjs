import test from 'node:test';
import assert from 'node:assert/strict';
import { canCancelJob, jobAcknowledgement, jobProgress } from '../src/jobStatus.ts';
const task = (kind, status, extra = {}) => ({ id: kind, kind, status, width: 512, height: 512, ...extra });
const job = (tasks, status = 'running') => ({ status, count: 2, tasks });
const device = extra => ({ id: 'worker', name: 'Laptop', online: true, enabled: true, session_expires_at: 120, capabilities: ['image_generate'], limits: { max_pixels: 262144 }, ...extra });
test('paused, expired, undersized and offline workers do not count as capacity', () => {
  for (const override of [{enabled:false}, {session_expires_at:99}, {online:false}, {limits:{max_pixels:65536}}, {capabilities:['image_finalize']}]) {
    assert.equal(jobProgress(job([task('image_generate','queued')]),[device(override)],100).title,'Waiting for a generation laptop');
  }
});
test('busy and available capacity have distinct waiting messages', () => {
  const j=job([task('image_generate','queued')]);
  assert.equal(jobProgress(j,[device({active_task_id:'other'})],100).title,'Waiting for a laptop slot');
  assert.equal(jobProgress(j,[device({})],100).title,'Ready for laptop generation');
});
test('generation does not show complete before dynamically created exports finish', () => {
  const p=jobProgress(job([task('image_generate','completed'),task('image_generate','completed'),task('image_finalize','queued')]),[],100);
  assert.equal(p.completed,2); assert.equal(p.total,4); assert.equal(p.waitingForExport,true);
  assert.equal(p.title,'Images generated · waiting for export');
});
test('running tasks name their actual assigned device', () => {
  const p=jobProgress(job([task('image_generate','running',{device_id:'worker'})]),[device({})],100);
  assert.match(p.detail,/Laptop/); assert.equal(p.waitingForExport,false);
});
test('terminal jobs never invite resumed work', () => {
  for (const status of ['completed','cancelled','failed']) assert.equal(jobProgress(job([task('image_finalize','queued')],status),[],100).waitingForExport,false);
});
test('missing server clock does not infer all devices are paused', () => {
  assert.equal(jobProgress(job([task('image_generate','queued')]),[device({})],undefined).title,'Checking device availability');
});

test('queued exports remain actionable while another image is generating or waiting', () => {
  for (const status of ['running', 'queued']) {
    const p=jobProgress(job([task('image_generate','completed'),task('image_finalize','queued'),task('image_generate',status)]),[],100);
    assert.equal(p.waitingForExport,true);
  }
});

test('a saved planning request has no device-work advice and remains cancellable', () => {
  for (const [status, attempts, title] of [['pending', 0, 'Waiting for the planner'], ['running', 1, 'Planning your request'], ['running', 2, 'Retrying planning']]) {
    const j = { ...job([], 'planning'), reserved: 40, plan: { planning: { status, attempts } } };
    const progress = jobProgress(j, [], 100);
    assert.equal(progress.title, title);
    assert.match(progress.detail, /40 sandbox credits are reserved/);
    assert.match(progress.detail, /Image work has not started/);
    assert.equal(progress.waitingForExport, false);
    assert.equal(progress.completed, 0);
    assert.equal(canCancelJob(j), true);
  }
});

test('top-level terminal state overrides stale nested planning metadata', () => {
  for (const status of ['cancelled', 'failed', 'completed']) {
    const j = { ...job([], status), plan: { planning: { status: 'pending', attempts: 0 } } };
    assert.equal(canCancelJob(j), false);
    assert.doesNotMatch(jobProgress(j, [], 100).title, /planner|Planning|Retrying/);
  }
});

test('planning failure only claims a full refund when the receipt proves it', () => {
  const j = { ...job([], 'failed'), budget: 40, plan: { planning: { status: 'failed', attempts: 1 } } };
  assert.equal(jobProgress(j, [], 100).title, 'Planning failed');
  assert.doesNotMatch(jobProgress(j, [], 100).detail, /were returned/);
  const receipt = { budget: 40, refund: 40, contributor_total: 0, platform_fee: 0, total_charged: 0 };
  assert.match(jobProgress({ ...j, receipt }, [], 100).detail, /All 40 reserved sandbox credits were returned/);
  assert.doesNotMatch(jobProgress({ ...j, receipt: { ...receipt, refund: 34, contributor_total: 6, total_charged: 6 } }, [], 100).detail, /All 40/);
  assert.equal(jobProgress({ ...j, tasks: [task('image_generate', 'completed')] }, [], 100).title, 'Request failed');
});

test('a planner warning after activation does not override queued image work', () => {
  const j = { ...job([task('image_generate', 'queued')], 'queued'), plan: { planning: { status: 'done', attempts: 1 }, dispatch_error: 'TimeoutError' } };
  assert.equal(jobProgress(j, [device({})], 100).title, 'Ready for laptop generation');
  assert.equal(canCancelJob(j), true);
});

test('acknowledgment preserves an existing terminal result instead of promising a new job', () => {
  assert.match(jobAcknowledgement({ id: '12345678-long-id', status: 'planning' }), /Request 12345678 saved.*Follow planning/);
  for (const status of ['failed', 'cancelled', 'completed']) {
    assert.match(jobAcknowledgement({ id: '12345678-long-id', status }), new RegExp(`It is ${status}`));
  }
});
