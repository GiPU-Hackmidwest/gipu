const revokedCredential = (error: unknown) => !!error && typeof error === 'object' && 'status' in error && error.status === 401;

/** Stop every local worker before revoking or discarding credentials needed by Pause. */
export async function stopAndSignOut({ stops, legacy, revoke, clear }: {
  stops: (() => Promise<void>)[]; legacy: boolean; revoke: () => Promise<void>; clear: () => Promise<void>;
}): Promise<void> {
  const stopped = await Promise.allSettled(stops.map(stop => Promise.resolve().then(stop)));
  const failure = stopped.find(result => result.status === 'rejected' && !revokedCredential(result.reason));
  if (failure?.status === 'rejected') throw failure.reason;
  if (!legacy) {
    try { await revoke(); }
    catch (error) { if (!revokedCredential(error)) throw error; }
  }
  await clear();
}
