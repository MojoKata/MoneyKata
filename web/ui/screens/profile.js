// Profile (requirements S12.2.16): name, email, avatar, password, time zone, theme, birth year,
// spouse for wash sales and alert emails.
import { useEffect, useState } from 'preact/hooks';
import { html } from '../app/html.js';
import { api } from '../api/client.js';
import { useApi, useSubmit } from '../app/hooks.js';
import { useTitle } from '../components/frame.js';
import { useGuide } from '../components/help.js';
import { Avatar, Failed, Loading } from '../components/bits.js';
import { errAt, Field, FormError, Input, Select } from '../components/fields.js';
import { toast } from '../components/toast.js';
import { applyTheme, theme } from '../store/prefs.js';
import { loadSession } from '../store/session.js';

export default function Profile() {
  useTitle('Profile');
  useGuide('profile');
  const res = useApi('/profile');
  const zones = useApi('/timezones');
  const p = /** @type {any} */ (res.data);
  const [f, setF] = useState(/** @type {any} */ (null));
  useEffect(() => {
    if (p) {
      setF({
        displayName: p.displayName,
        timeZone: p.timeZone,
        theme: p.theme,
        birthYear: p.birthYear ? String(p.birthYear) : '',
        spouseId: p.spouseId || '',
        alertEmails: p.alertEmails,
        avatar: p.avatar,
      });
    }
  }, [p]);
  const save = useSubmit(async () => {
    await api.patch('/profile', {
      displayName: f.displayName,
      timeZone: f.timeZone,
      theme: f.theme,
      birthYear: f.birthYear ? Number(f.birthYear) : null,
      spouseId: f.spouseId || null,
      alertEmails: f.alertEmails,
      avatar: f.avatar,
    }, p.version);
    theme.value = f.theme;
    applyTheme();
    toast('Saved');
    res.reload();
    loadSession();
  });
  if (res.error) return html`<${Failed} error=${res.error} />`;
  if (!p || !f) return html`<${Loading} lines=${8} />`;
  const z = /** @type {any} */ (zones.data);
  const set = (/** @type {string} */ k) => (/** @type {any} */ v) => setF({ ...f, [k]: v });
  const e = save.error;
  const pickAvatar = (/** @type {any} */ ev) => {
    const file = ev.currentTarget.files?.[0];
    if (!file) return;
    const img = new Image();
    img.onload = () => {
      // Made small in the browser: a 128-pixel square.
      const c = document.createElement('canvas');
      c.width = c.height = 128;
      const side = Math.min(img.width, img.height);
      c.getContext('2d')?.drawImage(
        img,
        (img.width - side) / 2,
        (img.height - side) / 2,
        side,
        side,
        0,
        0,
        128,
        128,
      );
      setF({ ...f, avatar: c.toDataURL('image/webp', 0.85) });
      URL.revokeObjectURL(img.src);
    };
    img.src = URL.createObjectURL(file);
  };
  return html`
    <div class="grid g2">
      <form class="card" onSubmit=${(/** @type {Event} */ ev) => {
        ev.preventDefault();
        save.run().catch(() => {});
      }}><h3>Profile</h3>
          <div class="acct-row" style=${{ marginBottom: '14px' }}><${Avatar} name=${f
            .displayName} image=${f.avatar} id=${p.id} />
            <label class="btn sm" for="f-avatar">Change avatar</label>
            <input id="f-avatar" class="sr-only" type="file" accept="image/png,image/jpeg,image/webp" onChange=${pickAvatar} />
            ${f.avatar
              ? html`<button type="button" class="btn sm" onClick=${() =>
                setF({ ...f, avatar: null })}>Remove</button>`
              : null}</div>
          ${errAt(e, 'avatar') ? html`<div class="err">${errAt(e, 'avatar')}</div>` : null}
          <${Field} label="Display name" error=${errAt(e, 'displayName')}><${Input} value=${f
            .displayName} onInput=${set('displayName')} required /></${Field}>
          <${Field} label="Time zone" error=${errAt(e, 'timeZone')} hint="Times show in it.">
            <${Select} value=${f.timeZone} onChange=${set('timeZone')} options=${[[
              'auto',
              `Auto: the server's (${z?.server || '…'})`,
            ], ...(z?.zones || []).map((/** @type {string} */ x) => [x, x])]} /></${Field}>
          <${Field} label="Theme" error=${errAt(e, 'theme')}><${Select} value=${f
            .theme} onChange=${set('theme')}
            options=${[['dark', 'Dark'], ['light', 'Light'], [
              'system',
              "The system's",
            ]]} /></${Field}>
          <${Field} label="Birth year" error=${errAt(
            e,
            'birthYear',
          )} hint="For contribution catch-up limits and RMDs."><${Input}
            value=${f.birthYear} onInput=${set('birthYear')} inputmode="numeric" /></${Field}>
          <${Field} label="Spouse for wash sales" id="spouse" error=${errAt(e, 'spouseId')}
            hint="Wash sales are checked across your accounts and your spouse's shared ones."><${Select} value=${f
              .spouseId}
            onChange=${set('spouseId')} options=${[
              ['', 'None'],
              ...p.people.map((/** @type {any} */ x) => [x.id, x.displayName]),
            ]} /></${Field}>
          <${Field} label="Alert emails" error=${errAt(
            e,
            'alertEmails',
          )} hint="Alerts always show in MoneyKata; this is only about email.">
            <${Select} value=${f.alertEmails} onChange=${set('alertEmails')} options=${[
              ['each', 'Each alert'],
              ['daily', 'A daily summary'],
              ['none', 'None'],
            ]} /></${Field}>
          <${FormError} error=${e} shown=${[
            'displayName',
            'timeZone',
            'theme',
            'birthYear',
            'spouseId',
            'alertEmails',
            'avatar',
          ]} />
          <button class="btn primary" disabled=${save.busy}>Save</button>
        </form>
        <div class="grid" style=${{ alignContent: 'start' }}>
          <${Email} p=${p} reload=${res.reload} />
          <${Password} />
        </div></div>
  `;
}

/** @param {{ p: any, reload: () => void }} props */
function Email({ p, reload }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [needPassword, setNeed] = useState(false);
  const save = useSubmit(async () => {
    if (needPassword) await api.post('/session/reauth', { password });
    try {
      await api.post('/profile/email', { email });
    } catch (e) {
      if (/** @type {any} */ (e).code === 'reauth-required') {
        setNeed(true);
        return;
      }
      throw e;
    }
    toast(`A confirmation link went to ${email}`);
    setEmail('');
    setNeed(false);
    reload();
  });
  return html`
    <form class="card" onSubmit=${(/** @type {Event} */ ev) => {
      ev.preventDefault();
      save.run().catch(() => {});
    }}>
      <h3>Email address</h3>
      <p class="small" style=${{ marginTop: 0 }}>${p.email}${p.pendingEmail
        ? html`<span class="dim"> · waiting for ${p.pendingEmail} to be confirmed</span>`
        : null}</p>
      <${Field} label="New email address" error=${errAt(save.error, 'email')}
        hint="It takes effect when you open the link sent to it.">
          <${Input} type="email" value=${email} onInput=${setEmail} autocomplete="email" required /></${Field}>
        ${needPassword
          ? html`
            <${Field} label="Your password" id="reauth-password"
              hint="Asked again: it was over 10 minutes ago.">
              <${Input}
                type="password" value=${password} onInput=${setPassword} autocomplete="current-password"
                required />
              </${Field}>
          `
          : null}
        <${FormError} error=${save.error} shown=${['email']} />
        <button class="btn" disabled=${save.busy}>Send the confirmation link</button></form>
  `;
}

function Password() {
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const save = useSubmit(async () => {
    await api.post('/profile/password', { currentPassword: current, newPassword: next });
    toast('Password changed: your other sessions were signed out');
    setCurrent('');
    setNext('');
  });
  return html`
    <form class="card" onSubmit=${(/** @type {Event} */ ev) => {
      ev.preventDefault();
      save.run().catch(() => {});
    }}>
      <h3>Password</h3>
      <${Field} label="Current password" error=${errAt(save.error, 'currentPassword')}>
        <${Input} type="password" value=${current}
          onInput=${setCurrent} autocomplete="current-password" required />
        </${Field}>
        <${Field} label="New password" error=${errAt(save.error, 'newPassword')}
          hint="At least 12 characters; not a common password.">
          <${Input} type="password" value=${next} onInput=${setNext} autocomplete="new-password" required /></${Field}>
        <${FormError} error=${save.error} shown=${['currentPassword', 'newPassword']} />
        <button class="btn" disabled=${save.busy}>Change password</button></form>
  `;
}
