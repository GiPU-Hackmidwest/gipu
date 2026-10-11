import type { SessionStore } from './identity';
import type { Session } from './types';

export const legacySessionKey = 'pocketgrid.session.v1';
type Storage = Pick<globalThis.Storage, 'getItem' | 'removeItem'>;
type Invoke = <T>(command: string, args?: Record<string, unknown>) => Promise<T>;

export function validSession(value: unknown): value is Session {
  if (!value || typeof value !== 'object') return false;
  const session = value as Partial<Session>;
  return typeof session.token === 'string' && session.token.length > 0 && typeof session.name === 'string'
    && typeof session.server === 'string' && (session.server === '' || /^https?:\/\/[^/?#\s]+$/i.test(session.server));
}

/** Never fall back to browser storage if secure storage fails. */
export function macSessionStore(invoke: Invoke, legacy: Storage): SessionStore {
  return {
    async load() {
      const current = await invoke<Session | null>('load_mac_session');
      if (current !== null) {
        if (!validSession(current)) throw new Error('Saved sign-in could not be read.');
        legacy.removeItem(legacySessionKey);
        return current;
      }
      let previous: unknown;
      try { previous = JSON.parse(legacy.getItem(legacySessionKey) || 'null'); } catch { previous = null; }
      if (!validSession(previous)) return null;
      await invoke('save_mac_session', { session: previous });
      legacy.removeItem(legacySessionKey);
      return previous;
    },
    async save(session) {
      if (!validSession(session)) throw new Error('Could not save this sign-in.');
      await invoke('save_mac_session', { session });
      legacy.removeItem(legacySessionKey);
    },
    async clear() {
      // Do not report a successful sign-out if Keychain deletion failed.
      await invoke('clear_mac_session');
      legacy.removeItem(legacySessionKey);
    },
  };
}
