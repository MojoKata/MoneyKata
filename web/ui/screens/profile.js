// Profile (requirements S12.2.16): name, email, avatar, password, two-step sign-in (S10.1.6),
// time zone, theme, birth year, spouse for wash sales and alert emails.
import { useEffect, useState } from 'preact/hooks';
import { html } from '../app/html.js';
import { api } from '../api/client.js';
import { useApi, useSubmit } from '../app/hooks.js';
import { useTitle } from '../components/frame.js';
import { Avatar, Failed, Loading } from '../components/bits.js';
import { errAt, Field, FormError, Input, Select } from '../components/fields.js';
import { toast } from '../components/toast.js';
import { Dialog, openDialog } from '../components/dialog.js';
import { ModelsChart } from '../charts/chart.js';
import { useDialogGuide, useGuide } from '../components/help.js';
import { applyTheme, theme } from '../store/prefs.js';
import { loadSession } from '../store/session.js';
import { AccessTokens } from '../components/tokens.js';
import { num } from '../app/dec.js';

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
          <${TwoStep} p=${p} reload=${res.reload} />
          <${AccessTokens} />
        </div></div>
      <${Assumptions} />
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

/**
 * Two-step sign-in: off, or on with the recovery codes left. Each change asks for the
 * password again when it was given over 10 minutes ago (S13.7.2).
 * @param {{ p: any, reload: () => void }} props
 */
function TwoStep({ p, reload }) {
  const [password, setPassword] = useState('');
  const [needPassword, setNeed] = useState(false);
  const act = useSubmit(async (/** @type {() => Promise<void>} */ fn) => {
    if (needPassword) await api.post('/session/reauth', { password });
    try {
      await fn();
    } catch (e) {
      if (/** @type {any} */ (e).code === 'reauth-required') {
        setNeed(true);
        return;
      }
      throw e;
    }
    setNeed(false);
    setPassword('');
  });
  const turnOn = async () => {
    const setup = await api.post('/profile/two-step');
    const done = await openDialog(TwoStepSetup, { setup });
    if (done) toast('Two-step sign-in is on');
    reload();
  };
  const newCodes = async () => {
    const r = await api.post('/profile/two-step/recovery-codes');
    await openDialog(RecoveryCodes, { codes: r.codes, fresh: true });
    reload();
  };
  const turnOff = async () => {
    await api.del('/profile/two-step', p.version);
    toast('Two-step sign-in is off');
    reload();
  };
  const run = (/** @type {() => Promise<void>} */ fn) => act.run(fn).catch(() => {});
  const ts = p.twoStep;
  return html`
    <div class="card" id="two-step">
      <h3>Two-step sign-in ${ts.on
        ? html`<span class="pill ok">on</span>`
        : html`<span class="pill">off</span>`}</h3>
      <p class="small dim" style=${{ marginTop: 0 }}>${ts.on
        ? html`A code from your authenticator app after your password. ${ts.recoveryCodesLeft} recovery
          code${ts.recoveryCodesLeft === 1 ? '' : 's'} left.`
        : 'Ask for a code from an authenticator app on your phone after your password.'}</p>
      ${ts.on && ts.recoveryCodesLeft <= 3
        ? html`<div class="notice warn small">Make new recovery codes before they run out.</div>`
        : null}
      ${needPassword
        ? html`
          <${Field} label="Your password" id="two-step-password"
            hint="Asked again: it was over 10 minutes ago.">
            <${Input} type="password" value=${password} onInput=${setPassword}
              autocomplete="current-password" required />
            </${Field}>
        `
        : null}
      <${FormError} error=${act.error} />
      ${ts.on
        ? html`
          <button type="button" class="btn" disabled=${act.busy}
            onClick=${() =>
              run(newCodes)}>New recovery codes</button> <button type="button" class="btn danger"
            disabled=${act.busy} onClick=${() => run(turnOff)}>Turn off</button>
        `
        : html`<button type="button" class="btn" disabled=${act.busy} onClick=${() =>
          run(turnOn)}>Turn on</button>`}
    </div>
  `;
}

/**
 * Setting up: the QR code (or the key, typed by hand), then a code from the app to confirm,
 * then the recovery codes, shown once.
 * @param {{ close: (v?: any) => void, setup: { secret: string, uri: string, qrImage: string } }} props
 */
