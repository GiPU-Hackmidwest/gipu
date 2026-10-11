import { parseGridLink, webSessionStore, type SessionStore } from './identity.ts';
import type { GridLink, Session } from './types';

// Android adapters for QR sign-in: Keystore-backed secrets, gipu:// links and the
// camera scanner. Call these only when the app runs on Android (isMobileApp and not iOS);
// the plugins are registered for Android alone. No UI decisions live here.

type Invoke = <T>(command: string, args?: Record<string, unknown>) => Promise<T>;
type LegacyStorage = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

export interface SecureStorage {
  get(key: string): Promise<string | null>;
  set(key: string, value: string): Promise<void>;
  delete(key: string): Promise<void>;
}

export function secureStorage(invoke: Invoke): SecureStorage {
  return {
    async get(key) {
      const result = await invoke<{ value: string; found: boolean }>('plugin:secure-storage|get_secret', { key });
      return result.found ? result.value : null;
    },
    async set(key, value) { await invoke('plugin:secure-storage|set_secret', { key, value }); },
    async delete(key) { await invoke('plugin:secure-storage|delete_secret', { key }); },
  };
}

// Same key as the web store, so a session saved before this adapter moves into the Keystore once.
export function secureSessionStore(secure: SecureStorage, legacy: LegacyStorage, key = 'pocketgrid.session.v1'): SessionStore {
  const parse = (text: string | null): Session | null => {
    try {
      const value = JSON.parse(text || 'null');
      return value && typeof value.token === 'string' && typeof value.server === 'string' ? value : null;
    } catch { return null; }
  };
  return {
    async load() {
      const stored = parse(await secure.get(key));
      if (stored) return stored;
      const earlier = await webSessionStore(legacy, key).load();
      if (!earlier) return null;
      await secure.set(key, JSON.stringify(earlier));
      legacy.removeItem(key);
      return earlier;
    },
    async save(session) { await secure.set(key, JSON.stringify(session)); legacy.removeItem(key); },
    async clear() { await secure.delete(key); legacy.removeItem(key); },
  };
}

type DeepLinkApi = {
  getCurrent(): Promise<string[] | null>;
  onOpenUrl(handler: (urls: string[]) => void): Promise<() => void>;
};

// Invite links carry the grid's join code, so only a short fingerprint is remembered.
function fingerprint(text: string): string {
  let hash = 0x811c9dc5;
  for (let i = 0; i < text.length; i++) hash = Math.imul(hash ^ text.charCodeAt(i), 0x01000193);
  return (hash >>> 0).toString(36);
}

// The plugin may report the launch URL again on reload or through both channels; handle each once.
export async function listenForGridLinks(api: DeepLinkApi, onLink: (link: GridLink) => void, seen: LegacyStorage): Promise<() => void> {
  const key = 'pocketgrid.handled-links.v1';
  const handled = (): string[] => { try { return JSON.parse(seen.getItem(key) || '[]'); } catch { return []; } };
  const deliver = (urls: string[] | null) => {
    for (const url of urls ?? []) {
      const previous = handled(), id = fingerprint(url);
      if (previous.includes(id)) continue;
      seen.setItem(key, JSON.stringify([...previous, id].slice(-20)));
      const link = parseGridLink(url);
      if (link) onLink(link);
    }
  };
  const stop = await api.onOpenUrl(deliver);
  deliver(await api.getCurrent());
  return stop;
}

type ScannerApi<Format> = {
  checkPermissions(): Promise<string>;
  requestPermissions(): Promise<string>;
  scan(options: { windowed: boolean; formats: Format[] }): Promise<{ content: string }>;
  cancel(): Promise<void>;
};

export class CameraPermissionError extends Error {
  constructor() { super('Camera access is off. Allow it in Settings to scan a code.'); }
}

