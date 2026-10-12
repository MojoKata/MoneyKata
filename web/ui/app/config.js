// What the page was served with: the app's version and whether this is dev mode.
const meta = (/** @type {string} */ name) =>
  document.querySelector(`meta[name="${name}"]`)?.getAttribute('content') ?? '';

export const version = meta('mk-version');
export const dev = meta('mk-dev') === '1';
/** Where the app's own files are: versioned, cached for a year (§20.3.5). */
export const base = `/ui/v/${version}`;
