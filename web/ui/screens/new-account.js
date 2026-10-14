// New account (requirements S12.2.2): a type picker, then the account form.
import { useState } from 'preact/hooks';
import { useLocation } from 'preact-iso';
import { html } from '../app/html.js';
import { api } from '../api/client.js';
import { useSubmit } from '../app/hooks.js';
import { Dialog } from '../components/dialog.js';
import { useDialogGuide } from '../components/help.js';
import { errAt, Field, FormError, Input, Select } from '../components/fields.js';
import { Tile } from '../components/bits.js';
import { toast } from '../components/toast.js';
import { BY_TYPE, TYPES } from '../account-types/index.js';
import { TERM_FIELDS, termsBody, TermsFields, termsForm } from '../components/loan.js';
import { PLAN_FIELDS, planBody, PlanFields, planForm } from '../components/edu.js';

export const LOT_METHODS = /** @type {[string, string][]} */ ([
  ['fifo', 'FIFO (first in, first out)'],
  ['lifo', 'LIFO (last in, first out)'],
  ['hifo', 'HIFO (highest cost first)'],
  ['specific', 'Specific identification'],
  ['average', 'Average cost'],
]);
export const KEPT_BY = /** @type {[string, string][]} */ ([
  ['file', 'File import (OFX, QFX or CSV)'],
  ['manual', 'Manual'],
]);

/** @param {{ close: (v?: any) => void }} p */
export function NewAccount({ close }) {
  const [type, setType] = useState(/** @type {string | null} */ (null));
  useDialogGuide(type ? 'dialog-account-form' : 'dialog-new-account');
  if (!type) {
    return html`
      <${Dialog} title="New account" wide close=${close} footer=${null}>
        <p class="small dim" style=${{
          marginTop: 0,
        }}>Choose the type. It decides the fields, the tax
              treatment and how the account can be kept current.</p>
        <div class="type-grid">${TYPES.map((t) =>
          html`<button type="button" class="type-card" onClick=${() => setType(t.type)}>
          <${Tile} group=${t.group} icon=${t.icon} /><div style=${{
            textAlign: 'left',
          }}><div>${t.label}</div>
          <div class="sub">${t.hint}</div></div></button>`
        )}</div>
        </${Dialog}>
    `;
  }
  return html`<${AccountForm} type=${type} close=${close} back=${() => setType(null)} />`;
}

/** @param {{ type: string, close: (v?: any) => void, back: () => void }} p */
function AccountForm({ type, close, back }) {
  const { route } = useLocation();
  const t = BY_TYPE[type];
  const [f, setF] = useState({
    name: '',
    institution: '',
    mask: '',
    keptBy: 'file',
    lotMethod: 'fifo',
    openingBalance: '',
    openingDate: '',
    ...termsForm(null, type),
    ...planForm(null),
  });
  const set = (/** @type {string} */ k) => (/** @type {string} */ v) => setF({ ...f, [k]: v });
  const [made, setMade] = useState(/** @type {any} */ (null));
  const save = useSubmit(async () => {
    const body = {
      name: f.name,
      type,
      institution: f.institution || null,
      mask: f.mask || null,
      keptBy: [f.keptBy],
      lotMethod: f.lotMethod,
      openingBalance: f.openingBalance ? f.openingBalance.replace(/[$,\s]/g, '') : null,
      openingDate: f.openingDate || null,
    };
    if (t.loan || t.physical) {
      Object.assign(body, { keptBy: ['manual'], openingBalance: null, openingDate: null });
    }
    // A loan is made, then given its terms; a refusal of the terms keeps the account made.
    const a = made || await api.post('/accounts', body, { idempotent: true });
    if (t.loan) {
      setMade(a);
      await api.put(`/accounts/${a.id}/loan`, termsBody(f));
    }
    if (t.education) {
      setMade(a);
      await api.put(`/accounts/${a.id}/plan529`, await planBody(f));
    }
    toast(`${a.name} made`);
    close(a);
    route(`/ui/accounts/${a.id}`);
  });
  const e = save.error;
  return html`
    <${Dialog} title=${`New ${t.label} account`} close=${close} onSubmit=${() =>
      save.run().catch(() => {})} footer=${html`
      <button type="button" class="btn" onClick=${back}>Back</button>
      <button class="btn primary" disabled=${save.busy}>Create</button>
    `}>
      <${Field} label="Name" error=${errAt(e, 'name')}>
        <${Input} value=${f.name} onInput=${set('name')}
          placeholder=${t.investing
            ? 'Individual brokerage'
            : t.loan
            ? t.label
            : 'Everyday checking'} required />
        </${Field}>
        <div class="row">
          <${Field} label="Institution" error=${errAt(e, 'institution')}>
            <${Input} value=${f.institution}
              onInput=${set('institution')} placeholder="The bank or broker" />
            </${Field}>
            <${Field} label="Last 4" id="mask" error=${errAt(e, 'mask')}>
              <${Input} value=${f.mask}
                onInput=${set('mask')} inputmode="numeric" placeholder="4821" />
              </${Field}>
              </div>
              ${t.education ? html`<${PlanFields} f=${f} set=${set} e=${e} />` : null}
              ${t.loan
                ? html`<${TermsFields} f=${f} set=${set} e=${e} type=${type} />`
                : t.physical
                ? html`<p class="small dim">Add the items after making the account, each with its
                  purchase date, cost basis, notes and documents.</p>`
                : html`
                  <${Field} label="Keep it current by" id="kept-by" error=${errAt(
                    e,
                    'keptBy',
                  )}><${Select}
                    value=${f.keptBy} onChange=${set('keptBy')} options=${KEPT_BY} /></${Field}>
                  ${t.investing
                    ? html`
                      <${Field} label="Lot method" error=${errAt(e, 'lotMethod')}
                        hint="How sales pick lots. The method in force at a sale is recorded with it.">
                        <${Select}
                          value=${f.lotMethod} onChange=${set(
                            'lotMethod',
                          )} options=${LOT_METHODS} />
                        </${Field}>
                    `
                    : null}
                  <div class="row">
                    <${Field} label="Opening balance" error=${errAt(e, 'openingBalance')}
                      hint="Optional. Without it, the first imported balance stands in."><${Input}
                      value=${f.openingBalance} onInput=${set(
                        'openingBalance',
                      )} inputmode="decimal" placeholder="0.00" /></${Field}>
                    <${Field} label="Opening balance date" id="opening-date" error=${errAt(
                      e,
                      'openingDate',
                    )}><${Input}
                      type="date" value=${f.openingDate} onInput=${set('openingDate')} /></${Field}>
                  </div>
                `}
        <${FormError} error=${e} shown=${[
          'name',
          'institution',
          'mask',
          'keptBy',
          'lotMethod',
          'openingBalance',
          'openingDate',
          ...TERM_FIELDS,
          ...PLAN_FIELDS,
        ]} />
      </${Dialog}>
  `;
}
