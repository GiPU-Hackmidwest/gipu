/** Tauri emits target-triple OS names (darwin/androideabi); retain friendly aliases too.
 * Build metadata is authoritative; user agent is only a development-build fallback. */
export function platformFlags(tauri: boolean, platform: string | undefined, userAgent: string) {
  const mobile = platform ? ['android', 'androideabi', 'ios'].includes(platform) : /Android|iPhone|iPad/.test(userAgent);
  const isMobileApp = tauri && mobile;
  const isDesktop = tauri && !mobile;
  const mac = platform ? platform === 'darwin' || platform === 'macos' : /Macintosh|Mac OS X/.test(userAgent);
  return { isTauri: tauri, isMobileApp, isDesktop, isMacDesktop: isDesktop && mac };
}
