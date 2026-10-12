// The default admin's first sign-in leads only here: choose a password and give an email
// address (requirements §13.1.2).
import { useState } from 'preact/hooks';
import { html } from '../app/html.js';
import { api } from '../api/client.js';
import { useSubmit } from '../app/hooks.js';
import { setSession } from '../store/session.js';
import { AuthCard } from '../components/auth.js';
import { errAt, Field, FormError, Input } from '../components/fields.js';

export default function Setup() {
  const [displayName, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const save = useSubmit(async () => {
    setSession(
      await api.post('/session/setup', { password, email, displayName: displayName || null }),
    );
  });
  return html`
    <${AuthCard} title="Set up the admin account" guide="setup"
      sub="This server is new. Choose the admin's password and email before anything else.">
      <form onSubmit=${(/** @type {Event} */ e) => {
        e.preventDefault();
        save.run().catch(() => {});
      }}>
        <${Field} label="Your name" hint="Shown to the people you share with.">
          <${Input}
            value=${displayName} onInput=${setName} autocomplete="name" />
          </${Field}>
          <${Field} label="Email address" error=${errAt(save.error, 'email')}>
            <${Input} type="email"
              value=${email} onInput=${setEmail} autocomplete="email" required />
            </${Field}>
            <${Field} label="New password" id="password" error=${errAt(save.error, 'password')}
              hint="At least 12 characters. Not the published default, and not a common password.">
              <${Input} type="password" value=${password} onInput=${setPassword}
                autocomplete="new-password" required />
              </${Field}>
              <${FormError} error=${save.error} shown=${['email', 'password']} />
              <button class="btn primary" style=${{ width: '100%', justifyContent: 'center' }}
                disabled=${save.busy}>Save and continue</button>
              </form>
              </${AuthCard}>
  `;
}
