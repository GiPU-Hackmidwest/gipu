import { useEffect, useRef, useState } from 'react';
import { Api, errorMessage, isTauri } from './api';
import type { CreditPack, Payments } from './types';

// Stripe Checkout opens in the system browser; the native apps restrict this to checkout.stripe.com.
async function openCheckout(url: string) {
  if (isTauri) { const { openUrl } = await import('@tauri-apps/plugin-opener'); await openUrl(url); }
  else window.open(url, '_blank', 'noopener');
}

const price = (pack: CreditPack, currency: string) => new Intl.NumberFormat(undefined, { style: 'currency', currency: currency.toUpperCase() }).format(pack.amount / 100);

export function BuyCredits({ api, payments }: { api: Api; payments?: Payments }) {
  const [busy, setBusy] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const watching = useRef<string | null>(null);
  useEffect(() => () => { watching.current = null; }, []);
  async function buy(pack: CreditPack) {
    setBusy(pack.id); setError(''); setMessage('');
    let sessionId = '';
    try {
      const checkout = await api.request<{ session_id: string; url: string }>('/credits/checkout', { pack: pack.id });
      sessionId = checkout.session_id;
      await openCheckout(checkout.url);
      setMessage('Finish paying in your browser. Credits appear here once Stripe confirms.');
    } catch (error) { setError(errorMessage(error)); return; }
    finally { setBusy(''); }
    // The coordinator asks Stripe; the balance in the header updates with the next refresh.
    watching.current = sessionId;
    for (let attempt = 0; attempt < 200 && watching.current === sessionId; attempt++) {
      await new Promise(resolve => setTimeout(resolve, 3000));
      if (watching.current !== sessionId) return;
      const status = await api.request<{ status: string; credits: number }>(`/credits/checkout/${sessionId}`).catch(() => null);
      if (status?.status === 'paid') { watching.current = null; setMessage(`${status.credits} credits added.`); return; }
    }
  }
  if (!payments) return null;
  return <section className="panel stack buy-credits"><h2>Buy credits</h2>
    {payments.available ? <>
      <div className="button-row">{payments.packs.map(pack => <button key={pack.id} className="secondary" disabled={!!busy} onClick={() => void buy(pack)}>{busy === pack.id ? 'Opening…' : `${pack.credits} credits · ${price(pack, payments.currency)}`}</button>)}</div>
      <small>Test mode: pay with card 4242 4242 4242 4242, any future date and any CVC. Credits are for GiPU only and can’t be cashed out.</small>
    </> : <p>Buying credits isn’t set up on this grid.</p>}
    {message && <p role="status">{message}</p>}{error && <p className="error" role="alert">{error}</p>}
  </section>;
}
