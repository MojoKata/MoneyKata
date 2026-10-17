// A physical-asset account's items (requirements S1.10): the Items tab, with precious metals
// summarised by metal; the item dialog, with its fields, valuations, a property's
// improvements, photos and documents, the loans it secures, and its sale.
import { useState } from 'preact/hooks';
import { html } from '../app/html.js';
import { api } from '../api/client.js';
import { useApi, useSubmit } from '../app/hooks.js';
import { date, quantity } from '../app/format.js';
import { Amt } from './amount.js';
import { Empty, Failed, Loading } from './bits.js';
import { Dialog, openDialog } from './dialog.js';
import { useDialogGuide } from './help.js';
import { errAt, Field, FormError, Input, Select, SwitchRow } from './fields.js';
import { Icon } from './icon.js';
import { toast } from './toast.js';
import { ACCEPT, uploadAll } from './receipt.js';
import { BY_TYPE } from '../account-types/index.js';
import { dec, num } from '../app/dec.js';

export const METALS = /** @type {[string, string][]} */ ([
  ['gold', 'Gold'],
  ['silver', 'Silver'],
  ['platinum', 'Platinum'],
  ['palladium', 'Palladium'],
]);
const FORMS = ['Coin', 'Bar', 'Round', 'Jewellery'];
const UNITS = /** @type {[string, string][]} */ ([
  ['ozt', 'troy oz'],
  ['g', 'grams'],
  ['kg', 'kilograms'],
]);
const CATEGORIES = [
  'Watch',
  'Coin (numismatic)',
  'Art',
  'Wine and spirits',
  'Trading cards',
  'Stamps',
  'Jewellery',
  'Other',
];
const HOW = /** @type {[string, string][]} */ ([
  ['bought', 'Bought'],
  ['gift', 'A gift (carried-over basis)'],
  ['inherited', 'Inherited (value at death)'],
]);
export const VALUED_BY = /** @type {[string, string][]} */ ([
  ['spot', 'Spot price × fine weight'],
  ['valuations', 'Valuations'],
  ['depreciation', 'Depreciation'],
]);
const SOURCES = /** @type {[string, string][]} */ ([
  ['appraisal', 'Appraisal'],
  ['sale', 'Recent sale'],
  ['guide', 'Price guide'],
  ['estimate', 'Estimate'],
]);
const SOURCE = Object.fromEntries(SOURCES);
const METAL = Object.fromEntries(METALS);
const clean = (/** @type {string} */ s) => (s ? String(s).replace(/[$,%\s]/g, '') : '');
const orNull = (/** @type {string} */ s) => (clean(s) === '' ? null : clean(s));
const today = () => new Date().toISOString().slice(0, 10);