function TwoStepSetup({ close, setup }) {
  useDialogGuide('dialog-two-step');
  const [code, setCode] = useState('');
  const [codes, setCodes] = useState(/** @type {string[] | null} */ (null));
  const save = useSubmit(async () => {
    const r = await api.post('/profile/two-step/confirm', { code });
    setCodes(r.codes);
  });
  if (codes) {
    return html`<${RecoveryCodes} close=${() => close(true)} codes=${codes} fresh=${false} />`;
  }
  const key = setup.secret.replace(/(.{4})/g, '$1 ').trim();
  return html`
    <${Dialog} title="Turn on two-step sign-in" close=${close}
      onSubmit=${() => save.run().catch(() => {})}
      footer=${html`<button class="btn primary" disabled=${save.busy}>Turn on</button>`}>
      <ol class="steps small">
        <li>Open your authenticator app (any app that reads TOTP codes) and add an account.</li>
        <li>Scan this code, or type the key below it.</li>
        <li>Type the six-digit code the app shows.</li>
      </ol>
      <div class="qr"><img src=${setup.qrImage} width="180" height="180"
        alt="QR code for your authenticator app" /></div>
      <p class="small center"><span class="dim">Key:</span> <code class="key">${key}</code></p>
      <${Field} label="Code from the app" id="two-step-code" error=${errAt(save.error, 'code')}>
        <${Input} value=${code} onInput=${setCode} inputmode="numeric"
          autocomplete="one-time-code" maxlength="7" required />
        </${Field}>
        <${FormError} error=${save.error} shown=${['code']} />
        </${Dialog}>
  `;
}

/**
 * The ten recovery codes, shown once: each signs in once in place of a code from the app.
 * @param {{ close: (v?: any) => void, codes: string[], fresh: boolean }} props
 */
function RecoveryCodes({ close, codes, fresh }) {
  useDialogGuide('dialog-recovery-codes');
  const text = codes.join('\n') + '\n';
  return html`
    <${Dialog} title=${fresh ? 'New recovery codes' : 'Two-step sign-in is on'} close=${close}
      onSubmit=${() => close(true)}
      note="They won't be shown again."
      footer=${html`
        <button type="button" class="btn" onClick=${() =>
          navigator.clipboard?.writeText(text).then(() => toast('Copied'))}>Copy</button>
        <a class="btn" download="moneykata-recovery-codes.txt"
          href=${'data:text/plain;charset=utf-8,' + encodeURIComponent(text)}>Download</a>
        <button class="btn primary">I've saved them</button>
      `}>
      <p class="small">Keep these somewhere safe, away from your phone. Each one signs you in once
        in place of a code from the app${fresh ? ', and the old ones no longer work' : ''}.</p>
      <ul class="codes">${codes.map((c) => html`<li><code>${c}</code></li>`)}</ul>
      </${Dialog}>
  `;
}

/**
 * Assumptions (S6.3): the expected return and volatility of each asset class, inflation, and
 * the bitcoin model, shared by every projection of yours unless one overrides a figure.
 */
