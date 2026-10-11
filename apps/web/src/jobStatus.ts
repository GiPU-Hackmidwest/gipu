import type { Device, Job } from './types';

export type JobProgress = {
  title: string;
  detail: string;
  generated: number;
  finalized: number;
  completed: number;
  total: number;
  waitingForExport: boolean;
};

export function canCancelJob(job: Pick<Job, 'status'>): boolean {
  return ['planning', 'queued', 'running'].includes(job.status);
}

export function jobAcknowledgement(job: Pick<Job, 'id' | 'status'>): string {
  const prefix = `Request ${job.id.slice(0, 8)} saved.`;
  if (job.status === 'planning') return `${prefix} Follow planning and cancel if needed under Jobs & results.`;
  if (['completed', 'cancelled', 'failed'].includes(job.status)) return `${prefix} It is ${job.status}; see its result and receipt below.`;
  return `${prefix} Follow its progress under Jobs & results.`;
}

export function eligibleDevices(devices: Device[], kind: string, pixels: number, now: number): Device[] {
  if (!Number.isFinite(now)) return [];
  return devices.filter(device => device.online && device.enabled
    && Number.isFinite(device.session_expires_at) && device.session_expires_at! > now
    && device.capabilities.includes(kind) && device.limits.max_pixels >= pixels);
}

export function jobProgress(job: Job, devices: Device[], now: number): JobProgress {
  const generated = job.tasks.filter(t => t.kind === 'image_generate' && t.status === 'completed').length;
  const finalized = job.tasks.filter(t => t.kind === 'image_finalize' && t.status === 'completed').length;
  const base = { generated, finalized, completed: generated + finalized, total: job.count * 2, waitingForExport: false };
  if (job.status === 'completed') return { ...base, title: 'Images ready', detail: 'Generation and export are complete. Your receipt shows the final charge and refund.' };
  if (job.status === 'cancelled') return { ...base, title: 'Request cancelled', detail: 'Accepted work stays paid; remaining reserved credits are returned.' };
  if (job.status === 'failed') {
    if (job.plan?.planning?.status === 'failed' && job.tasks.length === 0) {
      const receipt = job.receipt;
      const fullyRefunded = receipt && receipt.budget === job.budget && receipt.refund === job.budget
        && receipt.total_charged === 0 && receipt.contributor_total === 0 && receipt.platform_fee === 0;
      return { ...base, title: 'Planning failed', detail: fullyRefunded
        ? `No image work started. All ${receipt.refund} reserved sandbox credits were returned.`
        : 'No image work started. Check the receipt and credit ledger for the refund status.' };
    }
    return { ...base, title: 'Request failed', detail: 'The grid could not finish this request. Check activity and the credit ledger for the outcome.' };
  }
  if (job.status === 'planning') {
    const planning = job.plan?.planning;
    const reserved = Number.isFinite(job.reserved) ? `${job.reserved} sandbox credits are reserved. ` : '';
    return { ...base, title: planning?.status === 'pending' ? 'Waiting for the planner'
      : (planning?.attempts ?? 0) > 1 ? 'Retrying planning' : 'Planning your request',
    detail: `${reserved}Your request is saved. Image work has not started; you can cancel and release the budget.` };
  }
  base.waitingForExport = ['queued', 'running'].includes(job.status) && job.tasks.some(t => t.kind === 'image_finalize' && t.status === 'queued');
  const running = job.tasks.filter(t => t.status === 'running');
  if (running.length) {
    const generating = running.some(t => t.kind === 'image_generate');
    const names = [...new Set(running.map(t => devices.find(d => d.id === t.device_id)?.name).filter(Boolean))];
    return { ...base, title: generating ? 'Generating on participating devices' : 'Finishing image exports',
      detail: names.length ? `Working now: ${names.join(', ')}.` : 'Assigned workers are processing your request.' };
  }
  const generation = job.tasks.find(t => t.kind === 'image_generate' && t.status === 'queued');
  const finalization = job.tasks.find(t => t.kind === 'image_finalize' && t.status === 'queued');
  const queued = generation ?? finalization;
  if (!queued) return { ...base, title: 'Waiting for a grid update', detail: 'Your request is recorded. Check activity before submitting it again.' };
  const kind = queued.kind;
  const eligible = eligibleDevices(devices, kind, queued.width * queued.height, now);
  const exportStage = kind === 'image_finalize';
  if (!Number.isFinite(now)) return { ...base, title: 'Checking device availability', detail: 'Waiting for current coordinator timing before evaluating sharing sessions.' };
  if (!eligible.length) return { ...base,
    title: exportStage ? 'Images generated · waiting for export' : 'Waiting for a generation laptop',
    detail: exportStage ? 'No compatible export device is sharing. Start this window or a phone, keep it open, and allow this image size.'
      : 'No compatible laptop is sharing. Connect its Python worker or renew its sharing session with a sufficient image limit. This window cannot generate images.' };
  if (eligible.every(d => d.active_task_id)) return { ...base,
    title: exportStage ? 'Waiting for an export slot' : 'Waiting for a laptop slot',
    detail: 'Compatible devices are sharing but busy. This request will continue when a worker accepts it.' };
  return { ...base,
    title: exportStage ? 'Ready for image export' : 'Ready for laptop generation',
    detail: 'Compatible capacity is online. Waiting for a worker to claim the next task.' };
}
