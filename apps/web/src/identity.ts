import type { Api } from './api';
import type { GridLink, LinkCode, Session, SessionInfo, SessionResponse } from './types';

// Session and QR sign-in logic shared by every client; no UI and no platform storage.
// See docs/protocol.md (Identity, QR payloads).
type Client = Pick<Api, 'server' | 'token' | 'request'>;

export const linkCodeAlphabet = '23456789ABCDEFGHJKMNPQRSTVWXYZ';

export function normalizeServer(value: string): string {
  const server = value.trim().replace(/\/+$/, '');
  if (server) {
    const invalid = () => new Error('Use an http:// or https:// grid address without a path or sign-in details.');
    if (!/^https?:\/\/[^/?#\s]+$/i.test(server)) throw invalid();
    if (server.includes(String.fromCharCode(92))) throw invalid();
    let parsed: URL;
    try { parsed = new URL(server); } catch { throw invalid(); }
    if (!['http:', 'https:'].includes(parsed.protocol) || !parsed.hostname || parsed.username || parsed.password || parsed.pathname !== '/' || parsed.search || parsed.hash) throw invalid();
  }
  return server;
}

export function normalizeLinkCode(value: string): string {
  return value.toUpperCase().replace(/[\s-]/g, '');
}

export function parseGridLink(text: string): GridLink | null {
  let url: URL;
  try { url = new URL(text.trim()); } catch { return null; }
  const kind = url.hostname;
  if (url.protocol !== 'gipu:' || (kind !== 'join' && kind !== 'link')) return null;
  let server: string;
  try { server = normalizeServer(url.searchParams.get('grid') ?? ''); } catch { return null; }
  const raw = url.searchParams.get('code') ?? '';
  const code = kind === 'link' ? normalizeLinkCode(raw) : raw;
  if (!server || !code || code.length > 200) return null;
  if (kind === 'link' && (code.length !== 10 || [...code].some(char => !linkCodeAlphabet.includes(char)))) return null;
  return { kind, server, code };
}

export function gridLinkPayload(link: GridLink): string {
  const server = normalizeServer(link.server);
  if (!server) throw new Error('A QR code needs the full grid address.');
  return `gipu://${link.kind}?${new URLSearchParams({ grid: server, code: link.code })}`;
}

// `server` may be '' when the app is served by the coordinator; pass the page origin then.
export function linkQrPayload(server: string, code: LinkCode, origin?: string): string {
  return gridLinkPayload({ kind: 'link', server: server || origin || '', code: code.code });
}

function anonymous(client: Client) {
  // Never send an existing token while creating a session, possibly on another grid.
  if (client.token) throw new Error('Sign-in requests must not carry a session token.');
  return client;
}

export function toSession(server: string, result: SessionResponse): Session {
  return { token: result.token, name: result.user.name, server, userId: result.user.id };
}

export async function joinGrid(client: Client, joinCode: string, name?: string, clientName?: string): Promise<Session> {
  const result = await anonymous(client).request<SessionResponse>('/sessions', { join_code: joinCode, ...(name?.trim() ? { name: name.trim() } : {}), ...(clientName ? { client_name: clientName } : {}) });
  return toSession(client.server, result);
}

export async function redeemLinkCode(client: Client, code: string, clientName?: string): Promise<Session> {
  const result = await anonymous(client).request<SessionResponse>('/sessions/link', { code: normalizeLinkCode(code), ...(clientName ? { client_name: clientName } : {}) });
  return toSession(client.server, result);
}

export async function signInWithPassword(client: Client, username: string, password: string, clientName?: string): Promise<Session> {
  const result = await anonymous(client).request<SessionResponse>('/sessions/login', { username: username.trim(), password, ...(clientName ? { client_name: clientName } : {}) });
  return toSession(client.server, result);
}

export function signInWithGridLink(client: Client, link: GridLink, clientName?: string): Promise<Session> {
  if (normalizeServer(client.server) !== link.server) throw new Error('The client does not match the grid in this QR code.');
  return link.kind === 'join' ? joinGrid(client, link.code, undefined, clientName) : redeemLinkCode(client, link.code, clientName);
}

export function createLinkCode(api: Client): Promise<LinkCode> {
  return api.request<LinkCode>('/sessions/link-codes', {});
}

export function addLogin(api: Client, username: string, password: string, currentPassword?: string): Promise<{ username: string }> {
  return api.request<{ username: string }>('/account/credentials', { username: username.trim(), password, ...(currentPassword ? { current_password: currentPassword } : {}) });
}

export async function listSessions(api: Client): Promise<SessionInfo[]> {
  return (await api.request<{ sessions: SessionInfo[] }>('/sessions')).sessions;
}

export async function revokeSession(api: Client, id: string): Promise<void> {
  await api.request(`/sessions/${encodeURIComponent(id)}`, undefined, 'DELETE');
}

export async function signOut(api: Client): Promise<void> {
  await api.request('/sessions/logout', {});
}

// Platform adapters (Keychain, Android Keystore, Tauri) implement this; the web default uses localStorage.
export interface SessionStore {
  load(): Promise<Session | null>;
  save(session: Session): Promise<void>;
  clear(): Promise<void>;
}

export function webSessionStore(storage: Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>, key = 'pocketgrid.session.v1'): SessionStore {
  return {
    async load() {
      try {
        const value = JSON.parse(storage.getItem(key) || 'null');
        return value && typeof value.token === 'string' && typeof value.server === 'string' ? value : null;
      } catch { return null; }
    },
    async save(session) { storage.setItem(key, JSON.stringify(session)); },
    async clear() { storage.removeItem(key); },
  };
}
