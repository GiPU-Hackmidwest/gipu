import test from 'node:test';
import assert from 'node:assert/strict';
import { isLocalGridAddress } from '../src/accountLinkPresentation.ts';

test('phone QR addresses flag loopback, shorthand and wildcard hosts', () => {
  for (const address of ['http://localhost:8787', 'http://LOCALHOST.:8787', 'http://grid.localhost', 'http://127.0.0.1:8787', 'http://127.1:8787', 'http://127.2.3.4', 'http://[::1]:8787', 'http://[::ffff:127.0.0.1]', 'http://0.0.0.0:8787', 'http://[::]:8787']) {
    assert.equal(isLocalGridAddress(address), true, address);
  }
});

test('LAN and hosted grid addresses are not changed or guessed', () => {
  for (const address of ['http://192.168.1.10:8787', 'http://my-mac.local:8787', 'https://grid.example.com', 'https://localhost.example.com']) {
    assert.equal(isLocalGridAddress(address), false, address);
  }
});
