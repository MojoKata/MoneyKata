// The locked screen (requirements S13.6, S15.4.3): the server has started and holds no key
// until an admin enters the recovery phrase here. The phrase is the authentication: nobody
// can sign in before the database is open.
import { useState } from 'preact/hooks';
import { html } from '../app/html.js';
import { api } from '../api/client.js';
import { useSubmit } from '../app/hooks.js';
import { loadSession } from '../store/session.js';
import { AuthCard } from '../components/auth.js';
import { Field, FormError } from '../components/fields.js';
import { Icon } from '../components/icon.js';

export default function Locked() {
  const [words, setWords] = useState('');
  const [shown, setShown] = useState(false);
  const unlock = useSubmit(async () => {
    await api.post('/unlock', { phrase: words });
    setWords('');
    await loadSession();
  });
  return html`
    <${AuthCard} title="MoneyKata is locked" guide="locked"
      sub="The server started and holds no key. An admin enters the recovery phrase to open it; everyone signs in after that.">
      <form onSubmit=${(/** @type {Event} */ e) => {
        e.preventDefault();
        unlock.run().catch(() => {});
      }}>
        <${Field} label="Recovery phrase" id="recovery-phrase"
          hint="The 12 words from the recovery sheet, in order. Four letters of each are enough.">
          <span class="pw"><textarea class="in" rows="3" value=${words} required
              autocomplete="off" spellcheck=${false}
              style=${shown ? {} : { WebkitTextSecurity: 'disc' }}
              onInput=${(/** @type {any} */ ev) =>
                setWords(ev.currentTarget.value)}></textarea><button
              type="button" class="icon-btn" aria-pressed=${shown ? 'true' : 'false'}
              aria-label=${shown ? 'Hide the phrase' : 'Show the phrase'}
              onClick=${() => setShown(!shown)}><${Icon} name=${shown
                ? 'eye-off'
                : 'eye'} /></button></span>
          </${Field}>
          <${FormError} error=${unlock.error} />
          <button class="btn primary" style=${{ width: '100%', justifyContent: 'center' }}
            disabled=${unlock.busy}>${unlock.busy ? 'Opening…' : 'Unlock'}</button>
          <p class="small dim" style=${{ marginTop: '12px' }}>Or on the host:
            <code>docker compose exec moneykata moneykata keys unlock</code>. The server locks
            again at every restart; nothing of the phrase is kept.</p>
          </form>
          </${AuthCard}>
  `;
}