/** @param {{ a: any }} p */
export function Items({ a }) {
  const res = useApi(`/accounts/${a.id}/items`, {}, ['prices']);
  const v = /** @type {any} */ (res.data);
  if (res.error) return html`<${Failed} error=${res.error} />`;
  if (!v) return html`<${Loading} />`;
  const open = (/** @type {any} */ id) =>
    openDialog(ItemDialog, { a, id }).then(() => res.reload());
  const metals = a.type === 'precious-metals';
  return html`
    ${v.metals.length
      ? html`<div class="grid g2">${
        v.metals.map((/** @type {any} */ m) =>
          html`
            <div class="card">
              <h3>${METAL[m.metal]}<span class="spacer"></span><span
                      class="small dim" style=${{ fontWeight: 400 }}>${m.spot
                        ? html`spot <${Amt} v=${m.spot} />/oz · ${date(m.spotAsOf)}`
                        : 'no spot price yet'}</span></h3>
              <div class="kv">
                <div>
                  <div class="k">Fine ounces</div>
                  <div class="v">${quantity(m.ounces)}</div>
                </div>
                <div>
                  <div class="k">Average cost</div>
                  <div class="v">${m.averageCost ? html`<${Amt} v=${m.averageCost} />` : '—'}</div>
                </div>
                <div>
                  <div class="k">Value</div>
                  <div class="v">
                    <${Amt} v=${m.value} cents=${false} />
                  </div>
                </div>
                <div>
                  <div class="k">Gain</div>
                  <div class="v">
                    <${Amt} v=${m.gain} signed
                      cents=${false} />
                  </div>
                </div>
              </div>
            </div>
          `
        )
      }</div>`
      : null}
    <div class=${'card' + (v.metals.length ? ' mt' : '')} style=${{ padding: '4px 8px' }}>
      <h3 style=${{ padding: '8px 8px 0' }}>Items<span class="spacer"></span>${v.canWrite
        ? html`<button class="btn sm" onClick=${() => open(null)}><${Icon} name="plus" /> Add an
          item</button>`
        : null}</h3>
      ${v.items.length
        ? html`
          <div class="table-wrap">
            <table class="t">
              <caption class="sr-only">Items</caption>
              <thead>
                <tr><th>Item</th>${metals
                  ? html`<th class="num">Fine oz</th>`
                  : null}<th>Acquired</th><th class="num">Cost basis</th><th>Value</th>
                      <th class="num">Gain</th></tr>
              </thead>
              <tbody>${v.items.map((/** @type {any} */ i) =>
                html`<tr class="click" tabindex="0" onClick=${() => open(i.id)} onKeyDown=${(
                  /** @type {KeyboardEvent} */ e,
                ) => e.key === 'Enter' && open(i.id)}>
              <td>${i.name}<div class="small dim">${
                  [
                    i.metal ? METAL[i.metal] : null,
                    i.category,
                    !dec(i.quantity).eq(1) ? `× ${quantity(i.quantity)}` : null,
                  ].filter(Boolean).join(' · ')
                }</div></td>
              ${
                  metals
                    ? html`<td class="num">${i.fineOunces ? quantity(i.fineOunces) : '—'}</td>`
                    : null
                }
              <td class="small dim" style=${{ whiteSpace: 'nowrap' }}>${
                  date(i.acquiredOn)
                }<div>${i.years} yr</div></td>
              <td class="num"><${Amt} v=${i.basis} cents=${false} /></td>
              <td>${
                  i.sale
                    ? html`<span class="pill">sold ${date(i.sale.soldOn)}</span>`
                    : html`<b><${Amt} v=${i.value} cents=${false} /></b>${
                      i.latest
                        ? html`<div class="small dim">${SOURCE[i.latest.source]} · ${
                          date(
                            i.latest
                              .date,
                          )
                        } ${
                          i.stale ? html`<span class="pill warn">over a year old</span>` : null
                        }</div>`
                        : html`<div class="small dim">${
                          VALUED_BY.find(([k]) => k === i.valuation)?.[1]
                        }</div>`
                    }${
                      i
                          .equity != null
                        ? html`<div class="small dim">equity <${Amt} v=${i.equity} cents=${false} /></div>`
                        : null
                    }`
                }</td>
              <td class="num"><${Amt} v=${i.gain} signed cents=${false} /></td></tr>`
              )}</tbody>
              <tfoot>
                <tr>
                  <td colspan=${metals ? 3 : 2}><b>Held now</b></td>
                  <td class="num">
                    <${Amt}
                      v=${v.basis} cents=${false} />
                  </td>
                  <td><b><${Amt} v=${v.value} cents=${false} /></b></td>
                  <td class="num">
                    <${Amt} v=${v.gain} signed cents=${false} />
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        `
        : html`<${Empty}>No items yet.${
          v.canWrite ? ' Add each with its purchase date, cost basis and how it is valued.' : ''
        }</${Empty}>`}
      ${metals
        ? html`<p class="small dim" style=${{ padding: '0 8px' }}>Gold spot from PAXG, and silver,
          platinum and palladium from their trusts' metal per share. Gains on metals are taxed
          as collectables.</p>`
        : null}
    </div>
  `;
}

