/** These addresses refer to the scanning device, not the coordinator's computer. */
export function isLocalGridAddress(address: string): boolean {
  try {
    const host = new URL(address).hostname.toLowerCase().replace(/\.$/, '');
    return host === 'localhost' || host.endsWith('.localhost') || host.startsWith('127.')
      || host === '[::1]' || host === '0.0.0.0' || host === '[::]'
      || /^\[::ffff:7f[0-9a-f]{2}:[0-9a-f]{1,4}\]$/.test(host);
  } catch { return false; }
}
