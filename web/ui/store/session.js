// Who is signed in, and the household, from GET /ui/api/session.
import { signal } from '@preact/signals';
import { api } from '../api/client.js';
import { setBitcoinUnit, setZone } from '../app/format.js';

/** @type {import('@preact/signals').Signal<any>} */
export const session = signal(null);
/** Why there is no session: 'signed-out', 'expired', 'disabled', or '' while loading. */
export const ended = signal('');

export async function loadSession() {
  try {
    const info = await api.get('/session');
    session.value = info;
    setZone(info.user.zone);
    setBitcoinUnit(info.user.bitcoinUnit);
    ended.value = '';
    return info;
  } catch {
    session.value = null;
    ended.value = 'signed-out';
    return null;
  }
}

/** @param {any} info */
export function setSession(info) {
  session.value = info;
  if (info) {
    setZone(info.user.zone);
    setBitcoinUnit(info.user.bitcoinUnit);
  }
}

/**
 * Keep the theme with the profile too, so a new browser starts with it.
 * @param {string} theme
 */
export async function saveTheme(theme) {
  try {
    const profile = await api.get('/profile');
    if (profile.theme !== theme) await api.patch('/profile', { theme }, profile.version);
  } catch {
    // the browser still remembers it
  }
}
