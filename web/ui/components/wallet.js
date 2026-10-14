// A self-custody wallet's keys and addresses (requirements S1.6.1, S1.6.3): extended public keys
// (xpub, ypub, zpub) or addresses, never a private key or seed phrase. Text that looks like one
// is cleared from the form at once, before anything is sent; the server checks again.
import { useState } from 'preact/hooks';
import { html } from '../app/html.js';
import { api } from '../api/client.js';
import { useApi, useSubmit } from '../app/hooks.js';
import { ago } from '../app/format.js';
import { errAt, Field, FormError, Input } from './fields.js';
import { Failed, Loading } from './bits.js';
import { toast } from './toast.js';

export const WALLET_FIELDS = ['text', 'gapLimit'];
const SCRIPT = /** @type {Record<string, string>} */ ({
  p2pkh: 'legacy (1…)',
  'p2sh-p2wpkh': 'nested segwit (3…)',
  p2sh: 'script (3…)',
  p2wpkh: 'native segwit (bc1q…)',
  p2wsh: 'segwit script (bc1q…)',
  p2tr: 'taproot (bc1p…)',
});

/**
 * What secret the text looks like, if any: the same shapes the server refuses.
 * @param {string} text
 */
export function looksSecret(text) {
  const words = text.trim().toLowerCase().split(/\s+/).filter(Boolean);
  if (words.length >= 12 && words.every((w) => /^[a-z]{3,8}$/.test(w))) return 'seed phrase';
  for (const tok of text.split(/[\s,]+/)) {
    if (/^[0-9a-fA-F]{64}$/.test(tok)) return 'private key (64 hex digits)';
    if (/^[xyztuv]prv/.test(tok)) return 'extended private key';
    if (/^[5KLc9][1-9A-HJ-NP-Za-km-z]{50,51}$/.test(tok)) return 'private key (WIF)';
  }
  return null;
}

/** @param {string} what */
const refusal = (what) =>
  `That looks like a ${what}. MoneyKata never accepts one, and nothing was saved: enter an extended public key (xpub, ypub or zpub) or addresses instead.`;

/**
 * The keys box and gap limit, in the New account form and the wallet's Settings.
 * @param {{ f: any, set: (k: string) => (v: any) => void, e: any }} p
 */
export function WalletFields({ f, set, e }) {
  const [refused, setRefused] = useState(/** @type {string | null} */ (null));
  const onText = (/** @type {any} */ ev) => {
    const v = ev.currentTarget.value;
    const what = looksSecret(v);
    if (what) {
      ev.currentTarget.value = '';
      set('walletText')('');
      setRefused(refusal(what));
    } else {
      setRefused(null);
      set('walletText')(v);
    }
  };
  return html`
    <${Field} label="Extended public keys or addresses" id="wallet-keys" error=${refused ||
      errAt(e, 'text')}
      hint="An xpub, ypub or zpub, or addresses, one a line. Public data only.">
      <textarea class="in mono" rows="3" value=${f.walletText} onInput=${onText}
        placeholder="zpub6r…, or bc1q… one a line" spellcheck="false" autocomplete="off"></textarea>
      </${Field}>
      <${Field} label="Gap limit" error=${errAt(e, 'gapLimit')}
        hint="Addresses derived past the last one used. 20 suits most wallets.">
        <${Input} value=${f.gapLimit} onInput=${set('gapLimit')} inputmode="numeric" />
        </${Field}>
  `;
}

/** @param {any} f */
export const walletBody = (f) => ({ text: f.walletText, gapLimit: Number(f.gapLimit) || 20 });

/** The wallet's keys and the addresses it watches, on its Settings tab. */
/** @param {{ a: any }} p */
export function WalletCard({ a }) {
  const res = useApi(`/accounts/${a.id}/wallet`);
  const v = /** @type {any} */ (res.data);
  if (res.error) return html`<${Failed} error=${res.error} />`;
  if (!v) {
    return html`
      <div class="card">
        <${Loading} lines=${4} />
      </div>
    `;
  }
  return html`<${WalletForm} a=${a} v=${v} reload=${res.reload} />`;
}

/** @param {{ a: any, v: any, reload: () => void }} p */
function WalletForm({ a, v, reload }) {
  const owner = ['owner', 'write'].includes(a.level);
  const [f, setF] = useState({
    walletText: v.keys.map((/** @type {any} */ k) => k.value).join('\n'),
    gapLimit: String(v.keys[0]?.gapLimit || 20),
  });
  const set = (/** @type {string} */ k) => (/** @type {any} */ x) =>
    setF((o) => ({ ...o, [k]: x }));
  const save = useSubmit(async () => {
    await api.put(`/accounts/${a.id}/wallet`, walletBody(f));
    toast('Saved');
    reload();
  });
  const e = save.error;
  return html`
    <form class="card" onSubmit=${(/** @type {Event} */ ev) => {
      ev.preventDefault();
      save.run().catch(() => {});
    }}>
      <h3>Keys and addresses</h3>
      ${owner ? html`<${WalletFields} f=${f} set=${set} e=${e} />` : null}
      <p class="small dim" data-help="watched">${v.watched} addresses watched, ${v.used} used${v
          .checkedAt
        ? `, last checked ${ago(v.checkedAt)}`
        : ': not checked yet. Balances come from the explorer or node in Settings › Bitcoin.'}</p>
      ${v.keys.map((/** @type {any} */ k) =>
        html`
          <div class="list-item">
            <div
              class="grow"><span class="mono small">${k.value.length > 40
                ? k.value.slice(0, 12) + '…' + k.value.slice(-8)
                : k.value}</span><div class="small dim">${k.kind === 'xpub'
                ? `Extended public key · ${SCRIPT[k.script] || k.script} · ${k.addresses} addresses`
                : `Address · ${SCRIPT[k.script] || k.script}`}</div></div>
          </div>
        `
      )}
      ${v.addresses.length
        ? html`
          <details class="mt">
            <summary class="small">Addresses</summary>
            <div class="table-wrap">
              <table class="t">
                <caption class="sr-only">Addresses watched</caption>
                <thead>
                  <tr>
                    <th>Address</th>
                    <th>Chain</th>
                    <th class="num">Transactions</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>${v.addresses.map((/** @type {any} */ r) =>
                  html`
                    <tr>
                      <td class="mono small">${r.address}</td>
                      <td class="small dim">${r.chain ===
                          0
                        ? `receive ${r.index}`
                        : r.chain === 1
                        ? `change ${r.index}`
                        : 'typed'}</td>
                      <td class="num">${r.txCount}</td>
                      <td>${r.used ? html`<span class="pill">used</span>` : null}</td>
                    </tr>
                  `
                )}</tbody>
              </table>
            </div>
          </details>
        `
        : null}
      <${FormError} error=${e} shown=${WALLET_FIELDS} />
      ${owner
        ? html`<div class="toolbar mt"><span class="spacer"></span><button class="btn primary"
          disabled=${save.busy}>Save</button></div>`
        : null}
    </form>
  `;
}
