// Settings, for admins (requirements S16): one screen with its sections listed on the left,
// General first. Each section saves its own keys; a refusal shows at its field.
import { useEffect, useState } from 'preact/hooks';
import { html } from '../app/html.js';
import { api } from '../api/client.js';
import { useApi, useSubmit } from '../app/hooks.js';
import { ago, date, moment } from '../app/format.js';
import { useTitle } from '../components/frame.js';
import { useDialogGuide, useGuide } from '../components/help.js';
import { Failed, Loading } from '../components/bits.js';
import { Icon } from '../components/icon.js';
import { Dialog, openDialog } from '../components/dialog.js';
import { errAt, Field, FormError, Input, Select, Switch, SwitchRow } from '../components/fields.js';
import { toast } from '../components/toast.js';
import { loadSession } from '../store/session.js';

const SECTIONS = /** @type {[string, string][]} */ ([
  ['general', 'General'],
  ['email', 'Email (SMTP)'],
  ['sessions', 'Sign-in and sessions'],
  ['signup', 'Sign-up'],
  ['passwords', 'Passwords'],
  ['prices', 'Prices'],
  ['imports', 'Imports'],
  ['receipts', 'Receipts'],
  ['backups', 'Backups'],
  ['keys', 'Key storage'],
  ['alerts', 'Alerts'],
]);

/** @param {{ section?: string }} p */
export default function Settings({ section }) {
  const current = SECTIONS.some(([k]) => k === section)
    ? /** @type {string} */ (section)
    : 'general';
  const label = SECTIONS.find(([k]) => k === current)?.[1] || '';
  useTitle(label, [['Settings', '/ui/settings']]);
  useGuide('settings-' + current);
  return html`
    <div class="settings-layout">
      <nav class="settings-nav" aria-label="Settings">${SECTIONS.map(([k, l]) =>
        html`<a class=${k === current ? 'on' : ''} href=${`/ui/settings/${k}`} aria-current=${
          k === current ? 'page' : undefined
        }>${l}</a>`
      )}</nav>
      <div>${current === 'prices'
        ? html`<${Prices} />`
        : current === 'backups'
        ? html`<${Backups} />`
        : current === 'keys'
        ? html`<${Keys} />`
        : current === 'email'
        ? html`<${EmailSection} />`
        : html`<${Plain} section=${current} />`}</div>
    </div>
  `;
}

