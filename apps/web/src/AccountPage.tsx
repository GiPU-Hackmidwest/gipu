import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import { Api, errorMessage } from './api';
import { addLogin, createLinkCode, linkQrPayload } from './identity';
import type { LinkCode, Session } from './types';

export function AccountLinkQR({ api, session, serverTime }: { api: Api; session: Session; serverTime?: number }) {
  const [code, setCode] = useState<LinkCode | null>(null);
  const clockOffset = useRef(0);
  const [now, setNow] = useState(Date.now);
  useEffect(() => { if (Number.isFinite(serverTime)) { clockOffset.current = serverTime! * 1000 - Date.now(); setNow(Date.now() + clockOffset.current); } }, [serverTime]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const pending = useRef(false);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; const timer = setInterval(() => setNow(Date.now() + clockOffset.current), 1000); return () => { mounted.current = false; clearInterval(timer); }; }, []);
  async function create() {
    if (pending.current) return;
    pending.current = true; setBusy(true); setError(''); setCode(null);
    try { const next = await createLinkCode(api); if (mounted.current) { setCode(next); setNow(Date.now() + clockOffset.current); } }
    catch (error) { if (mounted.current) setError(errorMessage(error)); }
    finally { pending.current = false; if (mounted.current) setBusy(false); }
  }
  const valid = code && code.expires_at * 1000 > now;
  let payload = '';
  if (valid) { try { payload = linkQrPayload(session.server, code, location.origin); } catch { /* Unsupported origin has no shareable QR. */ } }
  return <section className="panel stack account-link"><h2>Link another device</h2><p>Same account. Same credits.</p>
    {valid && payload ? <><div className="account-qr"><QRCodeSVG value={payload} size={224} marginSize={4} title="Scan to link this account" /></div><code className="link-code">{code.code}</code><small>Expires in {Math.min(120, Math.max(0, Math.ceil((code.expires_at * 1000 - now) / 1000)))}s · single use</small><p className="grid-address">{session.server || location.origin}</p><small>Only share with your own device.</small></> : <p>{code ? 'Code expired. Make a new one.' : 'Scan this QR from your other device.'}</p>}
    <button disabled={busy} onClick={() => void create()}>{busy ? 'Creating…' : code ? 'New code' : 'Show QR'}</button>{error && <p className="error" role="alert">{error}</p>}
  </section>;
}

export function AccountPage({ api, session, username: existingUsername, supported, serverTime, leaving, onLeave }: { api: Api; session: Session; username?: string | null; supported: boolean | undefined; serverTime?: number; leaving: boolean; onLeave: () => Promise<void> }) {
  const [username, setUsername] = useState(existingUsername ?? '');
  const [password, setPassword] = useState('');
  const [currentPassword, setCurrentPassword] = useState('');
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const pending = useRef(false);
  async function save(event: FormEvent) {
    event.preventDefault(); if (pending.current) return;
    pending.current = true; setBusy(true); setError('');
    try { await addLogin(api, username, password, currentPassword || undefined); setPassword(''); setCurrentPassword(''); setSaved(true); }
    catch (error) { setError(errorMessage(error)); }
    finally { pending.current = false; setBusy(false); }
  }
  return <div className="account-layout">{supported ? <AccountLinkQR api={api} session={session} serverTime={serverTime} /> : <section className="panel stack"><h2>Link another device</h2><p>{supported === false ? 'Update this grid to link accounts.' : 'Connect to your grid first.'}</p></section>}<section className="panel stack"><h2>Keep your account</h2><p>{supported ? 'Link a second device or add a login.' : 'Your account is saved on this device.'}</p>{supported && <details><summary>{existingUsername || saved ? 'Update login' : 'Add a login'}</summary><form className="stack" onSubmit={save}><label>Username<input value={username} onChange={event => setUsername(event.target.value)} required autoComplete="username" autoCapitalize="none" spellCheck={false} minLength={3} maxLength={40} /></label>{(existingUsername || saved) && <label>Current password<input type="password" value={currentPassword} onChange={event => setCurrentPassword(event.target.value)} required autoComplete="current-password" /></label>}<label>New password<input type="password" value={password} onChange={event => setPassword(event.target.value)} required minLength={8} maxLength={200} autoComplete="new-password" /></label><button disabled={busy || leaving}>{busy ? 'Saving…' : 'Save login'}</button></form></details>}{saved && <p role="status">Login saved.</p>}{error && <p className="error" role="alert">{error}</p>}<button className="secondary" disabled={busy || leaving} onClick={() => void onLeave()}>{leaving ? 'Signing out…' : 'Sign out'}</button></section></div>;
}
