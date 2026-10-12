// The card the screens outside the frame share: sign-in, setup, invitations, reset.
import { html } from '../app/html.js';
import { useEffect } from 'preact/hooks';
import { screenGuide } from './help.js';

/** @param {{ title: string, sub?: any, children: any, guide: string }} p */
export function AuthCard({ title, sub, children, guide }) {
  useEffect(() => {
    screenGuide.value = { key: guide };
    document.title = `${title} · MoneyKata`;
  }, [guide, title]);
  return html`
    <main class="auth" id="main">
      <div class="card">
          <div class="acct-row"><div class="logo" aria-hidden="true">M</div><div><b style=${{
            fontSize: '17px',
          }}>MoneyKata</b></div></div>
          <h2>${title}</h2>
          ${sub ? html`<p class="small dim" style=${{ marginTop: 0 }}>${sub}</p>` : null}
          ${children}
        </div>
    </main>
  `;
}

/** The token a link from an email carries in its fragment (never sent to a server). */
export function tokenFromHash() {
  return decodeURIComponent(location.hash.replace(/^#/, ''));
}
