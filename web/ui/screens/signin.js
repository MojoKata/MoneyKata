// Sign in (requirements S10.1.1), Forgot password? (S10.1.5) and the account-is-disabled screen
// with its request to be made active again (S10.1.7).
import { useState } from 'preact/hooks';
import { useLocation } from 'preact-iso';
import { html } from '../app/html.js';
import { api } from '../api/client.js';
import { useSubmit } from '../app/hooks.js';
import { ended, setSession } from '../store/session.js';
import { AuthCard } from '../components/auth.js';
import { errAt, Field, FormError, Input } from '../components/fields.js';

export default function SignIn() {
  const { path, route } = useLocation();
  const [mode, setMode] = useState(ended.value === 'disabled' ? 'disabled' : 'signin');
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const [sent, setSent] = useState(false);
  const signIn = useSubmit(async () => {
    try {
      const info = await api.post('/session', { login, password });
      ended.value = '';
      setSession(info);
      if (path === '/ui/signin') route('/ui/', true);
    } catch (e) {
      if (/** @type {any} */ (e).code === 'account-disabled') setMode('disabled');
      throw e;
    }
  });
  const forgot = useSubmit(async () => {
    await api.post('/password-reset', { login });
    setSent(true);
  });
  const reactivate = useSubmit(async () => {
    await api.post('/reactivation-requests', { login, password });
    setSent(true);
  });

  if (mode === 'forgot') {
    return html`
      <${AuthCard} title="Forgot password" guide="signin"
        sub="We'll email a link to choose a new password. It works once, for an hour.">
            ${sent
              ? html`
                <div class="notice" role="status">If ${login} has an account here, an email is on its way.</div>
                <p><button type="button" class="linklike" onClick=${() =>
                  setMode('signin')}>Back to sign in</button></p>
              `
              : html`
                <form onSubmit=${(/** @type {Event} */ e) => {
                  e.preventDefault();
                  forgot.run().catch(() => {});
                }}>
                  <${Field} label="Username or email">
                    <${Input} value=${login} onInput=${setLogin}
                      autocomplete="username" required />
                    </${Field}>
                    <${FormError} error=${forgot.error} />
                    <button class="btn primary" style=${{ width: '100%', justifyContent: 'center' }}
                      disabled=${forgot.busy}>Send the link</button>
                    <div
                      class="toolbar mt"><button type="button" class="linklike" onClick=${() =>
                        setMode('signin')}>Back to sign in</button></div>
                    </form>
              `}
          </${AuthCard}>
    `;
  }

  if (mode === 'disabled') {
    return html`
      <${AuthCard} title="This account is disabled" guide="signin"
        sub="An admin switched it off. You can ask them to make it active again, once a week.">
            ${sent
              ? html`<div class="notice" role="status">Your request is with the admins.</div>`
              : html`
                <form onSubmit=${(/** @type {Event} */ e) => {
                  e.preventDefault();
                  reactivate.run().catch(() => {});
                }}>
                  <${Field} label="Username or email">
                    <${Input} value=${login} onInput=${setLogin}
                      autocomplete="username" />
                    </${Field}>
                    <${Field} label="Password">
                      <${Input} type="password" value=${password}
                        onInput=${setPassword} autocomplete="current-password" />
                      </${Field}>
                      <${FormError} error=${reactivate.error} />
                      <button class="btn primary" style=${{
                        width: '100%',
                        justifyContent: 'center',
                      }}
                        disabled=${reactivate.busy}>Ask to be made active again</button>
                      </form>
              `}
            <div class="toolbar mt"><button type="button" class="linklike" onClick=${() => {
              setSent(false);
              setMode('signin');
            }}>Back to sign in</button></div>
          </${AuthCard}>
    `;
  }

  return html`
    <${AuthCard} title="Sign in" guide="signin"
      sub=${ended.value === 'expired'
        ? 'Your session ended. Sign in again.'
        : "Your household's finances, on your own server."}>
      <form onSubmit=${(/** @type {Event} */ e) => {
        e.preventDefault();
        signIn.run().catch(() => {});
      }}>
        <${Field} label="Username or email" error=${errAt(signIn.error, 'login')}>
          <${Input} value=${login} onInput=${setLogin} autocomplete="username" required />
          </${Field}>
          <${Field} label="Password">
            <${Input} type="password" value=${password} onInput=${setPassword}
              autocomplete="current-password" required />
            </${Field}>
            <${FormError} error=${signIn.error} shown=${['login']} />
            <button class="btn primary" style=${{ width: '100%', justifyContent: 'center' }}
              disabled=${signIn.busy}>Sign in</button>
            </form>
            <div
              class="toolbar mt"><button type="button" class="linklike" onClick=${() => {
                setSent(false);
                setMode('forgot');
              }}>Forgot password?</button></div>
            </${AuthCard}>
  `;
}
