import type { Job, Snapshot } from './types';

export type JobSync = {
  revision: number;
  appliedRequest: number;
  retained: ReadonlyMap<string, Job>;
};
export type SnapshotRequest = { revision: number; sequence: number };

export function initialJobSync(): JobSync {
  return { revision: 0, appliedRequest: 0, retained: new Map() };
}

export function retainJobResponse(sync: JobSync, job: Job): JobSync {
  const retained = new Map(sync.retained);
  retained.set(job.id, job);
  // Every acknowledgment invalidates reads started before this write completed.
  return { ...sync, revision: sync.revision + 1, retained };
}

export function snapshotIsCurrent(sync: JobSync, request: SnapshotRequest): boolean {
  return request.revision === sync.revision && request.sequence > sync.appliedRequest;
}

export function mergeJobResponses(jobs: Job[], retained: ReadonlyMap<string, Job>): Job[] {
  const present = new Set(jobs.map(job => job.id));
  return [...retained.values()].filter(job => !present.has(job.id))
    .concat(jobs.map(job => retained.get(job.id) ?? job));
}

export function reconcileSnapshot(sync: JobSync, request: SnapshotRequest, snapshot: Snapshot): { sync: JobSync; snapshot: Snapshot } | null {
  if (!snapshotIsCurrent(sync, request)) return null;
  const retained = new Map(sync.retained);
  for (const job of snapshot.jobs) {
    const response = retained.get(job.id);
    // Terminal responses are immutable; never replace a receipt with active work.
    if (response && (!['completed', 'cancelled', 'failed'].includes(response.status) || response.status === job.status)) retained.delete(job.id);
  }
  return {
    sync: { ...sync, appliedRequest: request.sequence, retained },
    snapshot: { ...snapshot, jobs: mergeJobResponses(snapshot.jobs, retained) },
  };
}