/** Resolves the scanned grid link, null when cancelled, or throws for a non-GiPU code. */
export async function scanGridLink<Format>(api: ScannerApi<Format>, qrFormat: Format, overlay: ScanOverlay): Promise<GridLink | null> {
  let permission = await api.checkPermissions();
  if (permission !== 'granted') permission = await api.requestPermissions();
  if (permission !== 'granted') throw new CameraPermissionError();
  // The plugin's cancel() stops the camera but never settles the pending scan
  // (tauri-plugin-barcode-scanner 2.5.2 clears it before rejecting), so Cancel settles it here.
  let stop = () => {};
  const cancelled = new Promise<null>(resolve => { stop = () => resolve(null); });
  overlay.show(() => { stop(); void api.cancel(); });
  try {
    const result = await Promise.race([api.scan({ windowed: true, formats: [qrFormat] }), cancelled]);
    if (!result) return null;
    const link = parseGridLink(result.content);
    if (!link) throw new Error('That QR code is not a GiPU invite or link code.');
    return link;
  } catch (error) {
    if (String(error).includes('cancel')) return null;
    throw error;
  } finally {
    overlay.hide();
  }
}

export interface ScanOverlay { show(onCancel: () => void): void; hide(): void }

// A windowed scan draws the camera behind a transparent webview, so the page is
// hidden and replaced by a frame and a Cancel button. Back also cancels.
export function domScanOverlay(doc: Document = document, win: Window = window): ScanOverlay {
  let root: HTMLElement | null = null;
  let style: HTMLStyleElement | null = null;
  let onPop: (() => void) | null = null;
  return {
    show(onCancel) {
      style = doc.createElement('style');
      style.textContent = `html[data-scanning],html[data-scanning] body{background:transparent!important}
html[data-scanning] body>*:not(.qr-scan){visibility:hidden}
.qr-scan{position:fixed;inset:0;display:grid;place-items:center;align-content:center;gap:28px;z-index:2147483647;font:600 17px system-ui,sans-serif;color:#fff}
.qr-scan-frame{width:min(68vw,280px);aspect-ratio:1;border-radius:28px;box-shadow:0 0 0 100vmax rgba(0,0,0,.55);outline:3px solid #fff}
.qr-scan button{min-height:48px;padding:0 28px;border:0;border-radius:999px;background:#fff;color:#1c1e21;font:inherit}`;
      root = doc.createElement('div');
      root.className = 'qr-scan';
      root.setAttribute('role', 'dialog');
      root.setAttribute('aria-label', 'Scan a GiPU code');
      root.innerHTML = '<div class="qr-scan-frame"></div><span>Point at a GiPU code</span><button type="button">Cancel</button>';
      root.querySelector('button')!.addEventListener('click', onCancel);
      doc.head.append(style);
      doc.body.append(root);
      doc.documentElement.dataset.scanning = '';
      onPop = onCancel;
      win.history.pushState({ qrScan: true }, '');
      win.addEventListener('popstate', onPop);
    },
    hide() {
      if (onPop) win.removeEventListener('popstate', onPop);
      if (win.history.state?.qrScan) win.history.back();
      onPop = null;
      root?.remove(); style?.remove(); root = style = null;
      delete doc.documentElement.dataset.scanning;
    },
  };
}

/** The real plugins, loaded on demand so other platforms never import them. */
export async function androidAdapters() {
  const [{ invoke }, deepLink, scanner] = await Promise.all([
    import('@tauri-apps/api/core'), import('@tauri-apps/plugin-deep-link'), import('@tauri-apps/plugin-barcode-scanner'),
  ]);
  const secure = secureStorage(invoke);
  return {
    secure,
    sessionStore: secureSessionStore(secure, localStorage),
    listenForGridLinks: (onLink: (link: GridLink) => void) => listenForGridLinks(deepLink, onLink, sessionStorage),
    scanGridLink: () => scanGridLink(scanner, scanner.Format.QRCode, domScanOverlay()),
    openCameraSettings: () => scanner.openAppSettings(),
  };
}