/** The sections that are plain settings: a form over their keys. @param {{ section: string }} p */
function Plain({ section }) {
  const res = useApi('/settings');
  const v = /** @type {any} */ (res.data);
  const [f, setF] = useState(/** @type {Record<string, any>} */ ({}));
  useEffect(() => {
    if (v) setF(v.values);
  }, [v]);
  const save = useSubmit(async (/** @type {string[]} */ keys) => {
    const body = Object.fromEntries(keys.map((k) => [k, f[k]]));
    await api.patch('/settings', body);
    toast('Saved');
    res.reload();
    if (keys.includes('householdName') || keys.includes('householdAvatar')) loadSession();
  });
  if (res.error) return html`<${Failed} error=${res.error} />`;
  if (!v || !f.passwordMinLength) return html`<${Loading} />`;
  const set = (/** @type {string} */ k, num = false) => (/** @type {string} */ x) =>
    setF({ ...f, [k]: num ? (x === '' ? '' : Number(x)) : x });
  const e = save.error;
  const form = (/** @type {string[]} */ keys, /** @type {any} */ body) =>
    html`
      <form class="card content-narrow"
        onSubmit=${(/** @type {Event} */ ev) => {
          ev.preventDefault();
          save.run(keys).catch(() => {});
        }}>${body}<${FormError} error=${e} shown=${keys} /><button class="btn primary" disabled=${save
          .busy}>Save</button></form>
    `;
  if (section === 'general') {
    const av = f.householdAvatar || { kind: 'initials', initials: '', color: '#3b7a57' };
    return form(
      ['serverName', 'householdName', 'householdAvatar', 'publicUrl'],
      html`
        <h3>General</h3>
        <${Field} label="Server name" error=${errAt(
          e,
          'serverName',
        )} hint="Shown to linked servers.">
          <${Input}
            value=${f.serverName} onInput=${set('serverName')} />
          </${Field}>
          <div
            class="list-item"><span class="grow dim">Server time zone</span>${v
              .serverZone} <span class="small dim">· from the host</span></div>
          <${Field} label="Household name" error=${errAt(e, 'householdName')}
            hint="At the top of the sidebar, and sent to linked servers with the avatar.">
            <${Input} value=${f.householdName}
              onInput=${set('householdName')} />
            </${Field}>
            <div class="row">
              <${Field} label="Household initials" id="household-initials" error=${errAt(
                e,
                'householdAvatar',
              )}>
                <${Input}
                  value=${av.initials || ''} onInput=${(/** @type {string} */ x) =>
                    setF({ ...f, householdAvatar: { ...av, kind: 'initials', initials: x } })} />
                </${Field}>
                <${Field} label="Household colour"
                  id="household-colour"><input class="in" type="color" value=${av.color ||
                    '#3b7a57'}
                  onInput=${(/** @type {any} */ ev) =>
                    setF({
                      ...f,
                      householdAvatar: { ...av, kind: 'initials', color: ev.currentTarget.value },
                    })} /></${Field}></div>
              <${Field} label="Public URL" error=${errAt(e, 'publicUrl')}
                hint="Links in emails are built from it, never from the request."><${Input} value=${f
                  .publicUrl || ''}
                onInput=${set('publicUrl')} placeholder="https://money.example.lan" /></${Field}>
      `,
    );
  }
  if (section === 'sessions') {
    return form(
      ['sessionIdleHours', 'sessionAbsoluteDays', 'lockoutFailures', 'lockoutMinutes'],
      html`
        <h3>Sign-in and sessions</h3>
        <div class="row">
          <${Field} label="Idle timeout (hours)" error=${errAt(e, 'sessionIdleHours')}
            hint="Signed out after this long without using MoneyKata.">
            <${Input} value=${f.sessionIdleHours} onInput=${set(
              'sessionIdleHours',
              true,
            )} inputmode="numeric" />
            </${Field}>
            <${Field} label="Longest session (days)" error=${errAt(e, 'sessionAbsoluteDays')}
              hint="Signed out after this long, used or not.">
              <${Input} value=${f.sessionAbsoluteDays} onInput=${set(
                'sessionAbsoluteDays',
                true,
              )} inputmode="numeric" />
              </${Field}>
              </div>
              <div class="row">
                <${Field} label="Failed sign-ins before a lockout" error=${errAt(
                  e,
                  'lockoutFailures',
                )}>
                  <${Input}
                    value=${f.lockoutFailures} onInput=${set(
                      'lockoutFailures',
                      true,
                    )} inputmode="numeric" />
                  </${Field}>
                  <${Field} label="Lockout (minutes)" error=${errAt(e, 'lockoutMinutes')}>
                    <${Input} value=${f.lockoutMinutes}
                      onInput=${set('lockoutMinutes', true)} inputmode="numeric" />
                    </${Field}>
                    </div>
      `,
    );
  }
  if (section === 'signup') {
    return form(
      ['signupEnabled', 'signupDomains'],
      html`
        <h3>Sign-up</h3>
        <${SwitchRow} label="Sign-up" on=${f.signupEnabled}
          onChange=${(/** @type {boolean} */ x) => setF({ ...f, signupEnabled: x })}
          hint="People can ask for an account from the sign-in screen; an admin approves or rejects each request. It needs email (SMTP) and the public URL." />
        ${errAt(e, 'signupEnabled')
          ? html`<div class="err">${errAt(e, 'signupEnabled')}</div>`
          : null}
        <${Field} label="Allowed email domains" id="signup-domains" error=${errAt(
          e,
          'signupDomains',
        )}
          hint="Optional, separated by commas. Requests from other domains are refused.">
          <${Input} value=${(f.signupDomains || []).join(', ')} placeholder="any domain"
            onInput=${(/** @type {string} */ x) =>
              setF({
                ...f,
                signupDomains: x.split(',').map((d) => d.trim()).filter(Boolean),
              })} />
          </${Field}>
      `,
    );
  }
  if (section === 'receipts') {
    return form(
      ['receiptMaxMb'],
      html`
        <h3>Receipts</h3>
        <p class="small dim" style=${{ marginTop: '-6px' }}>Receipts are kept encrypted in the data
          directory, each file once, and go into every backup.</p>
        <div class="list-item"><span class="grow dim">File types</span>PDF, JPEG, PNG, WebP, HEIC
          <span class="small dim">· checked from the content</span></div>
        <${Field} label="Largest file (MB)" id="receipt-max-mb" error=${errAt(e, 'receiptMaxMb')}>
          <${Input} value=${f.receiptMaxMb} onInput=${set(
            'receiptMaxMb',
            true,
          )} inputmode="numeric" />
          </${Field}>
      `,
    );
  }
  if (section === 'alerts') {
    return form(
      ['alertSourceHours', 'alertSummaryTime'],
      html`
        <h3>Alerts</h3>
        <p class="small dim" style=${{
          marginTop: '-6px',
        }}>Alerts tell people when something needs them.
          Each user chooses in Profile whether they are emailed.</p>
        <${Field} label="Alert when a source has failed for" id="alert-source-hours"
          error=${errAt(e, 'alertSourceHours')}
          hint="Price sources and email. Admins are alerted.">
          <${Select} value=${String(f.alertSourceHours)}
            onChange=${(/** @type {string} */ x) => setF({ ...f, alertSourceHours: Number(x) })}
            options=${[['24', '24 hours'], ['48', '48 hours'], ['72', '72 hours'], [
              '168',
              '1 week',
            ]]} />
          </${Field}>
          <${Field} label="Daily summary at" id="alert-summary-time" error=${errAt(
            e,
            'alertSummaryTime',
          )}
            hint="In each person's time zone, for those who chose the daily summary.">
            <${Input} type="time" value=${f.alertSummaryTime} onInput=${set('alertSummaryTime')} />
            </${Field}>
      `,
    );
  }
  if (section === 'passwords') {
    return form(
      ['passwordMinLength'],
      html`
        <h3>Passwords</h3>
        <${Field} label="Minimum length" error=${errAt(e, 'passwordMinLength')}
          hint="At least 8. The only rule: no character classes, no expiry; the most common passwords are refused.">
          <${Input}
            value=${f.passwordMinLength} onInput=${set(
              'passwordMinLength',
              true,
            )} inputmode="numeric" />
          </${Field}>
      `,
    );
  }
  return form(
    ['importMaxMb'],
    html`
      <h3>Imports</h3>
      <p class="small dim"
        style=${{
          marginTop: '-6px',
        }}>Accounts are kept current from the files people bring: OFX, QFX and CSV
            downloads. No bank or exchange is connected.</p>
      <div
        class="list-item"><span class="grow dim">File types</span>OFX, QFX, CSV <span class="small dim">· checked from the content</span></div>
      <${Field} label="Largest file (MB)" error=${errAt(e, 'importMaxMb')}>
        <${Input} value=${f.importMaxMb}
          onInput=${set('importMaxMb', true)} inputmode="numeric" />
        </${Field}>
    `,
  );
}

