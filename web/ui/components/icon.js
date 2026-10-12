// Icons: one SVG sprite (requirements §20.3.6).
import { html } from '../app/html.js';
import { base } from '../app/config.js';

// The generated mockup carries the sprite in the page; the app loads it as a file.
const sprite = document.getElementById('mk-icons') ? '' : `${base}/assets/icons.svg`;

/** @param {{ name: string, cls?: string, label?: string }} p */
export function Icon({ name, cls = '', label }) {
  return html`
    <svg class=${'i ' + cls} aria-hidden=${label ? undefined : 'true'} role=${label
      ? 'img'
      : undefined} aria-label=${label}>
      <use href=${`${sprite}#i-${name}`} />
    </svg>
  `;
}
