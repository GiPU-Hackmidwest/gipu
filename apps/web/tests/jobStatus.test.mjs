import test from 'node:test';
import assert from 'node:assert/strict';
import { jobProgress } from '../src/jobStatus.ts';
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