function Prices() {
  const res = useApi('/price-sources', {}, ['prices']);
  const v = /** @type {any} */ (res.data);
  const [time, setTime] = useState('');
  useEffect(() => {
    if (v) setTime(v.refreshTime);
  }, [v]);
  const saveTime = useSubmit(async () => {
    await api.patch('/settings', { priceRefreshTime: time });
    toast('Saved');
  });
  if (res.error) return html`<${Failed} error=${res.error} />`;
  if (!v) return html`<${Loading} />`;
  const change = async (/** @type {any} */ src, /** @type {any} */ body) => {
    try {
      await api.patch(`/price-sources/${src.id}`, body, src.version);
      res.reload();
    } catch (e) {
      toast(/** @type {any} */ (e).message);
    }
  };
  const remove = async (/** @type {any} */ src) => {
    await api.del(`/price-sources/${src.id}`, src.version);
    toast(`${src.label} removed`);
    res.reload();
  };
  return html`<div class="card"><h3>Price sources<span class="spacer"></span><button type="button" class="btn sm"
    onClick=${() =>
    openDialog(AddSource, { sources: v }).then((x) =>
      x && res.reload()
    )}><${Icon} name="plus" /> Add a source</button></h3>
    <p class="small dim" style=${{
    marginTop: '-6px',
  }}>Free, daily closes. For each class, the first enabled source in the order is
      used, and the next one if it fails. Every price shows its source and date.</p>
    ${
    v.sources.length
      ? html`
        <div class="table-wrap">
          <table class="t">
            <caption class="sr-only">Price sources</caption>
            <thead>
              <tr>
                <th>Source</th>
                <th>Serves</th>
                <th>Key</th>
                <th>Last run</th>
                <th class="num">Enabled</th>
                <th></th>
              </tr>
            </thead>
            <tbody>${v.sources.map((/** @type {any} */ src) =>
              html`
                <tr>
                  <td><b>${src.label}</b>${src.name === 'stub'
                    ? html`
                      <span class="pill bad">dev</span>
                    `
                    : null}<div class="small dim">${src.terms}</div></td>
                  <td class="small dim">${src.classes.join(', ')}</td>
                  <td class="small">${!src.needsKey
                    ? html`<span class="dim">none needed</span>`
                    : src.key
                    ? html`
                      <span class="pill ok" data-tip=${`set ${moment(src.key.setAt)}${
                        src.key.setBy ? ' by ' + src.key.setBy : ''
                      }`}><${Icon} name="lock" /> set</span>
                      <button type="button" class="linklike small" onClick=${() =>
                        openDialog(SetKey, { src }).then((x) => x && res.reload())}>change</button>
                    `
                    : html`<button type="button" class="btn sm" onClick=${() =>
                      openDialog(SetKey, { src }).then((x) =>
                        x && res.reload()
                      )}>Set the key</button>`}</td>
                  <td class="small dim">${src.lastRunAt
                    ? ago(src.lastRunAt)
                    : 'not yet'}${src.lastError
                    ? html`<div style=${{ color: 'var(--deny)' }}>${src.lastError}</div>`
                    : null}</td>
                  <td class="num">
                    <${Switch} on=${src.enabled} label=${'Enabled: ' +
                      src.label} help="enabled" id=${'enabled-' +
                      src.name}
                      onChange=${(/** @type {boolean} */ x) => change(src, { enabled: x })} />
                  </td>
                  <td
                    class="num"><button type="button" class="btn sm danger" onClick=${() =>
                      remove(src)}>Remove</button></td>
                </tr>
              `
            )}</tbody>
          </table>
        </div>
      `
      : html`
        <p
          class="small dim">No sources yet: prices are off until one is added. Without them, holdings are valued from
                the brokers' files and the last trade.</p>
      `
  }
    <form class="mt" style=${{ maxWidth: '360px' }} onSubmit=${(/** @type {Event} */ ev) => {
    ev.preventDefault();
    saveTime.run().catch(() => {});
  }}><${Field} label="Daily refresh at" error=${errAt(saveTime.error, 'priceRefreshTime')}
      hint=${`${v.refreshZone} time, after the US market close.`}><${Input} type="time" value=${time} onInput=${setTime} /></${Field}>
      <button class="btn sm" disabled=${saveTime.busy}>Save the time</button></form>
    <div class="toolbar"><button type="button" class="btn" onClick=${() =>
    api.post('/prices/refresh').then(
      () => toast('Refreshing prices: the header shows when it is done'),
      (e) => toast(e.message),
    )}><${Icon} name="refresh" /> Refresh prices</button></div>
  </div>`;
}