function Assumptions() {
  const res = useApi('/assumptions');
  const v = /** @type {any} */ (res.data);
  const [f, setF] = useState(/** @type {any} */ (null));
  useEffect(() => {
    if (v) setF(structuredClone(v.figures));
  }, [v]);
  const save = useSubmit(async () => {
    await api.put('/assumptions', f, v.version);
    toast('Saved · projections recompute when opened');
    res.reload();
  });
  if (!v || !f) return null;
  const e = save.error;
  const setClass = (/** @type {string} */ k, /** @type {string} */ field) =>
  (
    /** @type {string} */ x,
  ) => {
    const next = structuredClone(f);
    next.classes[k][field] = x === '' ? null : Number(x);
    setF(next);
  };
  return html`
    <form class="card mt" id="assumptions" onSubmit=${(/** @type {Event} */ ev) => {
      ev.preventDefault();
      save.run().catch(() => {});
    }}>
      <h3>Assumptions<span class="spacer"></span><span class="small dim" style=${{
        fontWeight: 400,
      }}>used by all your projections</span></h3>
      <table class="t">
        <thead>
          <tr>
            <th>Asset class</th>
            <th class="num">Expected return %</th>
            <th
              class="num">Volatility %</th>
          </tr>
        </thead>
        <tbody>${v.classes.map(([k, label]) =>
          html`
            <tr>
              <td>${label}</td>
              <td class="num"><input class="in num" style=${{
                maxWidth: '90px',
              }} data-help="expected-return"
                          aria-label=${label + ' expected return'} value=${f.classes[k].return ??
                            ''}
                          onInput=${(/** @type {any} */ ev) =>
                            setClass(k, 'return')(ev.currentTarget.value)} />${errAt(
                              e,
                              `classes.${k}.return`,
                            )
                            ? html`<div class="err">${errAt(e, `classes.${k}.return`)}</div>`
                            : null}</td>
              <td class="num"><input class="in num" style=${{
                maxWidth: '90px',
              }} data-help="volatility"
                          aria-label=${label + ' volatility'} value=${f.classes[k].volatility ?? ''}
                          onInput=${(/** @type {any} */ ev) =>
                            setClass(k, 'volatility')(ev.currentTarget.value)} /></td>
            </tr>
          `
        )}</tbody>
      </table>
      <div class="row mt">
        <${Field} label="General inflation (%)" id="general-inflation" error=${errAt(
          e,
          'inflation',
        )}>
          <${Input} value=${f.inflation} inputmode="decimal" onInput=${(/** @type {string} */ x) =>
            setF({ ...f, inflation: Number(x) })} />
          </${Field}>
          <${Field} label="Education inflation (%)" id="education-inflation"
            error=${errAt(e, 'educationInflation')}>
            <${Input} value=${f.educationInflation} inputmode="decimal" onInput=${(
              /** @type {string} */ x,
            ) => setF({ ...f, educationInflation: Number(x) })} />
            </${Field}>
            </div>
            <${Field} label="Bitcoin model" id="bitcoin-model"
              hint="For the bitcoin in your projections; other coins use the crypto row.">
              <${Select} value=${f.bitcoinModel} onChange=${(/** @type {string} */ x) =>
                setF({ ...f, bitcoinModel: x })} options=${v.bitcoinModels} />
              </${Field}>
              <${FormError} error=${e} />
              <div class="toolbar"><button class="btn primary" disabled=${save.busy}>Save</button>
        <button type="button" class="linklike" onClick=${() =>
          openDialog(BitcoinModels, {})}>Compare models</button></div>
              </form>
  `;
}

const MODEL_NAMES = /** @type {Record<string, string>} */ ({
  powerLaw: 'Power law',
  logRegression: 'Log regression',
  stockToFlow: 'Stock-to-flow',
  saylor: 'Saylor base',
  ark: 'ARK base',
});

/** Compare models (S6.3.1.1): their median paths and figures, with their sources and records. */
function BitcoinModels({ close }) {
  useDialogGuide('dialog-bitcoin-models');
  const res = useApi('/bitcoin-models');
  const v = /** @type {any} */ (res.data);
  const fmt = (/** @type {any} */ x, n = num(x)) =>
    n >= 1e9
      ? `$${(n / 1e9).toFixed(1)}B`
      : n >= 1e6
      ? `$${(n / 1e6).toFixed(1)}M`
      : `$${Math.round(n / 1e3)}K`;
  return html`
    <${Dialog} title="Bitcoin models" wide close=${close} footer=${html`
      <button type="button"
        class="btn" onClick=${() => close()}>Close</button>
    `}>
      ${v
        ? html`
          <p class="small dim"
            style=${{ marginTop: 0 }}>Each model's median path from today's price${v.price
              ? ` (${fmt(v.price)})`
              : ''}, on a log scale. These are models other people publish, shown so you can compare them,
            not MoneyKata's view or advice.</p>
          <${ModelsChart} rows=${v.rows} names=${MODEL_NAMES} />
          <div class="table-wrap mt">
            <table class="t">
              <thead>
                <tr>
                  <th>Model</th>
                  <th class="num">2030</th>
                  <th class="num">2035</th>
                  <th class="num">2045</th>
                  <th>Source and record</th>
                </tr>
              </thead>
              <tbody>${v.rows.map((/** @type {any} */ r) =>
                html`<tr><td>${MODEL_NAMES[r.model]}</td>${
                  [2030, 2035, 2045].map((y) => html`<td class="num">${fmt(r.at[y])}</td>`)
                }<td class="small dim">${r.record}</td></tr>`
              )}</tbody>
            </table>
          </div>
          <p
            class="small dim">Their figures ship with MoneyKata, dated, in Settings › Tax tables (${v
              .figuresYear}).</p>
        `
        : html`<p class="dim">Loading…</p>`}
    </${Dialog}>
  `;
}
