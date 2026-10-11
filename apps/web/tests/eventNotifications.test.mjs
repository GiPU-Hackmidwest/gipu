import test from 'node:test';
import assert from 'node:assert/strict';
import { shouldNotifyEvent } from '../src/eventNotifications.ts';

const event = (kind, userId) => ({
  id: 1, kind, user_id: userId, device_id: 'generation-laptop', job_id: 'requesters-job',
  message: '6 sandbox credits earned for accepted work', created_at: 1,
});

test('requesters do not receive earnings alerts for another contributor on their job', () => {
  const payment = event('credits_earned', 'contributor');
  assert.equal(shouldNotifyEvent(payment, 'requester'), false);
  assert.equal(shouldNotifyEvent(payment, 'contributor'), true);
});

test('unattributed earnings never become a personal earnings notification', () => {
  for (const owner of [undefined, null, '']) {
    assert.equal(shouldNotifyEvent(event('credits_earned', owner), 'requester'), false);
  }
  assert.equal(shouldNotifyEvent(event('credits_earned', ''), ''), false);
});

test('task and completion alerts retain their existing behavior', () => {
  assert.equal(shouldNotifyEvent(event('task_started', 'contributor'), 'requester'), true);
  assert.equal(shouldNotifyEvent(event('job_completed', undefined), 'requester'), true);
  assert.equal(shouldNotifyEvent(event('device_paused', 'requester'), 'requester'), false);
});