/** @param {{ close: (v?: any) => void, sources: any }} p */
function AddSource({ close, sources }) {
  useDialogGuide('dialog-add-source');
  const added = new Set(sources.sources.map((/** @type {any} */ s) => s.name));
  const options = sources.available.filter((/** @type {any} */ s) => !added.has(s.name));
  const [name, setName] = useState(options[0]?.name || '');
  const chosen = options.find((/** @type {any} */ s) => s.name === name);
  const save = useSubmit(async () => {
    close(await api.post('/price-sources', { name }));
    toast(`${chosen.label} added${chosen.needsKey ? ': set its key to enable it' : ''}`);
  });
  return html`
    <${Dialog} title="Add a price source" close=${close} onSubmit=${() =>
      save.run().catch(() => {})}
      footer=${html`<button class="btn primary" disabled=${
        save.busy || !chosen
      }>Add the source</button>`}>
        ${options.length
          ? html`<${Field} label="Source"><${Select} value=${name} onChange=${setName}
      options=${
            options.map((
              /** @type {any} */ s,
            ) => [
              s.name,
              `${s.label} · ${s.classes.join(', ')} · ${s.needsKey ? 'free key' : 'no key'}`,
            ])
          } /></${Field}>
      ${
            chosen
              ? html`<p class="small dim">${chosen.terms}${
                chosen.termsChecked ? ` Terms checked ${date(chosen.termsChecked)}.` : ''
              }
        ${
                chosen.keyUrl
                  ? html`
                    <a href=${chosen
                      .keyUrl} target="_blank" rel="noopener noreferrer">Get a free key</a>
                  `
                  : null
              }</p>`
              : null
          }`
          : html`<p>Every source MoneyKata ships is added.</p>`}
        <${FormError} error=${save.error} />
      </${Dialog}>
  `;
}