/** The summary on a physical-asset account's Overview. */
/** @param {{ a: any }} p */
export function ItemsSummary({ a }) {
  const res = useApi(`/accounts/${a.id}/items`, {}, ['prices']);
  const v = /** @type {any} */ (res.data);
  if (!v) {
    return html`
      <div class="card">
        <${Loading} lines=${4} />
      </div>
    `;
  }
  const held = v.items.filter((/** @type {any} */ i) => !i.sale);
  const stale = held.filter((/** @type {any} */ i) => i.stale).length;
  return html`
    <div class="card facts">
      <h3>Details</h3>
      <div class="list-item"><span class="grow dim">Type</span>${a.typeLabel}</div>
      <div class="list-item"><span class="grow dim">Items held</span>${held.length}${stale
        ? html`<span class="pill warn">${stale} valued over a year ago</span>`
        : null}</div>
      <div class="list-item"><span class="grow dim">Valued by</span>${VALUED_BY.find(([k]) =>
        k === BY_TYPE[a.type]?.physical
      )?.[1]}</div>
      <div class="list-item"><span class="grow dim">Cost basis</span><${Amt} v=${v.basis}
        cents=${false} /></div>
      <div class="list-item"><span class="grow dim">Gain</span><${Amt} v=${v.gain} signed
        cents=${false} /></div>
      <div class="list-item"><span class="grow dim">Owner</span>${a.ownerName}</div>
    </div>
  `;
}

/**
 * The form's values: blank for a new item of this account type, or the item's.
 * @param {any} i  the item, or null
 * @param {string} type  the account type
 */
function itemForm(i, type) {
  const by = BY_TYPE[type]?.physical || 'valuations';
  const s = (/** @type {any} */ x) => (x == null ? '' : String(x));
  return {
    name: s(i?.name),
    category: s(i?.category) ||
      (type === 'precious-metals' ? 'Coin' : type === 'collectables' ? 'Watch' : ''),
    description: s(i?.description),
    acquiredOn: s(i?.acquiredOn),
    acquiredHow: i?.acquiredHow || 'bought',
    costBasis: s(i?.costBasis),
    quantity: s(i?.quantity ?? '1'),
    location: s(i?.location),
    serial: s(i?.serial),
    condition: s(i?.condition),
    insuredValue: s(i?.insuredValue),
    policy: s(i?.policy),
    notes: s(i?.notes),
    valuation: i?.valuation || by,
    metal: i?.metal || 'gold',
    unitWeight: s(i?.unitWeight ?? (type === 'precious-metals' ? '1' : '')),
    weightUnit: i?.weightUnit || 'ozt',
    purity: s(i?.purity ?? (type === 'precious-metals' ? '.9999' : '')),
    sellPremium: s(i?.sellPremium ?? '0'),
    depreciationRate: s(i?.depreciationRate ?? (type === 'vehicle' ? '12' : '')),
    address: s(i?.address),
    closingCosts: s(i?.closingCosts),
    primaryResidence: i ? i.primaryResidence : type === 'real-estate',
    personalUse: i ? i.personalUse : ['vehicle', 'real-estate'].includes(type),
  };
}

/** @param {any} f */
function itemBody(f) {
  return {
    name: f.name,
    category: f.category || null,
    description: f.description || null,
    acquiredOn: f.acquiredOn,
    acquiredHow: f.acquiredHow,
    costBasis: clean(f.costBasis) || '0',
    quantity: clean(f.quantity) || '1',
    location: f.location || null,
    serial: f.serial || null,
    condition: f.condition || null,
    insuredValue: orNull(f.insuredValue),
    policy: f.policy || null,
    notes: f.notes || null,
    valuation: f.valuation,
    metal: f.valuation === 'spot' ? f.metal : null,
    unitWeight: f.valuation === 'spot' ? orNull(f.unitWeight) : null,
    weightUnit: f.valuation === 'spot' ? f.weightUnit : null,
    purity: f.valuation === 'spot' ? f.purity : null,
    sellPremium: f.valuation === 'spot' ? clean(f.sellPremium) || '0' : '0',
    depreciationRate: f.valuation === 'depreciation' ? orNull(f.depreciationRate) : null,
    address: f.address || null,
    closingCosts: orNull(f.closingCosts),
    primaryResidence: f.primaryResidence,
    personalUse: f.personalUse,
  };
}

const ITEM_FIELDS = Object.keys(itemBody(itemForm(null, 'other-asset')));

