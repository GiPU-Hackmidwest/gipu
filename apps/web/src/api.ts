import { platformFlags } from './platform';

export const { isTauri, isMobileApp, isDesktop, isMacDesktop } = platformFlags(
  '__TAURI_INTERNALS__' in window, import.meta.env.TAURI_ENV_PLATFORM, navigator.userAgent,
);
export class Api {
  constructor(readonly server: string, readonly token: string) {}
  url(path: string) { return `${this.server.replace(/\/$/, '')}${path.startsWith('/api/') ? path : `/api${path}`}`; }
  async request<T>(path: string, body?: unknown, method?: string, signal?: AbortSignal, keepalive = false): Promise<T> {
    const response = await fetch(this.url(path), { method: method ?? (body === undefined ? 'GET' : 'POST'), headers: { ...(this.token ? { Authorization: `Bearer ${this.token}` } : {}), ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) }, body: body === undefined ? undefined : JSON.stringify(body), signal, keepalive });
    if (!response.ok) { const error = await response.json().catch(() => null); throw new Error(typeof error?.detail === 'string' ? error.detail : `Request failed (${response.status})`); }
    return response.json();
  }
  async image(path: string, signal?: AbortSignal) {
    const response = await fetch(this.url(path), { headers: { Authorization: `Bearer ${this.token}` }, signal });
    if (!response.ok) throw new Error(`Image unavailable (${response.status})`);
    return response.blob();
  }
}
export function errorMessage(error: unknown) { return error instanceof Error ? error.message : String(error); }
export async function askNotifications(): Promise<boolean> {
  if (isTauri) { const api = await import('@tauri-apps/plugin-notification'); return await api.isPermissionGranted() || await api.requestPermission() === 'granted'; }
  return 'Notification' in window && await Notification.requestPermission() === 'granted';
}
export async function notify(message: string) {
  if (isTauri) { const api = await import('@tauri-apps/plugin-notification'); if (await api.isPermissionGranted()) api.sendNotification({ title: 'PocketGrid', body: message }); }
  else if ('Notification' in window && Notification.permission === 'granted') new Notification('PocketGrid', { body: message });
}

export async function copyText(text: string) {
  if (isTauri) { const clipboard = await import('@tauri-apps/plugin-clipboard-manager'); await clipboard.writeText(text); }
  else { if (!navigator.clipboard) throw new Error('Clipboard access requires HTTPS or localhost.'); await navigator.clipboard.writeText(text); }
}
