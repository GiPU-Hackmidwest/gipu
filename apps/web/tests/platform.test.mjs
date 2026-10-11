import test from 'node:test';
import assert from 'node:assert/strict';
import { platformFlags } from '../src/platform.ts';

test('Android uses native plugins but never exposes a desktop worker', () => {
  for (const platform of ['android', 'androideabi']) {
    assert.deepEqual(platformFlags(true, platform, 'Macintosh'), { isTauri: true, isMobileApp: true, isDesktop: false, isMacDesktop: false });
  }
});
test('Mac metadata exposes the worker even if the webview changes its user agent', () => {
  for (const platform of ['darwin', 'macos']) {
    assert.deepEqual(platformFlags(true, platform, ''), { isTauri: true, isMobileApp: false, isDesktop: true, isMacDesktop: true });
  }
});
test('browser and other desktop targets never expose Mac commands', () => {
  assert.equal(platformFlags(false, undefined, 'Macintosh').isMacDesktop, false);
  assert.equal(platformFlags(true, 'windows', 'Macintosh').isMacDesktop, false);
  assert.equal(platformFlags(true, 'linux', 'Macintosh').isMacDesktop, false);
});
test('development fallback separates native phone webviews from Mac webviews', () => {
  for (const ua of ['Android', 'iPhone; CPU iPhone OS like Mac OS X', 'iPad; CPU OS like Mac OS X']) {
    assert.equal(platformFlags(true, undefined, ua).isDesktop, false);
  }
  assert.equal(platformFlags(true, undefined, 'Macintosh').isMacDesktop, true);
});

test('iOS metadata remains mobile even with a desktop-style user agent', () => {
  assert.deepEqual(platformFlags(true, 'ios', 'Macintosh'), { isTauri: true, isMobileApp: true, isDesktop: false, isMacDesktop: false });
});