/** @param {{ close: (v?: any) => void, a: any, id: string | null }} p */
export function ItemDialog({ close, a, id }) {
  useDialogGuide('dialog-item');
  const res = useApi(id ? `/items/${id}` : null);
  const it = /** @type {any} */ (res.data);
  if (id && !it) {
    return html`
      <${Dialog} title="Item" close=${close} footer=${null}>
        <${Loading} lines=${6} />
        </${Dialog}>
    `;
  }
  return html`<${ItemEditor} a=${a} it=${it} close=${close} reload=${res.reload} />`;
}

/** @param {{ a: any, it: any, close: (v?: any) => void, reload: () => void }} p */
function ItemEditor({ a, it, close, reload }) {
  const [f, setF] = useState(itemForm(it, a.type));
  const [cur, setCur] = useState(it);
  const set = (/** @type {string} */ k) => (/** @type {any} */ x) => setF({ ...f, [k]: x });
  const canWrite = cur ? cur.canWrite : true;
  const save = useSubmit(async () => {
    const body = itemBody(f);
    const out = cur
      ? await api.patch(`/items/${cur.id}`, body, cur.version)
      : await api.post(`/accounts/${a.id}/items`, body, { idempotent: true });
    toast(cur ? 'Saved' : `${out.name} added`);
    if (cur) {
      setCur(out);
      reload();
    } else close(out);
  });
  const e = save.error;
  const t = a.type;
  const spot = f.valuation === 'spot';
  return html`
    <${Dialog} title=${cur ? cur.name : 'Add an item'} wide close=${close} onSubmit=${() =>
      canWrite && save.run().catch(() => {})}
      footer=${canWrite
        ? html`<button class="btn primary" disabled=${save.busy}>${cur ? 'Save' : 'Add'}</button>`
        : null}>
      <div class="split" style=${{ alignItems: 'flex-start' }}>
        <fieldset disabled=${!canWrite} style=${{
          flex: '1 1 320px',
          border: 0,
          padding: 0,
          margin: 0,
          minWidth: 0,
        }}>
          <${Field} label="Name" error=${errAt(e, 'name')}>
            <${Input} value=${f.name} onInput=${set('name')} required placeholder=${{
              'precious-metals': 'American Gold Eagle, 1 oz',
              collectables: 'Rolex Submariner 124060',
              'real-estate': 'Home',
              vehicle: '2023 Subaru Outback',
            }[t] || ''} /></${Field}>
          ${t === 'real-estate'
            ? html`
              <${Field} label="Address" error=${errAt(e, 'address')}>
                <${Input} value=${f.address} onInput=${set('address')}
                  placeholder="Optional" />
                </${Field}>
                <${SwitchRow} label="Primary residence"
                  hint="Your main home: its sale may be partly tax-free." on=${f.primaryResidence}
                  onChange=${set('primaryResidence')} />
            `
            : null}
          ${t === 'precious-metals'
            ? html`
              <div class="row">
                <${Field} label="Metal" error=${errAt(e, 'metal')}>
                  <${Select} value=${f.metal}
                    onChange=${set('metal')} options=${METALS} />
                  </${Field}>
                  <${Field} label="Form" id="category" error=${errAt(e, 'category')}>
                    <${Select}
                      value=${f.category} onChange=${set('category')} options=${FORMS} />
                    </${Field}>
                    </div>
            `
            : t === 'collectables'
            ? html`
              <${Field} label="Category" error=${errAt(e, 'category')}>
                <${Select}
                  value=${f.category} onChange=${set('category')} options=${CATEGORIES} />
                </${Field}>
            `
            : null}
          ${t === 'vehicle' || t === 'other-asset'
            ? html`
              <${Field} label="Valued by" id="valuation" error=${errAt(e, 'valuation')}>
                <${Select} value=${f.valuation} onChange=${set('valuation')}
                  options=${VALUED_BY.filter(([k]) => k !== 'spot')} />
                </${Field}>
            `
            : null}
          ${spot
            ? html`
              <div class="row">
                <${Field} label="Weight per unit" id="unit-weight" error=${errAt(e, 'unitWeight')}>
                  <${Input} value=${f.unitWeight} onInput=${set('unitWeight')}
                    inputmode="decimal" />
                  </${Field}>
                  <${Field} label="Unit" id="weight-unit" error=${errAt(e, 'weightUnit')}>
                    <${Select} value=${f.weightUnit} onChange=${set('weightUnit')}
                      options=${UNITS} />
                    </${Field}>
                    </div>
                    <div class="row">
                      <${Field} label="Purity" error=${errAt(e, 'purity')}
                        hint=".9999, .925, 22k">
                        <${Input} value=${f.purity}
                          onInput=${set('purity')} />
                        </${Field}>
                        <${Field} label="Quantity" error=${errAt(e, 'quantity')}>
                          <${Input}
                            value=${f.quantity} onInput=${set('quantity')} inputmode="decimal" />
                          </${Field}>
                          </div>
            `
            : null}
          ${f.valuation === 'depreciation'
            ? html`
              <${Field} label="Depreciation per year" id="depreciation-rate"
                error=${errAt(e, 'depreciationRate')}
                hint="A percentage of the value each year, until a valuation replaces it.">
                <${Input} value=${f.depreciationRate} onInput=${set('depreciationRate')}
                  inputmode="decimal" placeholder="12" />
                </${Field}>
            `
            : null}
          <div class="row">
            <${Field} label="Date acquired" id="acquired-on" error=${errAt(e, 'acquiredOn')}>
              <${Input} type="date" value=${f.acquiredOn} onInput=${set('acquiredOn')}
                required /></${Field}>
            <${Field} label="How acquired" id="acquired-how" error=${errAt(e, 'acquiredHow')}>
              <${Select} value=${f.acquiredHow} onChange=${set('acquiredHow')}
                options=${HOW} /></${Field}>
          </div>
          <div class="row">
            <${Field} label=${t === 'real-estate' ? 'Purchase price' : 'Cost basis'}
              id="cost-basis" error=${errAt(e, 'costBasis')} hint=${t === 'real-estate'
                ? 'Improvements add to it below.'
                : 'Price plus premium, fees and shipping.'}>
              <${Input} value=${f.costBasis} onInput=${set('costBasis')} inputmode="decimal"
                required /></${Field}>
            ${t === 'real-estate'
              ? html`
                <${Field} label="Closing costs" error=${errAt(e, 'closingCosts')}>
                  <${Input} value=${f.closingCosts} onInput=${set('closingCosts')}
                    inputmode="decimal" />
                  </${Field}>
              `
              : html`
                <${Field} label="Insured value" error=${errAt(e, 'insuredValue')}>
                  <${Input} value=${f.insuredValue} onInput=${set('insuredValue')}
                    inputmode="decimal" />
                  </${Field}>
              `}
          </div>
          ${spot
            ? html`
              <${Field} label="Selling premium" id="sell-premium" error=${errAt(
                e,
                'sellPremium',
              )}
                hint="What you'd expect over spot when selling, in percent; below spot is negative.">
                <${Input} value=${f.sellPremium} onInput=${set('sellPremium')}
                  inputmode="decimal" />
                </${Field}>
            `
            : null}
          ${t === 'real-estate' ? null : html`
            <div class="row">
              <${Field} label="Where it's kept" id="location" error=${errAt(e, 'location')}>
                <${Input} value=${f.location} onInput=${set('location')} />
                </${Field}>
                <${Field} label=${t === 'vehicle' ? 'VIN' : 'Serial or certificate'} id="serial"
                  error=${errAt(e, 'serial')}>
                  <${Input} value=${f.serial}
                    onInput=${set('serial')} />
                  </${Field}>
                  </div>
          `}
          <div class="row">
            <${Field} label="Condition or grade" id="condition" error=${errAt(e, 'condition')}>
              <${Input} value=${f.condition} onInput=${set('condition')} /></${Field}>
            <${Field} label="Insurance policy" id="policy" error=${errAt(e, 'policy')}>
              <${Input} value=${f.policy} onInput=${set('policy')} /></${Field}>
          </div>
          ${t === 'vehicle' || t === 'other-asset' || t === 'collectables'
            ? html`
              <${SwitchRow} label="Used personally"
                hint="A loss when it's sold isn't deductible." on=${f.personalUse}
                onChange=${set('personalUse')} />
            `
            : null}
          <${Field} label="Notes" error=${errAt(e, 'notes')} hint="Markdown.">
            <textarea class="in" rows="3" value=${f.notes} onInput=${(/** @type {any} */ ev) =>
              set('notes')(ev.currentTarget.value)}></textarea></${Field}>
          <${FormError} error=${e} shown=${ITEM_FIELDS} />
        </fieldset>
        ${cur ? html`<${Side} a=${a} it=${cur} setIt=${setCur} reload=${reload} />` : null}
      </div>
    </${Dialog}>
  `;
}

