import { Brand } from './Brand';
import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { Api, errorMessage, isAndroidApp, isDesktop, isMacDesktop, isMobileApp } from './api';
import { joinGrid, normalizeServer, parseGridLink, redeemLinkCode, signInWithGridLink, signInWithPassword } from './identity';
import type { GridLink, Session } from './types';

type Detector = { detect(source: HTMLVideoElement): Promise<{ rawValue: string }[]> };
type DetectorConstructor = new (options: { formats: string[] }) => Detector;
const detectorClass = () => (globalThis as typeof globalThis & { BarcodeDetector?: DetectorConstructor }).BarcodeDetector;
const defaultServer = () => isDesktop ? import.meta.env.VITE_DEFAULT_COORDINATOR ?? 'https://66-228-53-243.ip.linodeusercontent.com' : isMobileApp ? import.meta.env.VITE_DEFAULT_COORDINATOR ?? '' : '';

export function SignInScreen({ onSession, incomingLink, onDismissLink, linkError }: { onSession: (session: Session) => Promise<void>; incomingLink?: GridLink | null; onDismissLink?: () => void; linkError?: string }) {
  const clientName = isAndroidApp ? 'Android' : isMacDesktop ? 'Mac' : 'Browser';
  const [server, setServer] = useState(defaultServer);
  const [text, setText] = useState('');
  const [addressOpen, setAddressOpen] = useState(false);
  const [link, setLink] = useState<GridLink | null>(incomingLink ?? null);
  useEffect(() => { if (incomingLink) { setLink(incomingLink); setScanning(false); } }, [incomingLink]);
  const canScan = isAndroidApp || !!detectorClass();
  const [name, setName] = useState('');
  const [joinCode, setJoinCode] = useState('pocketgrid-demo');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [mode, setMode] = useState<'join' | 'login'>('join');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [scanning, setScanning] = useState(false);
  const [unsaved, setUnsaved] = useState<Session | null>(null);
  const pending = useRef(false);
  const video = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    if (!scanning) return;
    const controller = new AbortController();
    let disposed = false; let stream: MediaStream | undefined; let timer: ReturnType<typeof setTimeout>;
    const stop = () => stream?.getTracks().forEach(track => track.stop());
    const hidden = () => { if (document.hidden) { controller.abort(); stop(); setScanning(false); } };
    document.addEventListener('visibilitychange', hidden);
    void (async () => {
      if (isAndroidApp) {
        const { androidAdapters } = await import('./android');
        if (disposed || controller.signal.aborted) return;
        const adapters = await androidAdapters();
        if (disposed || controller.signal.aborted) return;
        const found = await adapters.scanGridLink(controller.signal);
        if (!disposed) { if (found) { setLink(found); setText(''); } setScanning(false); }
        return;
      }
      const Constructor = detectorClass();
      if (!Constructor) throw new Error('Paste a link or type its code instead.');
      const detector = new Constructor({ formats: ['qr_code'] });
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false });
      if (disposed) { stop(); return; }
      if (!video.current) { stop(); return; }
      video.current.srcObject = stream; await video.current.play();
      const scan = async () => {
        if (disposed || !video.current) return;
        try {
          const results = await detector.detect(video.current);
          if (disposed) return;
          const found = results.map(result => parseGridLink(result.rawValue)).find(Boolean);
          if (found) { setLink(found); setText(''); stop(); setScanning(false); return; }
        } catch { /* A not-yet-ready video frame can be retried. */ }
        if (!disposed) timer = setTimeout(scan, 250);
      };
      void scan();
    })().catch(error => { if (!disposed && !controller.signal.aborted) { setError(isAndroidApp ? errorMessage(error) : 'Camera unavailable. Paste a link or type its code.'); setScanning(false); } stop(); });
    return () => { disposed = true; controller.abort(); clearTimeout(timer); stop(); document.removeEventListener('visibilitychange', hidden); };
  }, [scanning]);

  async function authenticate(work: () => Promise<Session>) {
    if (pending.current) return;
    pending.current = true; setBusy(true); setError(''); setScanning(false);
    try {
      const next = unsaved ?? await work();
      setUnsaved(next);
      await onSession(next);
    } catch (error) { setError(errorMessage(error)); }
    finally { pending.current = false; setBusy(false); }
  }
  function useCode(event: FormEvent) {
    event.preventDefault();
    const parsed = parseGridLink(text);
    if (parsed) { setLink(parsed); setError(''); return; }
    if (text.trim().toLowerCase().startsWith('gipu:')) { setError('This link is not valid. Ask for a new one.'); return; }
    if (isMobileApp && !server.trim()) { setAddressOpen(true); setError('Enter the grid address for this code.'); return; }
    void authenticate(() => redeemLinkCode(new Api(normalizeServer(server), ''), text, clientName));
  }
  function manual(event: FormEvent) {
    event.preventDefault();
    void authenticate(() => mode === 'join' ? joinGrid(new Api(normalizeServer(server), ''), joinCode, name, clientName)
      : signInWithPassword(new Api(normalizeServer(server), ''), username, password, clientName));
  }
  return <main className="onboarding account-onboarding"><Brand /><h1><em>Welcome to</em><br />GiPU.</h1><p>{canScan ? 'Scan a QR to join.' : 'Link your account.'}</p>
    <section className="panel stack">{!canScan && !link && !unsaved && <p>Paste a link or type a code from your other device.</p>}
      {unsaved ? <><h2>Save your sign-in</h2><button disabled={busy} onClick={() => void authenticate(async () => unsaved)}>Try again</button></> : <>
        {link ? <div className="stack"><h2>{link.kind === 'link' ? 'Link your account' : 'Join this grid'}</h2><p className="grid-address">{link.server}</p><small>{link.kind === 'link' ? 'Use your existing credits.' : 'Create a new account.'}</small><button disabled={busy} onClick={() => void authenticate(() => signInWithGridLink(new Api(link.server, ''), link, clientName))}>{busy ? 'Joining…' : 'Continue'}</button><button className="secondary" disabled={busy} onClick={() => { setLink(null); onDismissLink?.(); }}>Cancel</button></div> : <>
          {canScan && (isAndroidApp || typeof navigator.mediaDevices?.getUserMedia === 'function') && <button disabled={busy} onClick={() => { setError(''); setScanning(value => !value); }}>{scanning ? 'Stop camera' : 'Scan QR'}</button>}
          {scanning && !isAndroidApp && <video className="qr-camera" ref={video} muted playsInline aria-label="QR camera" />}
          <form className="stack" onSubmit={useCode}><label>Link or code<input value={text} onChange={event => setText(event.target.value)} autoComplete="off" autoCapitalize="none" spellCheck={false} placeholder="Paste a link or enter 10 characters" required /></label><details open={addressOpen} onToggle={event => setAddressOpen(event.currentTarget.open)}><summary>Grid address</summary><label>Address<input value={server} onChange={event => setServer(event.target.value)} inputMode="url" spellCheck={false} autoCapitalize="none" placeholder="https://your-grid" /></label></details><button disabled={busy || !text.trim()}>{busy ? 'Joining…' : 'Continue'}</button></form>
          <details><summary>Sign in another way</summary><form className="stack" onSubmit={manual}><div className="button-row"><button type="button" className="secondary" aria-pressed={mode === 'join'} onClick={() => setMode('join')}>New account</button><button type="button" className="secondary" aria-pressed={mode === 'login'} onClick={() => setMode('login')}>Use login</button></div><label>Grid address<input value={server} onChange={event => setServer(event.target.value)} placeholder={isMobileApp ? 'https://your-grid' : 'This page’s grid'} inputMode="url" autoCapitalize="none" spellCheck={false} required={isMobileApp} /></label>
            {mode === 'join' ? <><label>Name <span className="muted">(optional)</span><input value={name} onChange={event => setName(event.target.value)} autoComplete="name" maxLength={60} /></label><label>Invite code<input type="password" value={joinCode} onChange={event => setJoinCode(event.target.value)} autoComplete="off" required /></label></> : <><label>Username<input value={username} onChange={event => setUsername(event.target.value)} autoComplete="username" autoCapitalize="none" spellCheck={false} required /></label><label>Password<input type="password" value={password} onChange={event => setPassword(event.target.value)} autoComplete="current-password" required /></label></>}
            <button disabled={busy}>{busy ? 'Joining…' : mode === 'join' ? 'Join grid' : 'Sign in'}</button></form></details>
        </>}
      </>}
      {(error || linkError) && <p className="error" role="alert">{error || linkError}</p>}<small>Sharing starts only when you turn it on.</small>
    </section>
  </main>;
}
