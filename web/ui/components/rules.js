// Categorisation and payee rules (requirements S2.7): Transactions › Rules lists a user's own
// rules, first match wins, and edits them one at a time; applied on import and on demand.
import { useState } from 'preact/hooks';
import { html } from '../app/html.js';
import { api } from '../api/client.js';
import { useApi, useList, useSubmit } from '../app/hooks.js';
import { money } from '../app/format.js';
import { Dialog, openDialog } from './dialog.js';
import { useDialogGuide } from './help.js';
import { errAt, Field, FormError, Input, Select } from './fields.js';
import { Failed, Loading } from './bits.js';
import { Icon } from './icon.js';
import { toast } from './toast.js';

const clean = (/** @type {string} */ s) => (s ? String(s).replace(/[$,\s]/g, '') : '');
const DIRECTIONS = [['any', 'Money in or out'], ['out', 'Money out'], ['in', 'Money in']];

/**
 * The list, and the editor in turn: one dialog at a time, so editing closes the list and
 * opens it again after.
 * @param {any} [start]  a rule to make first, filled from a transaction
 */
export async function openRules(start) {
  let edit = start ? { rule: null, fill: start } : null;
  for (;;) {
    if (edit) {
      await openDialog(RuleDialog, edit);
      edit = null;
    }
    const next = await openDialog(RulesDialog, {});
    if (!next) return;
    edit = next;
  }
}

/** @param {any} r */
function when(r) {
  const parts = [r.payeeMatch.toLowerCase().startsWith('re:') ? r.payeeMatch : `“${r.payeeMatch}”`];
  if (r.amountMin != null || r.amountMax != null) {
    parts.push(
      r.amountMin != null && r.amountMax != null
        ? `${money(r.amountMin)}–${money(r.amountMax)}`
        : r.amountMin != null
        ? `${money(r.amountMin)} or more`
        : `up to ${money(r.amountMax)}`,
    );
  }
  if (r.direction !== 'any') parts.push(r.direction === 'in' ? 'money in' : 'money out');
  if (r.accountId) parts.push(`in ${r.accountName}${r.accountDeleted ? ' (deleted)' : ''}`);
  return parts.join(' · ');
}

/** @param {any} r */
function sets(r) {
  const parts = [];
  if (r.categoryId) parts.push(`${r.categoryPath}${r.categoryDeleted ? ' (deleted)' : ''}`);
  if (r.payee) parts.push(`shown as ${r.payee}`);
  if (r.tags.length) parts.push(r.tags.map((/** @type {string} */ t) => `#${t}`).join(' '));
  return parts.join(' · ');
}

/** @param {{ close: (v?: any) => void }} p */
function RulesDialog({ close }) {
  useDialogGuide('dialog-rules');
  const res = useApi('/rules');
  const v = /** @type {any} */ (res.data);
  const [armed, setArmed] = useState(/** @type {string | null} */ (null));
  const act = useSubmit(async (/** @type {() => Promise<any>} */ f) => {
    await f();
    setArmed(null);
    res.reload();
  });
  const apply = useSubmit(async () => {
    const r = await api.post('/rules/apply', {});
    toast(r.changed === 1 ? 'Set 1 transaction' : `Set ${r.changed} transactions`);
    close();
  });
  const move = (/** @type {any} */ r, /** @type {number} */ to) =>
    act.run(() => api.post(`/rules/${r.id}/move`, { to })).catch(() => {});
  const rows = v ? /** @type {any[]} */ (v.items) : null;
  return html`
    <${Dialog} title="Categorisation rules" wide close=${close}
      onSubmit=${() => apply.run().catch(() => {})}
      footer=${html`
        <button type="button" class="btn" onClick=${() => close({ rule: null })}><${Icon}
          name="plus" /> Add a rule</button>
        <span class="spacer" style=${{ flex: 1 }}></span>
        <button type="button" class="btn" onClick=${() => close()}>Close</button>
        <button class="btn primary" disabled=${!v?.uncategorised || apply.busy}>${v?.uncategorised
          ? `Apply to ${v.uncategorised} uncategorised`
          : 'Nothing uncategorised to set'}</button>
      `}>
      <p class="small dim" style=${{ marginTop: 0 }} data-help="first-match">First match wins, top
        to bottom. Applied to what you import, and to the uncategorised when you choose.</p>
      ${res.error
        ? html`<${Failed} error=${res.error} />`
        : !rows
        ? html`<${Loading} lines=${3} />`
        : !rows.length
        ? html`<p class="small dim">No rules yet. <b>Add a rule</b>, or <b>Make a rule</b> from a
          transaction.</p>`
        : html`
          <div class="table-wrap">
            <table class="t">
              <thead>
                <tr>
                  <th>#</th>
                  <th>When</th>
                  <th
                  >Then</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>${rows.map((r, i) =>
                html`
                  <tr>
                    <td class="dim">${i + 1}</td>
                    <td>${when(r)}</td>
                    <td>${sets(r)}</td>
                    <td
                      style=${{ whiteSpace: 'nowrap', textAlign: 'right' }}>
                      <button type="button" class="btn sm" aria-label=${`Move rule ${i + 1} up`}
                        disabled=${i === 0 || act.busy} onClick=${() => move(r, i - 1)}>↑</button>
                      <button type="button" class="btn sm" aria-label=${`Move rule ${i + 1} down`}
                        disabled=${i === rows.length - 1 || act.busy} onClick=${() =>
                          move(r, i + 1)}>↓</button>
                      <button type="button" class="btn sm" onClick=${() =>
                        close({ rule: r })}>Edit…</button>
                      <button type="button" class="btn sm danger" disabled=${act.busy}
                        onClick=${() =>
                          armed === r.id
                            ? act.run(() => api.del(`/rules/${r.id}`, r.version)).catch(() => {})
                            : setArmed(r.id)}>${armed === r.id
                          ? 'Click again to delete'
                          : 'Delete'}</button>
                    </td>
                  </tr>
                `
              )}</tbody>
            </table>
          </div>
        `}
      <${FormError} error=${act.error || apply.error} />
    </${Dialog}>
  `;
}