/** @param {{ close: (v?: any) => void, src: any }} p */
function SetKey({ close, src }) {
  useDialogGuide('dialog-source-key');
  const [key, setKey] = useState('');
  const save = useSubmit(async () => {
    close(await api.patch(`/price-sources/${src.id}`, { apiKey: key, enabled: true }, src.version));
    toast(`${src.label}'s key is set and the source is on`);
  });
  return html`
    <${Dialog} title=${`${src.label}'s key`} close=${close} onSubmit=${() =>
      save.run().catch(() => {})}
      footer=${html`<button class="btn primary" disabled=${save.busy}>Save the key</button>`}>
      <${Field} label="API key" error=${errAt(save.error, 'apiKey')}
        hint="Stored encrypted and never shown again; Settings shows only that it is set, when and by whom.">
          <${Input} type="password" value=${key} onInput=${setKey} autocomplete="off" required /></${Field}>
        ${src.keyUrl
          ? html`
            <p
              class="small"><a href=${src
                .keyUrl} target="_blank" rel="noopener noreferrer">Get a free key</a></p>
          `
          : null}
        <${FormError} error=${save.error} shown=${['apiKey']} />
      </${Dialog}>
  `;
}

/** Email (S16.2): the SMTP server, its password as a secret, a test, and the outbox. */
function EmailSection() {
  const res = useApi('/settings/email', {}, ['task']);
  const s = useApi('/settings');
  const v = /** @type {any} */ (res.data);
  const values = /** @type {any} */ (s.data)?.values;
  const [f, setF] = useState(/** @type {any} */ (null));
  const [password, setPassword] = useState('');
  useEffect(() => {
    if (values) {
      setF({
        smtpHost: values.smtpHost || '',
        smtpPort: values.smtpPort,
        smtpSecurity: values.smtpSecurity,
        smtpUsername: values.smtpUsername || '',
        smtpFrom: values.smtpFrom || '',
      });
    }
  }, [values]);
  const save = useSubmit(async () => {
    await api.patch('/settings', f);
    if (password) await api.put('/settings/email/password', { password });
    setPassword('');
    toast('Saved');
    res.reload();
    s.reload();
  });
  const test = useSubmit(async () => {
    const r = await api.post('/settings/email/test');
    toast(`Test email sent to ${r.to}`);
  });
  if (res.error) return html`<${Failed} error=${res.error} />`;
  if (!v || !f) return html`<${Loading} />`;
  const set = (/** @type {string} */ k, num = false) => (/** @type {string} */ x) =>
    setF({ ...f, [k]: num ? (x === '' ? '' : Number(x)) : x });
  const e = save.error;
  const keys = ['smtpHost', 'smtpPort', 'smtpSecurity', 'smtpUsername', 'smtpFrom', 'password'];
  return html`
    <form class="card content-narrow" onSubmit=${(/** @type {Event} */ ev) => {
      ev.preventDefault();
      save.run().catch(() => {});
    }}>
      <h3>Email (SMTP)</h3>
      <p class="small dim" style=${{ marginTop: '-6px' }}>${values.smtpHost
        ? 'Emails go out through this server.'
        : 'Until a host is set, emails are written to the mail folder in the data directory.'}</p>
      <div class="row">
        <${Field} label="Host" id="smtp-host" error=${errAt(e, 'smtpHost')}>
          <${Input} value=${f.smtpHost} onInput=${set('smtpHost')} placeholder="smtp.example.com" />
          </${Field}>
          <${Field} label="Port" id="smtp-port" error=${errAt(e, 'smtpPort')}>
            <${Input} value=${f.smtpPort} onInput=${set('smtpPort', true)} inputmode="numeric" />
            </${Field}>
            </div>
            <${Field} label="Security" id="smtp-security" error=${errAt(e, 'smtpSecurity')}
              hint="STARTTLS on port 587, TLS on 465. None only for a relay on your own network.">
              <${Select} value=${f.smtpSecurity} onChange=${set('smtpSecurity')}
                options=${[['starttls', 'STARTTLS'], ['tls', 'TLS'], ['none', 'None']]} />
              </${Field}>
              <div class="row">
                <${Field} label="Username" id="smtp-username" error=${errAt(e, 'smtpUsername')}>
                  <${Input} value=${f.smtpUsername} onInput=${set(
                    'smtpUsername',
                  )} autocomplete="off" />
                  </${Field}>
                  <${Field} label="Password" id="smtp-password" error=${errAt(e, 'password')}
                    hint=${v.password
                      ? `Set ${date(v.password.setAt)}${
                        v.password.setBy ? ' by ' + v.password.setBy : ''
                      }. Type a new one to replace it.`
                      : 'Not set.'}>
                    <${Input} type="password" value=${password} onInput=${setPassword}
                      autocomplete="new-password" placeholder=${v.password ? '••••••••' : ''} />
                    </${Field}>
                    </div>
                    <${Field} label="From address" id="smtp-from" error=${errAt(e, 'smtpFrom')}
                      hint="As emails show it, such as MoneyKata <money@example.com>.">
        <${Input} value=${f.smtpFrom} onInput=${set('smtpFrom')} />
      </${Field}>
      ${v.waiting || v.setAside || v.lastError
        ? html`<div class=${'notice small' + (v.lastError ? ' bad' : '')} role="status">
          ${v.waiting} waiting to be sent${
          v.setAside ? `, ${v.setAside} set aside (refused by the SMTP server)` : ''
        }${v.lastError ? html`. Last try ${ago(v.lastRun)}: ${v.lastError}` : ''}</div>`
        : null}
      <${FormError} error=${e} shown=${keys} />
      <${FormError} error=${test.error} />
      <div class="toolbar mt"><button type="button" class="btn" disabled=${test.busy ||
        !values.smtpHost} onClick=${() => test.run().catch(() => {})}>Send a test email</button>
        <span class="spacer"></span>
        <button class="btn primary" disabled=${save.busy}>Save</button></div>
    </form>
  `;
}

function Backups() {
  const res = useApi('/settings/backups', {}, ['task']);
  const s = useApi('/settings');
  const v = /** @type {any} */ (res.data);
  const values = /** @type {any} */ (s.data)?.values;
  const [f, setF] = useState(/** @type {any} */ (null));
  useEffect(() => {
    if (values) setF({ backupTime: values.backupTime, backupCopies: values.backupCopies });
  }, [values]);
  const save = useSubmit(async () => {
    await api.patch('/settings', f);
    toast('Saved');
    res.reload();
  });
  if (res.error) return html`<${Failed} error=${res.error} />`;
  if (!v || !f) return html`<${Loading} />`;
  const mb = (/** @type {number} */ n) => (n / 1048576).toFixed(n < 1048576 * 10 ? 1 : 0) + ' MB';
  return html`
    <form class="card content-narrow" onSubmit=${(/** @type {Event} */ ev) => {
      ev.preventDefault();
      save.run().catch(() => {});
    }}>
      <h3>Backups</h3>
      <div class="row">
        <${Field} label="Time of day" error=${errAt(save.error, 'backupTime')}>
          <${Input} type="time"
            value=${f.backupTime} onInput=${(/** @type {string} */ x) =>
              setF({ ...f, backupTime: x })} />
          </${Field}>
          <${Field} label="Copies kept" error=${errAt(
            save.error,
            'backupCopies',
          )}><${Input} value=${f.backupCopies}
            inputmode="numeric" onInput=${(/** @type {string} */ x) =>
              setF({ ...f, backupCopies: Number(x) })} /></${Field}></div>
        <${FormError} error=${save.error} shown=${['backupTime', 'backupCopies']} />
        <div class="toolbar"><button class="btn primary" disabled=${save
          .busy}>Save</button><span class="spacer"></span>
          <button type="button" class="btn" disabled=${v.running} onClick=${() =>
            api.post('/settings/backups/run').then(() => {
              toast('Backing up now');
              res.reload(); // shows it running; the live stream says when it ends
            }, (e) => toast(e.message))}><${Icon} name="refresh" /> Back up now</button></div>
        <div class=${'notice ' + (v.lastError ? 'bad' : '')}><${Icon} name=${v.lastError
          ? 'alert'
          : 'check'} /><div>${v.lastRun
          ? html`Last backup ${moment(v.lastRun)}${
            v.lastError ? html`: failed (${v.lastError})` : ': encrypted and verified'
          }.`
          : 'No backup yet.'} Directory (set on the host): <code>${v
          .directory}</code>. Backups open with the master key's
          recovery phrase.</div></div>
        ${v.backups.length
          ? html`
            <table class="t mt">
              <caption class="sr-only">Backups kept</caption>
              <thead>
                <tr>
                  <th>Made</th>
                  <th class="num">Size</th>
                  <th>Master key</th>
                </tr>
              </thead>
              <tbody>${v.backups.map((/** @type {any} */ b) =>
                html`
                  <tr>
                    <td>${moment(b.made)}</td>
                    <td class="num">${mb(b.bytes)}</td>
                    <td><code>${b.masterKey}</code></td>
                  </tr>
                `
              )}</tbody>
            </table>
          `
          : null}
      </form>
  `;
}

function Keys() {
  const res = useApi('/settings/keys', {}, ['task']);
  const v = /** @type {any} */ (res.data);
  const [test, setTest] = useState(/** @type {any} */ (null));
  const [armed, setArmed] = useState(false);
  if (res.error) return html`<${Failed} error=${res.error} />`;
  if (!v) return html`<${Loading} />`;
  const confirmed = v.confirmations.find((/** @type {any} */ c) => c.matched);
  return html`<div class="card"><h3>Key storage<span class="spacer"></span>${
    test
      ? test.ok
        ? html`<span class="pill ok"><${Icon} name="lock" /> everything opens</span>`
        : html`<span class="pill bad">a problem</span>`
      : null
  }</h3>
    <p class="small dim" style=${{
    marginTop: 0,
  }}>Read only here. The master key is a file on the host and is changed only there,
      so a browser session can never read or replace it.</p>
    <div class="list-item"><span class="grow dim">Key file</span><code>${v.keyFile}</code></div>
    <div class="list-item"><span class="grow dim">Fingerprint</span><code>${v.fingerprint}</code></div>
    <div class="list-item"><span class="grow dim">Made</span>${
    date(v.created.slice(0, 10))
  } · ${v.ageDays} days old
      ${
    v.reminderMonths
      ? html`<span class="small dim"> · rotation reminder at ${v.reminderMonths} months</span>`
      : null
  }
      ${
    v.reminderDue
      ? html`
        <span class="pill warn">time to rotate</span>
      `
      : null
  }</div>
    <div class="list-item"><span class="grow dim">Encrypted under it</span>the database (${
    (v.databaseBytes / 1048576).toFixed(1)
  } MB), ${v.receipts} receipt file${v.receipts === 1 ? '' : 's'}, ${v.secrets} secret${
    v.secrets === 1 ? '' : 's'
  }
      <span class="small dim">· passwords are hashed</span></div>
    <div class="list-item"><span class="grow dim">Previous key</span>${
    v.previous.length
      ? v.previous.map((/** @type {any} */ p) =>
        html`<span><code>${p.fingerprint}</code> ${
          p.removableAfter
            ? html`<span class="small dim">· can go after ${date(p.removableAfter)}</span>`
            : null
        }</span>`
      )
      : html`<span class="dim">none</span>`
  }</div>
    <div class="list-item"><div class="grow">Recovery phrase<div class="small dim">${
    confirmed
      ? `Last confirmed with moneykata keys verify on ${date(confirmed.at.slice(0, 10))}.`
      : 'Not confirmed on the host since install. Check it once a year with moneykata keys verify.'
  }</div></div>
      ${
    confirmed
      ? html`<span class="pill ok"><${Icon} name="check" /> confirmed</span>`
      : html`<span class="pill warn">unchecked</span>`
  }</div>
    <div class="notice mt"><${Icon} name="alert" /><div>Without the key file or its recovery phrase, nothing here and no backup
      can be opened. Keep the phrase in two places, one offline, never beside the backups.</div></div>
    ${
    test
      ? html`<ul class="small">${
        test.checks.map((/** @type {any} */ c) =>
          html`<li>${c.ok ? '✓' : '✗'} <b>${c.name}</b>: ${c.detail}</li>`
        )
      }</ul>`
      : null
  }
    <div class="toolbar mt"><button type="button" class="btn" onClick=${() =>
    api.post('/settings/keys/test').then(setTest)}>Test</button>
      <button type="button" class="btn" disabled=${v.reencrypting} onClick=${() =>
    armed
      ? api.post('/settings/keys/reencrypt').then(() => {
        toast('Re-encrypting under a new data key');
        setArmed(false);
        res.reload();
      })
      : setArmed(true)}>${
    v.reencrypting ? 'Re-encrypting…' : armed ? 'Click again to re-encrypt' : 'Re-encrypt'
  }</button>
      <span class="small dim">A new data key for the database and every secret. Rarely needed.</span></div>
  </div>`;
}
