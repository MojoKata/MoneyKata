// Making or changing a portfolio (requirements S5.1): its name, accounts and benchmark.
import { useState } from 'preact/hooks';
import { html } from '../app/html.js';
import { api } from '../api/client.js';
import { useList, useSubmit } from '../app/hooks.js';
import { Dialog } from '../components/dialog.js';
import { useDialogGuide } from '../components/help.js';
import { errAt, Field, FormError, Input, Select } from '../components/fields.js';
import { toast } from '../components/toast.js';

export const BENCHMARKS = /** @type {[string, string][]} */ ([
  ['VT', 'VT (world stocks)'],
  ['SPY', 'SPY (US large companies)'],
  ['60-40', '60/40: VT and BND'],
]);

/** @param {{ close: (v?: any) => void, portfolio?: any }} p */
export function PortfolioDialog({ close, portfolio }) {
  useDialogGuide('dialog-portfolio');
  const accounts = useList('/accounts');
  const [name, setName] = useState(portfolio?.name || '');
  const [benchmark, setBenchmark] = useState(portfolio?.benchmark || 'VT');
  const [ids, setIds] = useState(/** @type {Set<string>} */ (new Set(portfolio?.accountIds || [])));
  const save = useSubmit(async () => {
    const body = { name, benchmark, accountIds: [...ids] };
    const out = portfolio
      ? await api.patch(`/portfolios/${portfolio.id}`, body, portfolio.version)
      : await api.post('/portfolios', body, { idempotent: true });
    toast('Saved');
    close(out);
  });
  const list = /** @type {any[]} */ (accounts.data) || [];
  return html`
    <${Dialog} title=${portfolio ? 'Portfolio' : 'New portfolio'} close=${close}
      onSubmit=${() =>
        save.run().catch(
          () => {},
        )} footer=${html`<button class="btn primary" disabled=${save.busy}>Save</button>`}>
      <${Field} label="Name" error=${errAt(save.error, 'name')}>
        <${Input} value=${name} onInput=${setName} required />
        </${Field}>
        <fieldset class="field"
          style=${{ border: 0, padding: 0, margin: '0 0 14px' }}><legend class="small" style=${{
            color: 'var(--fg-dim)',
          }}>Accounts</legend>
          ${list.map((a) =>
            html`<label class="list-item" style=${{ cursor: 'pointer' }}><input type="checkbox"
        checked=${ids.has(a.id)} onChange=${() => {
              const next = new Set(ids);
              next.has(a.id) ? next.delete(a.id) : next.add(a.id);
              setIds(next);
            }} /><span class="grow">${a.name} <span class="small dim">${
              a.institution || ''
            }</span></span>${
              a.level !== 'owner' ? html`<span class="pill">shared</span>` : null
            }</label>`
          )}
          ${errAt(save.error, 'accountIds')
            ? html`<div class="err">${errAt(save.error, 'accountIds')}</div>`
            : null}
        </fieldset>
        <${Field} label="Benchmark"
          hint="What Performance compares it with, given the same money at the same times.">
          <${Select}
            value=${benchmark} onChange=${setBenchmark} options=${BENCHMARKS} />
          </${Field}>
          <${FormError} error=${save.error} shown=${['name', 'accountIds', 'benchmark']} />
          </${Dialog}>
  `;
}