/** @param {{ a: any, it: any, setIt: (it: any) => void, reload: () => void }} p */
function Side({ a, it, setIt, reload }) {
  const done = (/** @type {any} */ out, /** @type {string} */ msg) => {
    setIt(out);
    reload();
    toast(msg);
  };
  return html`
    <div style=${{ flex: '0 1 280px', minWidth: 0 }}>
      <div class="list-item"><span class="grow dim">Value</span><b><${Amt} v=${it.value}
        cents=${false} /></b></div>
      ${it.valuation === 'spot'
        ? html`<p class="small dim">${quantity(it.fineOunces)} fine oz × ${
          it.spot
            ? html`<${Amt} v=${it.spot} /> spot on ${date(it.spotAsOf)}`
            : 'spot, once a price is in'
        }${num(it.sellPremium) ? ` · ${it.sellPremium}% when selling` : ''}</p>`
        : null}
      <div class="list-item"><span class="grow dim">Cost basis</span><${Amt} v=${it.basis}
        cents=${false} /></div>
      ${it.loans.map((/** @type {any} */ l) =>
        html`<div class="list-item"><span class="grow dim">Secures</span><a
          href=${`/ui/accounts/${l.accountId}`}>${l.name}</a>${' '}<${Amt} v=${l.owed}
          cents=${false} /></div>`
      )}
      ${it.equity != null
        ? html`
          <div
            class="list-item"><span class="grow dim">Equity</span><${Amt} v=${it
              .equity} cents=${false} /></div>
        `
        : null}
      ${it.valuation === 'spot' ? null : html`<${Valuations} it=${it} done=${done} />`}
      ${a.type === 'real-estate' ? html`<${Improvements} it=${it} done=${done} />` : null}
      <${Documents} it=${it} done=${done} />
      <${SaleCard} it=${it} done=${done} />
    </div>
  `;
}