/** @param {{ close: (v?: any) => void, rule: any, fill?: any }} p */
function RuleDialog({ close, rule, fill }) {
  useDialogGuide('dialog-rule');
  const accounts = useList('/accounts');
  const cats = useList('/categories');
  const r = rule || {};
  const [f, setF] = useState({
    payeeMatch: r.payeeMatch ?? fill?.payeeMatch ?? '',
    amountMin: r.amountMin ?? '',
    amountMax: r.amountMax ?? '',
    direction: r.direction ?? 'any',
    accountId: r.accountId ?? '',
    categoryId: r.categoryId ?? fill?.categoryId ?? '',
    payee: r.payee ?? '',
    tags: (r.tags || []).join(', '),
  });
  const set = (/** @type {string} */ k) => (/** @type {any} */ x) => setF({ ...f, [k]: x });
  const save = useSubmit(async () => {
    const body = {
      payeeMatch: f.payeeMatch,
      amountMin: clean(f.amountMin) || null,
      amountMax: clean(f.amountMax) || null,
      direction: f.direction,
      accountId: f.accountId || null,
      categoryId: f.categoryId || null,
      payee: f.payee || null,
      tags: f.tags.split(',').map((/** @type {string} */ x) => x.trim()).filter(Boolean),
    };
    if (rule) await api.patch(`/rules/${rule.id}`, body, rule.version);
    else await api.post('/rules', body);
    toast(rule ? 'Rule saved' : 'Rule added');
    close(true);
  });
  const e = save.error;
  const writable = (/** @type {any[]} */ (accounts.data) || []).filter((a) => a.level !== 'read');
  return html`
    <${Dialog} title=${rule ? 'Edit a rule' : 'New rule'} close=${close}
      onSubmit=${() => save.run().catch(() => {})}
      footer=${html`
        <button type="button" class="btn" onClick=${() =>
          close()}>Cancel</button><button class="btn primary"
          disabled=${save.busy}>${rule ? 'Save' : 'Add the rule'}</button>
      `}>
      <${Field} label="Payee contains" error=${errAt(e, 'payeeMatch')}
        hint="As the bank writes it; case doesn't matter. re: starts a regular expression.">
        <${Input} value=${f.payeeMatch} onInput=${set('payeeMatch')} required
          placeholder="WHOLE FOODS, or re:^AMZN" />
        </${Field}>
        <div class="row">
          <${Field} label="Amount from" error=${errAt(e, 'amountMin')}>
            <${Input} value=${f.amountMin} onInput=${set('amountMin')} inputmode="decimal"
              placeholder="any" />
            </${Field}>
            <${Field} label="Amount to" error=${errAt(e, 'amountMax')}>
              <${Input} value=${f.amountMax} onInput=${set('amountMax')} inputmode="decimal"
                placeholder="any" />
              </${Field}>
              </div>
              <div class="row">
                <${Field} label="Direction" error=${errAt(e, 'direction')}>
                  <${Select} value=${f.direction} onChange=${set(
                    'direction',
                  )} options=${DIRECTIONS} />
                  </${Field}>
                  <${Field} label="Account" error=${errAt(e, 'accountId')}>
                    <${Select} value=${f.accountId} onChange=${set('accountId')} options=${[
                      ['', 'Any account'],
                      ...writable.map((a) => [a.id, a.name]),
                    ]} />
                    </${Field}>
                    </div>
                    <${Field} label="Category" error=${errAt(e, 'categoryId')}>
                      <${Select} value=${f.categoryId} onChange=${set('categoryId')} options=${[
                        ['', 'Leave it as it is'],
                        ...(/** @type {any[]} */ (cats.data) || []).map((c) => [c.id, c.path]),
                      ]} />
                      </${Field}>
                      <${Field} label="Rename to" error=${errAt(e, 'payee')}
                        hint="The payee shown; the bank's text is kept beside it.">
                        <${Input} value=${f.payee} onInput=${set('payee')}
                          placeholder="leave the payee" />
                        </${Field}>
                        <${Field} label="Tags" error=${errAt(e, 'tags')}
                          hint="Your own, separated by commas.">
                          <${Input} value=${f.tags} onInput=${set('tags')}
                            placeholder="coffee, work" />
                          </${Field}>
                          <${FormError} error=${e} shown=${[
                            'payeeMatch',
                            'amountMin',
                            'amountMax',
                            'direction',
                            'accountId',
                            'categoryId',
                            'payee',
                            'tags',
                          ]} />
                          </${Dialog}>
  `;
}
