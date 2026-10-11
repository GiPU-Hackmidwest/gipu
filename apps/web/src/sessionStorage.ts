import { isAndroidApp, isMacDesktop } from './api';
import { webSessionStore } from './identity';
import type { SessionStore } from './identity';
import { macSessionStore } from './sessionStorageCore';

let store: SessionStore | undefined;
export function sessionStore(): SessionStore {
  if (!store) {
    if (isAndroidApp) {
      let pending: Promise<SessionStore> | undefined;
      const androidStore = () => pending ??= import('./android').then(module => module.androidAdapters()).then(adapters => adapters.sessionStore)
        .catch(error => { pending = undefined; throw error; });
      store = { load: async () => (await androidStore()).load(), save: async session => (await androidStore()).save(session), clear: async () => (await androidStore()).clear() };
      return store;
    }
    store = isMacDesktop ? macSessionStore(async (command, args) => {
      const { invoke } = await import('@tauri-apps/api/core');
      return invoke(command, args);
    }, localStorage) : webSessionStore(localStorage);
  }
  return store;
}