/** @param {{ it: any, done: (out: any, msg: string) => void }} p */
function Valuations({ it, done }) {
  const [f, setF] = useState({ date: today(), value: '', source: 'estimate' });
  const add = useSubmit(async () => {
    const out = await api.post(`/items/${it.id}/valuations`, {
      date: f.date,
      value: clean(f.value),
      source: f.source,
    });
    setF({ ...f, value: '' });
    done(out, 'Valuation added');
  });
  const remove = useSubmit(async (/** @type {string} */ vid) => {
    const was = it.valuations.find((/** @type {any} */ x) => x.id === vid);
    const out = await api.del(`/items/${it.id}/valuations/${vid}`, was?.version);
    done(out.parent, 'Valuation removed');
  });
  return html`
    <h4 style=${{ margin: '14px 0 8px' }} data-help="valuations">Valuations</h4>
    ${it.valuations.length
      ? it.valuations.map((/** @type {any} */ v) =>
        html`<div class="list-item"><div class="grow"><${Amt} v=${v.value} cents=${false} /><div
          class="small dim">${SOURCE[v.source]} · ${date(v.date)}</div></div>${
          it.canWrite
            ? html`<button type="button" class="icon-btn" aria-label=${`Remove the ${
              date(v.date)
            } valuation`} onClick=${() => remove.run(v.id).catch(() => {})}><${Icon}
              name="x" /></button>`
            : null
        }</div>`
      )
      : html`<p class="small dim">None yet: it counts at its cost basis${
        it.valuation ===
            'depreciation'
          ? ', depreciated'
          : ''
      }.</p>`}
    ${it.canWrite
      ? html`
        <div class="row">
          <${Field} label="Value" help="valuations" id="valuation-value"
            error=${errAt(add.error, 'value')}>
            <${Input} value=${f.value} inputmode="decimal"
              onInput=${(/** @type {string} */ x) => setF({ ...f, value: x })} />
            </${Field}>
            <${Field}
              label="On" help="valuations" id="valuation-date" error=${errAt(add.error, 'date')}>
              <${Input}
                type="date" value=${f.date} onInput=${(/** @type {string} */ x) =>
                  setF({ ...f, date: x })} />
              </${Field}>
              </div>
              <div class="row">
                <${Field} label="Source" help="valuations" id="valuation-source"><${Select}
                  value=${f.source} options=${SOURCES} onChange=${(/** @type {string} */ x) =>
                    setF({ ...f, source: x })} /></${Field}><button type="button" class="btn sm"
                  style=${{ alignSelf: 'end' }} disabled=${add.busy ||
                    !clean(f.value)} onClick=${() =>
                    add.run().catch(() => {})}><${Icon} name="plus" /> Add</button></div>
      `
      : null}
  `;
}

