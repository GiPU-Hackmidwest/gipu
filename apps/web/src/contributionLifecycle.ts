import type { WorkerStatus } from './desktopWorker';

export type ContributionStart = {
  connect: () => Promise<WorkerStatus>;
  status: () => Promise<WorkerStatus>;
  enable: (id: string) => Promise<void>;
  pause: (id: string) => Promise<void>;
  cancelled: () => boolean;
  onStatus: (status: WorkerStatus) => void;
  wait?: () => Promise<void>;
  clock?: () => number;
  timeoutMs?: number;
};

/** One explicit gesture connects paused, waits for readiness, then authorizes work. */
export async function connectAndStartContribution({ connect, status, enable, pause, cancelled, onStatus, wait = () => new Promise(resolve => setTimeout(resolve, 500)), clock = Date.now, timeoutMs = 310_000 }: ContributionStart): Promise<string | null> {
  const deadline = clock() + timeoutMs;
  if (cancelled()) return null;
  let worker = await connect();
  while (!cancelled()) {
    onStatus(worker);
    if (worker.phase === 'connected' && worker.deviceId) break;
    if (worker.phase !== 'starting') throw new Error(worker.phase === 'failed' ? worker.message : 'Could not connect. Try again.');
    if (clock() >= deadline) throw new Error('Starting took too long. Try again.');
    await wait();
    if (cancelled()) return null;
    worker = await status();
  }
  if (cancelled() || !worker.deviceId) return null;
  const id = worker.deviceId;
  try {
    await enable(id);
  } catch (error) {
    // A lost response does not prove the server rejected Start.
    await pause(id).catch(() => {});
    throw error;
  }
  if (cancelled()) { await pause(id); return null; }
  return id;
}

export type DeviceAcknowledgement = { device: import('./types').Device; confirmedAt: number | null };

/** Preserve acknowledged writes until a snapshot known to follow them arrives. */
export function reconcileAcknowledgedDevice(observed: import('./types').Device | undefined, now: number, acknowledged: DeviceAcknowledgement | null): import('./types').Device | undefined {
  if (!acknowledged) return observed;
  if (acknowledged.confirmedAt === null || !Number.isFinite(now) || now < acknowledged.confirmedAt) return acknowledged.device;
  return observed;
}
