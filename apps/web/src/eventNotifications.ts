import type { GridEvent } from './types';

export function shouldNotifyEvent(event: GridEvent, userId: string): boolean {
  // A requester's event feed also includes payments to other contributors.
  if (event.kind === 'credits_earned') return !!userId && event.user_id === userId;
  return event.kind === 'task_started' || event.kind === 'job_completed';
}