/** @param {{ it: any, done: (out: any, msg: string) => void }} p */
function Improvements({ it, done }) {
  const [f, setF] = useState({ date: today(), description: '', amount: '' });
  const add = useSubmit(async () => {
    const out = await api.post(`/items/${it.id}/improvements`, {
      date: f.date,
      description: f.description,
      amount: clean(f.amount),
    });
    setF({ ...f, description: '', amount: '' });
    done(out, 'Improvement added to the basis');
  });
  const remove = useSubmit(async (/** @type {string} */ mid) => {
    const was = it.improvements.find((/** @type {any} */ x) => x.id === mid);
    const out = await api.del(`/items/${it.id}/improvements/${mid}`, was?.version);
    done(out.parent, 'Improvement removed');
  });
  return html`
    <h4 style=${{ margin: '14px 0 8px' }} data-help="improvements">Improvements</h4>
    ${it.improvements.map((/** @type {any} */ m) =>
      html`
        <div
          class="list-item"><div class="grow">${m.description}<div class="small dim">${date(
            m.date,
          )}</div></div><${Amt} v=${m.amount} cents=${false} />${it.canWrite
            ? html`
              <button type="button" class="icon-btn" aria-label=${'Remove ' + m.description}
                onClick=${() => remove.run(m.id).catch(() => {})}><${Icon} name="x" /></button>
            `
            : null}</div>
      `
    )}
    ${it.canWrite
      ? html`
        <${Field} label="What was done" help="improvements" id="improvement-description"
          error=${errAt(add.error, 'description')}>
          <${Input} value=${f.description}
            placeholder="Kitchen remodel" onInput=${(/** @type {string} */ x) =>
              setF({ ...f, description: x })} />
          </${Field}>
          <div class="row">
            <${Field} label="Cost" help="improvements" id="improvement-amount"
              error=${errAt(add.error, 'amount')}>
              <${Input} value=${f.amount} inputmode="decimal"
                onInput=${(/** @type {string} */ x) => setF({ ...f, amount: x })} />
              </${Field}>
              <${Field}
                label="On" help="improvements" id="improvement-date">
                <${Input} type="date"
                  value=${f.date} onInput=${(/** @type {string} */ x) => setF({ ...f, date: x })} />
                </${Field}>
                </div>
                <button type="button" class="btn sm" disabled=${add.busy ||
                  !f.description}
                  onClick=${() =>
                    add.run().catch(() => {})}><${Icon} name="plus" /> Add improvement</button>
      `
      : null}
  `;
}

