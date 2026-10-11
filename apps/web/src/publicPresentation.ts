import type { GridCounts, GridEvent, JobImage, Snapshot } from './types';

/** Older coordinators may return other accounts. Never render that data. */
export function privateSnapshot(snapshot: Snapshot): Snapshot {
  const jobs = snapshot.jobs.filter(job => job.owner_id === snapshot.user.id);
  const ids = new Set(jobs.map(job => job.id));
  return { ...snapshot, jobs, devices: snapshot.devices.filter(device => device.owner_id === snapshot.user.id),
    events: snapshot.events.filter(event => event.user_id === snapshot.user.id
      || (event.kind !== 'credits_earned' && !!event.job_id && ids.has(event.job_id))) };
}

export function gridCounts(snapshot: Snapshot | null): GridCounts | null {
  const grid = snapshot?.grid;
  return grid && [grid.connected, grid.ready_to_create, grid.ready_to_finish].every(value => Number.isInteger(value) && value >= 0) ? grid : null;
}

export function activityLabel(event: Pick<GridEvent, 'kind'>): string {
  const labels: Record<string, string> = {
    job_created: 'Image requested', job_completed: 'Your image is ready', job_cancelled: 'Request cancelled',
    job_failed: 'Request stopped', task_started: 'Work started', task_completed: 'Work accepted',
    task_failed: 'Work will retry', task_retried: 'Work will retry', credits_earned: 'Credits earned',
    device_registered: 'Device connected', device_paused: 'Sharing paused', device_expired: 'Sharing session ended',
    session_expired: 'Sharing session ended', routing_updated: 'Request updated',
  };
  return Object.hasOwn(labels, event.kind) ? labels[event.kind] : 'Activity updated';
}

export function creditLabel(kind: string): string {
  const labels: Record<string, string> = { earned: 'Credits earned', reserve: 'Reserved', reserved: 'Reserved', refund: 'Refund', refunded: 'Refund',
    spent: 'Image work', payment: 'Image work', fee: 'Service fee', grant: 'Welcome credits' };
  return Object.hasOwn(labels, kind) ? labels[kind] : 'Credit update';
}

/** Show one image per variant. Verification comes only from the explicit field. */
export function visibleImages(images: JobImage[]): JobImage[] {
  const selected = new Map<number, JobImage>();
  const rank = (image: JobImage) => image.verified === true ? 3 : image.stage === 'image_finalize' || image.stage === 'verified' ? 2 : 1;
  for (const image of images) {
    const previous = selected.get(image.variant);
    if (!previous || rank(image) >= rank(previous)) selected.set(image.variant, image);
  }
  return [...selected.values()].sort((a, b) => a.variant - b.variant);
}

export function imageLabel(image: Pick<JobImage, 'verified'>): string {
  return image.verified === true ? 'Ready' : image.verified === false ? 'Verifying…' : 'Verification unavailable';
}
