import type { Device } from './types';

// Only a live, unexpired session represents active contribution.
export function isSharing(device: Device | undefined, now: number): boolean {
  return !!device?.online && device.enabled && Number.isFinite(now)
    && Number.isFinite(device.session_expires_at) && device.session_expires_at! > now;
}

export function deviceStatus(device: Device | undefined, now: number): string {
  if (!device) return 'Paused';
  if (!device.online) return 'Offline';
  if (device.enabled && (!Number.isFinite(now) || !Number.isFinite(device.session_expires_at))) return 'Checking session…';
  if (isSharing(device, now)) return device.active_task_id ? 'Working' : 'Sharing';
  if (device.enabled && Number.isFinite(device.session_expires_at) && device.session_expires_at! <= now) return 'Session ended';
  return 'Paused';
}

export function canStartDevice(device: Device, local: boolean): boolean {
  // This window can reconnect its own worker. Remote workers must return online first.
  return local || device.online;
}

export function canPauseDevice(device: Device, now: number): boolean {
  // An offline worker's remaining permission can still be revoked remotely.
  return device.enabled && !(Number.isFinite(device.session_expires_at) && device.session_expires_at! <= now);
}