/** @param {{ it: any, done: (out: any, msg: string) => void }} p */
function Documents({ it, done }) {
  const [busy, setBusy] = useState(false);
  const send = async (/** @type {FileList} */ files) => {
    setBusy(true);
    let out = null;
    for (const r of await uploadAll(files)) {
      out = await api.post(`/items/${it.id}/documents`, { receiptId: r.id });
    }
    setBusy(false);
    if (out) done(out, 'Kept with the item');
  };
  const remove = useSubmit(async (/** @type {string} */ rid) =>
    done((await api.del(`/items/${it.id}/documents/${rid}`)).parent, 'Removed from the item')
  );
  return html`
    <h4 style=${{ margin: '14px 0 8px' }} data-help="photos-and-documents">Photos and documents</h4>
    ${it.documents.length
      ? it.documents.map((/** @type {any} */ d) =>
        html`
          <div
            class="list-item"><span class="grow"><${Icon} name="clip" /> ${d
              .fileName}</span>${it.canWrite
              ? html`
                <button type="button" class="icon-btn" aria-label=${'Remove ' + d.fileName}
                  onClick=${() => remove.run(d.id).catch(() => {})}><${Icon} name="x" /></button>
              `
              : null}</div>
        `
      )
      : html`<p class="small dim">The purchase receipt, an appraisal, a certificate, the title.</p>`}
    ${it.canWrite
      ? html`
        <label class="btn sm" for="f-item-files"><${Icon} name="upload" /> ${busy
          ? 'Uploading…'
          : 'Add'}</label><input
          id="f-item-files" class="sr-only" type="file" multiple
          accept=${ACCEPT} data-help="photos-and-documents" onChange=${(/** @type {any} */ e) => {
            send(e.currentTarget.files);
            e.currentTarget.value = '';
          }} />
      `
      : null}
  `;
}

/** @param {{ it: any, done: (out: any, msg: string) => void }} p */
function SaleCard({ it, done }) {
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ soldOn: today(), proceeds: '', fees: '' });
  const sell = useSubmit(async () => {
    const out = await api.put(`/items/${it.id}/sale`, {
      soldOn: f.soldOn,
      proceeds: clean(f.proceeds),
      fees: clean(f.fees) || '0',
    }, it.version);
    setOpen(false);
    done(out, 'Sale recorded');
  });
  const undo = useSubmit(async () =>
    done((await api.del(`/items/${it.id}/sale`, it.version)).parent, 'Sale undone')
  );
  const s = it.sale;
  if (s) {
    return html`
      <h4 style=${{ margin: '14px 0 8px' }} data-help="sale">Sold</h4>
      <div class="list-item"><span class="grow dim">On</span>${date(s.soldOn)}</div>
      <div class="list-item"><span class="grow dim">Proceeds, less fees</span><${Amt}
        v=${dec(s.proceeds).sub(dec(s.fees))} /></div>
      <div
        class="list-item"><span class="grow dim">${dec(s.gain).isNegative()
          ? 'Loss'
          : 'Gain'}</span><${Amt} v=${s.gain} signed /></div>
      ${s.collectable
        ? html`<p class="small dim">Taxed as a collectable, flagged on Form 8949.</p>`
        : null}
      ${!s.deductible
        ? html`<p class="small dim">A loss on property you used yourself isn't deductible.</p>`
        : null}
      ${it.canWrite
        ? html`<button type="button" class="btn sm" onClick=${() =>
          undo.run().catch(() => {})}>Undo the sale</button>`
        : null}
    `;
  }
  if (!it.canWrite) return null;
  if (!open) {
    return html`
      <div
        class="toolbar mt"><button type="button" class="btn sm" onClick=${() =>
          setOpen(true)}>Record the sale…</button></div>
    `;
  }
  return html`
    <h4 style=${{ margin: '14px 0 8px' }} data-help="sale">Sale</h4>
    <div class="row">
      <${Field} label="Sold on" help="sale" id="sold-on" error=${errAt(
        sell.error,
        'soldOn',
      )}>
        <${Input} type="date" value=${f.soldOn} onInput=${(/** @type {string} */ x) =>
          setF({ ...f, soldOn: x })} />
        </${Field}>
        <${Field} label="Proceeds" help="sale"
          id="proceeds" error=${errAt(sell.error, 'proceeds')}>
          <${Input} value=${f.proceeds}
            inputmode="decimal" onInput=${(/** @type {string} */ x) =>
              setF({ ...f, proceeds: x })} />
          </${Field}>
          </div>
          <${Field} label="Fees" help="sale" id="sale-fees" error=${errAt(sell.error, 'fees')}>
            <${Input}
              value=${f.fees} inputmode="decimal" onInput=${(/** @type {string} */ x) =>
                setF({ ...f, fees: x })} />
            </${Field}>
            <${FormError} error=${sell.error} shown=${['soldOn', 'proceeds', 'fees']} />
            <button type="button" class="btn sm danger" disabled=${sell.busy || !clean(f.proceeds)}
              onClick=${() => sell.run().catch(() => {})}>Record the sale</button>
  `;
}
