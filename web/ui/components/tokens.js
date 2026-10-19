// Profile › Access tokens (requirements S10.9.1): tokens an AI assistant uses to read, never
// change, what you can see through the MCP endpoint. Each is shown once, when it is made.
import { useState } from 'preact/hooks';
import { html } from '../app/html.js';
import { api } from '../api/client.js';
import { useList, useSubmit } from '../app/hooks.js';
import { ago, day } from '../app/format.js';
import { Dialog, openDialog } from './dialog.js';
import { useDialogGuide } from './help.js';
import { errAt, Field, FormError, Input, Select } from './fields.js';
import { Failed, Loading } from './bits.js';
import { Icon } from './icon.js';
import { withReauth } from './reauth.js';
import { toast } from './toast.js';

const endpoint = () => `${location.origin}/mcp`;

export function AccessTokens() {
  const res = useList('/profile/tokens');
  const rows = /** @type {any[]} */ (res.data);
  const [armed, setArmed] = useState(/** @type {string | null} */ (null));
  const revoke = useSubmit(async (/** @type {any} */ t) => {
    await api.del(`/profile/tokens/${t.id}`, t.version);
    toast(`${t.name}: revoked`);
    setArmed(null);
    res.reload();
  });
  const make = () =>
    openDialog(NewToken, {}).then((made) => {
      if (!made) return;
      res.reload();
      openDialog(TokenShown, { made });
    });
  return html`
    <div class="card" id="access-tokens">
      <h3 data-help="access-tokens">Access tokens<span class="spacer"></span><button class="btn sm"
        onClick=${make}><${Icon} name="plus" /> New token</button></h3>
      <p class="small dim" style=${{ marginTop: '-6px' }}>Let an AI assistant read, never change,
        what you can see, through MCP at <code>${endpoint()}</code>.</p>
      ${res.error
        ? html`<${Failed} error=${res.error} />`
        : !rows
        ? html`<${Loading} lines=${2} />`
        : !rows.length
        ? html`<p class="small dim">None yet.</p>`
        : rows.map((t) =>
          html`
            <div
              class="list-item"><div class="grow"><b>${t.name}</b><div class="small dim">${t
                  .scope === 'all'
                ? 'everything I can see'
                : t.items.map((/** @type {any} */ i) => i.name).join(', ')} · ${t.expired
                ? html`<span class="pill warn">expired</span>`
                : `expires ${day(t.expiresAt)}`} · ${t.lastUsedAt
                ? `last used ${ago(t.lastUsedAt)}`
                : 'never used'}</div></div><button class="btn sm danger" disabled=${revoke.busy}
                        onClick=${() =>
                          armed === t.id
                            ? revoke.run(t).catch(() => {})
                            : setArmed(t.id)}>${armed === t.id
                          ? 'Click again to revoke'
                          : 'Revoke'}</button></div>
          `
        )}
    </div>
  `;
}

/** @param {{ close: (v?: any) => void }} p */
function NewToken({ close }) {
  useDialogGuide('dialog-new-token');
  const accounts = useList('/accounts');
  const portfolios = useList('/portfolios');
  const [f, setF] = useState({ name: '', scope: 'all', days: '90' });
  const [picked, setPicked] = useState(/** @type {Record<string, boolean>} */ ({}));
  const set = (/** @type {string} */ k) => (/** @type {any} */ x) => setF({ ...f, [k]: x });
  const items = [
    ...(/** @type {any[]} */ (accounts.data) || []).map((a) => ({
      kind: 'account',
      id: a.id,
      name: a.name,
    })),
    ...(/** @type {any[]} */ (portfolios.data) || []).map((p) => ({
      kind: 'portfolio',
      id: p.id,
      name: `${p.name} (portfolio)`,
    })),
  ];
  const save = useSubmit(async () => {
    const made = await withReauth(() =>
      api.post('/profile/tokens', {
        name: f.name,
        scope: f.scope,
        days: Number(f.days),
        items: items.filter((i) => picked[i.kind + i.id]).map((i) => ({ kind: i.kind, id: i.id })),
      })
    );
    close(made);
  });
  const e = save.error;
  return html`
    <${Dialog} title="New access token" close=${close} onSubmit=${() => save.run().catch(() => {})}
      footer=${html`<button class="btn primary" disabled=${save.busy}>Create token</button>`}>
      <p class="small dim" style=${{ marginTop: 0 }}>For an AI assistant or another tool that
        speaks MCP. It can read, never change, and only what you choose here.</p>
      <${Field} label="Token name" error=${errAt(e, 'name')}>
        <${Input} value=${f.name} onInput=${set('name')} placeholder="Claude on my laptop"
          required />
        </${Field}>
        <${Field} label="Can read" error=${errAt(e, 'scope') || errAt(e, 'items')}
          hint="Never secrets, Settings or linked households.">
        <${Select} value=${f.scope} onChange=${set('scope')} options=${[
          ['all', 'Everything I can see'],
          ['chosen', 'Chosen items…'],
        ]} />
      </${Field}>
      ${f.scope === 'chosen'
        ? html`<div class="field" data-help="chosen-items" style=${{
          maxHeight: '220px',
          overflow: 'auto',
        }}>${
          items.map((i) =>
            html`<label class="list-item" style=${{ cursor: 'pointer' }}><input type="checkbox"
              checked=${!!picked[i.kind + i.id]} onChange=${(/** @type {any} */ ev) =>
              setPicked({ ...picked, [i.kind + i.id]: ev.currentTarget.checked })} /><span
              class="grow">${i.name}</span></label>`
          )
        }</div>`
        : null}
      <${Field} label="Expires" error=${errAt(e, 'days')}>
        <${Select} value=${f.days} onChange=${set('days')} options=${[
          ['30', 'In 30 days'],
          ['90', 'In 90 days'],
          ['365', 'In a year'],
        ]} />
      </${Field}>
      <${FormError} error=${e} shown=${['name', 'scope', 'items', 'days']} />
    </${Dialog}>
  `;
}

/** @param {{ close: (v?: any) => void, made: any }} p */
function TokenShown({ close, made }) {
  useDialogGuide('dialog-token-shown');
  return html`
    <${Dialog} title="Your new access token" close=${close} onSubmit=${() => close(true)}
      note="It is shown once and can't be shown again."
      footer=${html`
        <button type="button" class="btn" onClick=${() =>
          navigator.clipboard?.writeText(made.secret).then(() => toast('Copied'))}>Copy</button>
        <button class="btn primary">Done</button>
      `}>
      <div class="notice" style=${{ marginBottom: '12px' }}>
        <${Icon} name="alert" />
        <div>Copy it
        now. Anyone with it can read what it can until it expires or you revoke it.</div>
      </div>
      <div class="field"
        data-help="token"><label>Token</label><code class="mono" style=${{
          display: 'block',
          padding: '10px 12px',
          background: 'var(--bg-3)',
          borderRadius: '8px',
        }}>${made.secret}</code></div>
      <p class="small dim">Use it with the MCP endpoint <code>${endpoint()}</code>, as a bearer
        token: <code>Authorization: Bearer mkt_…</code>.</p>
      </${Dialog}>
  `;
}
