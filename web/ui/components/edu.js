// A 529 plan's parts of its account page (requirements S1.8): the plan's fields (shared by New
// account and Settings), its facts on the Overview, and the Contributions, Withdrawals and Goal
// tabs.
import { useState } from 'preact/hooks';
import { html } from '../app/html.js';
import { api } from '../api/client.js';
import { useApi, useSubmit } from '../app/hooks.js';
import { date, money } from '../app/format.js';
import { Amt } from './amount.js';
import { Empty, Failed, Loading } from './bits.js';
import { errAt, Field, FormError, Input, Select, SwitchRow } from './fields.js';
import { Icon } from './icon.js';
import { toast } from './toast.js';
import { ACCEPT, uploadAll } from './receipt.js';
import { FanChart } from '../charts/chart.js';
import { EducationAnswer } from '../screens/projections.js';

const clean = (/** @type {string} */ s) => (s ? String(s).replace(/[$,\s]/g, '') : '');
const today = () => new Date().toISOString().slice(0, 10);

/**
 * The plan form's values.
 * @param {any} p  the plan, or null
 */
export function planForm(p) {
  return {
    planState: p?.planState || '',
    planName: p?.planName || '',
    beneficiary: p?.beneficiary ? `${p.beneficiary.kind}:${p.beneficiary.id}` : '',
    openedOn: p?.openedOn || '',
    stateDeduction: p?.stateDeduction || '',
    newName: '',
    newBirthYear: '',
  };
}

/**
 * The body to save, adding a new person first when one was typed.
 * @param {any} f
 */
export async function planBody(f) {
  let who = f.beneficiary;
  if (who === 'new') {
    const p = await api.post('/people', {
      name: f.newName,
      relationship: 'child',
      birthYear: f.newBirthYear ? Number(f.newBirthYear) : null,
    });
    who = `person:${p.id}`;
  }
  const [kind, id] = who ? who.split(':') : [];
  return {
    planState: f.planState || null,
    planName: f.planName || null,
    beneficiary: who ? { kind, id } : null,
    openedOn: f.openedOn || null,
    stateDeduction: clean(f.stateDeduction) || null,
  };
}

export const PLAN_FIELDS = [
  'planState',
  'planName',
  'beneficiary',
  'openedOn',
  'stateDeduction',
  'name',
  'birthYear',
];

/**
 * The plan's fields.
 * @param {{ f: any, set: (k: string) => (v: any) => void, e: any }} p
 */
export function PlanFields({ f, set, e }) {
  const people = useApi('/people');
  const list = (/** @type {any[]} */ (people.data) || []).filter((p) => p.level === 'owner');
  return html`
    <div class="row">
      <${Field} label="Plan state" id="plan-state" error=${errAt(e, 'planState')}>
        <${Input} value=${f.planState} onInput=${set('planState')} placeholder="Utah" />
        </${Field}>
        <${Field} label="Plan name" id="plan-name" error=${errAt(e, 'planName')}>
          <${Input} value=${f.planName} onInput=${set('planName')} placeholder="my529" />
          </${Field}>
          </div>
          <${Field} label="Beneficiary" error=${errAt(e, 'beneficiary')}
            hint="Someone on your list of people. The 529 counts in your net worth, not theirs.">
      <${Select} value=${f.beneficiary} onChange=${set('beneficiary')} options=${[
        ['', 'Choose…'],
        ...(f.beneficiary.startsWith('user:') ? [[f.beneficiary, 'A user']] : []),
        ...list.map((p) => [`person:${p.id}`, p.name]),
        ['new', 'Add a person…'],
      ]} /></${Field}>
    ${f.beneficiary === 'new'
      ? html`
        <div class="row">
          <${Field} label="Their name" id="new-name" error=${errAt(e, 'name')}>
            <${Input} value=${f.newName} onInput=${set('newName')} required />
            </${Field}>
            <${Field} label="Year of birth" id="new-birth-year" error=${errAt(e, 'birthYear')}
              hint="When school starts, for the Goal tab.">
              <${Input} value=${f.newBirthYear} onInput=${set('newBirthYear')}
                inputmode="numeric" />
              </${Field}>
              </div>
      `
      : null}
    <div class="row">
      <${Field} label="Opened" id="opened-on" error=${errAt(e, 'openedOn')}
        hint="A Roth IRA rollover is possible 15 years on.">
        <${Input} type="date" value=${f.openedOn} onInput=${set('openedOn')} /></${Field}>
      <${Field} label="State tax deduction a year" id="state-deduction"
        error=${errAt(e, 'stateDeduction')} hint="What you expect, typed.">
        <${Input} value=${f.stateDeduction} onInput=${set('stateDeduction')}
          inputmode="decimal" /></${Field}>
    </div>
  `;
}

/** The Settings card with the plan. */
/** @param {{ a: any }} p */
export function PlanCard({ a }) {
  const res = useApi(`/accounts/${a.id}/plan529`);
  const v = /** @type {any} */ (res.data);
  if (!v) {
    return html`
      <div class="card">
        <${Loading} lines=${4} />
      </div>
    `;
  }
  return html`<${PlanEditor} a=${a} v=${v} reload=${res.reload} />`;
}

/** @param {{ a: any, v: any, reload: () => void }} p */
function PlanEditor({ a, v, reload }) {
  const [f, setF] = useState(planForm(v));
  const set = (/** @type {string} */ k) => (/** @type {any} */ x) => setF({ ...f, [k]: x });
  const save = useSubmit(async () => {
    await api.put(`/accounts/${a.id}/plan529`, await planBody(f));
    toast('Plan saved');
    reload();
  });
  return html`
    <form class="card" onSubmit=${(/** @type {Event} */ ev) => {
      ev.preventDefault();
      save.run().catch(() => {});
    }}>
      <h3>The plan</h3>
      <${PlanFields} f=${f} set=${set} e=${save.error} />
      <${FormError} error=${save.error} shown=${PLAN_FIELDS} />
      <div class="toolbar mt"><span class="spacer"></span><button class="btn primary"
        disabled=${save.busy || !v.canWrite}>Save plan</button></div>
    </form>
  `;
}

/** The plan's facts on the Overview. */
/** @param {{ a: any }} p */
export function PlanFacts({ a }) {
  const res = useApi(`/accounts/${a.id}/plan529`, {}, ['import']);
  const v = /** @type {any} */ (res.data);
  if (!v) {
    return html`
      <div class="card">
        <${Loading} lines=${4} />
      </div>
    `;
  }
  const b = v.beneficiary;
  const r = v.rollover;
  return html`
    <div class="card facts">
      <h3>The plan</h3>
      <div class="list-item"><span class="grow dim">Beneficiary</span>${b
        ? html`${b.name}${
          b.birthYear ? html`<span class="small dim"> · born ${b.birthYear}</span>` : null
        }`
        : html`<span class="dim">not chosen</span>`}</div>
      <div class="list-item"><span class="grow dim">Plan</span>${[v.planName, v.planState]
        .filter(Boolean).join(' · ') || '—'}</div>
      <div class="list-item"><span class="grow dim">Opened</span>${v.openedOn
        ? html`${date(v.openedOn)}${
          r.possibleFrom
            ? html`<span class="small dim"> · Roth rollover from ${date(r.possibleFrom)}</span>`
            : null
        }`
        : '—'}</div>
      <div class="list-item"><span class="grow dim">Contributed this year</span><${Amt}
        v=${v.contributedThisYear} cents=${false} /></div>
      <div class="list-item"><span class="grow dim">Owner</span>${a.ownerName}</div>
    </div>
  `;
}

/** @param {{ a: any }} p */
export function Contributions({ a }) {
  const res = useApi(`/accounts/${a.id}/contributions`, {}, ['import']);
  const plan = useApi(`/accounts/${a.id}/plan529`, {}, ['import']);
  const v = /** @type {any} */ (res.data);
  const pl = /** @type {any} */ (plan.data);
  if (res.error) return html`<${Failed} error=${res.error} />`;
  if (!v || !pl) return html`<${Loading} />`;
  const again = () => {
    res.reload();
    plan.reload();
  };
  const r = pl.rollover;
  return html`
    ${v.canWrite ? html`<${AddContribution} a=${a} done=${again} />` : null}
    <div class="card mt" style=${{ padding: '4px 8px' }}>
      <h3 style=${{ padding: '8px 8px 0' }}>Against the annual gift exclusion</h3>
      ${v.years.length
        ? html`
          <div class="table-wrap">
            <table class="t">
              <caption class="sr-only">Contributions by contributor and year</caption>
              <thead>
                <tr>
                  <th>Year</th>
                  <th>Contributor</th>
                  <th class="num">Counts</th>
                  <th class="num">Exclusion</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>${v.years.map((/** @type {any} */ y) =>
                html`
                  <tr>
                    <td>${y.year}</td>
                    <td>${y.name}${y.fromElection
                      ? html`<div class="small dim">a fifth of the ${y.fromElection} five-year
                election</div>`
                      : null}</td>
                    <td class="num">
                      <${Amt} v=${y.counted} cents=${false} />
                    </td>
                    <td class="num">
                      <${Amt} v=${y.exclusion} cents=${false} />
                    </td>
                    <td>${y.over ? html`<span class="pill warn">over: Form 709</span>` : null}</td>
                  </tr>
                `
              )}</tbody>
            </table>
          </div>
        `
        : html`<${Empty}>No contributions yet.</${Empty}>`}
    </div>
    <div class="card mt" style=${{ padding: '4px 8px' }}>
      <h3 style=${{ padding: '8px 8px 0' }}>Contributions</h3>
      ${v.rows.length
        ? html`
          <div class="table-wrap">
            <table class="t">
              <caption class="sr-only">Contributions</caption>
              <thead>
                <tr><th>Date</th><th>From</th><th class="num">Amount</th>
                      ${v.canWrite ? html`<th></th>` : null}</tr>
              </thead>
              <tbody>${v.rows.map((/** @type {any} */ c) =>
                html`<tr><td>${date(c.date)}</td><td>${c.name}${
                  c.relationship ? html`<span class="small dim"> · ${c.relationship}</span>` : null
                }${
                  c.fiveYear
                    ? html`
                      <span class="pill info">five-year election</span>
                    `
                    : null
                }</td><td class="num"><${Amt} v=${c.amount} /></td>${
                  v.canWrite
                    ? html`
                      <td>
                        <${Retag} a=${a} c=${c} done=${again} />
                      </td>
                    `
                    : null
                }</tr>`
              )}</tbody>
            </table>
          </div>
        `
        : null}
    </div>
    <div class="grid g2 mt">
      <div class="card facts">
        <h3>State tax deduction</h3>
        <p class="small dim" style=${{ marginTop: 0 }}>Typed by the owner: MoneyKata doesn't
          model state rules.</p>
        <div class="list-item"><span class="grow dim">Expected a year</span>${pl.stateDeduction
          ? html`<${Amt} v=${pl.stateDeduction} cents=${false} />`
          : '—'}</div>
      </div>
      <div class="card facts">
        <h3>Rollover to a Roth IRA</h3>
        <div class="list-item"><span class="grow dim">Possible from</span>${r.possibleFrom
          ? date(r.possibleFrom)
          : 'once the opening date is set'}</div>
        <div class="list-item"><span class="grow dim">Lifetime limit</span><span><${Amt}
          v=${r.limit} cents=${false} /><span class="small dim"> · used <${Amt} v=${r.used}
            cents=${false} /></span></span></div>
        <div class="list-item"><span class="grow dim">Could still roll over</span><${Amt}
          v=${r.available} cents=${false} /></div>
        <p class="small dim">Contributions of the last five years, and their earnings, can't
          roll over; each year's rollover is also held to the IRA limit.</p>
      </div>
    </div>
  `;
}

/** @param {{ a: any, done: () => void }} p */
function AddContribution({ a, done }) {
  const people = useApi('/people');
  const accounts = useApi('/accounts');
  const [f, setF] = useState({
    date: today(),
    amount: '',
    contributor: 'owner',
    fiveYear: false,
    from: '',
  });
  const set = (/** @type {string} */ k) => (/** @type {any} */ x) => setF({ ...f, [k]: x });
  const banks = (/** @type {any[]} */ (accounts.data) || []).filter((x) =>
    x.group === 'banking' && x.active && ['owner', 'write'].includes(x.level)
  );
  const save = useSubmit(async () => {
    await api.post(`/accounts/${a.id}/contributions`, {
      date: f.date,
      amount: clean(f.amount),
      contributor: f.contributor,
      fiveYear: f.fiveYear,
      fromAccountId: f.from || null,
    }, { idempotent: true });
    toast('Contribution recorded');
    setF({ ...f, amount: '', fiveYear: false });
    done();
  });
  const e = save.error;
  return html`
    <form class="card" onSubmit=${(/** @type {Event} */ ev) => {
      ev.preventDefault();
      save.run().catch(() => {});
    }}>
      <h3>Record a contribution</h3>
      <div class="row">
        <${Field} label="Date" error=${errAt(e, 'date')}>
          <${Input} type="date" value=${f.date}
            onInput=${set('date')} />
          </${Field}>
          <${Field} label="Amount" error=${errAt(e, 'amount')}>
            <${Input} value=${f.amount}
              onInput=${set('amount')} inputmode="decimal" required />
            </${Field}>
            <${Field} label="From" id="contributor" error=${errAt(e, 'contributor')}>
              <${Select} value=${f.contributor} onChange=${set('contributor')} options=${[
                ['owner', 'You'],
                ...(/** @type {any[]} */ (people.data) || []).map((
                  p,
                ) => [`person:${p.id}`, p.name]),
              ]} />
              </${Field}>
              <${Field} label="Paid from" id="from-account" error=${errAt(e, 'fromAccountId')}>
                <${Select} value=${f.from} onChange=${set('from')} options=${[
                  ['', 'Not recorded here'],
                  ...banks.map((b) => [b.id, b.name]),
                ]} />
                </${Field}>
                </div>
                <${SwitchRow} label="Five-year election"
                  hint="Superfunding: counted as a fifth in each of five years against the gift exclusion."
                  on=${f.fiveYear} onChange=${set('fiveYear')} />
                <${FormError} error=${e} shown=${[
                  'date',
                  'amount',
                  'contributor',
                  'fromAccountId',
                ]} />
                <div class="toolbar mt"><span class="spacer"></span><button class="btn primary"
        disabled=${save.busy}>Record</button></div>
                </form>
  `;
}

/** Who an existing deposit came from. */
/** @param {{ a: any, c: any, done: () => void }} p */
function Retag({ a, c, done }) {
  const people = useApi('/people');
  const save = useSubmit(async (/** @type {string} */ who) => {
    await api.put(`/contributions/${c.transactionId}`, { contributor: who, fiveYear: c.fiveYear });
    toast('Saved');
    done();
  });
  return html`
    <${Select} aria-label=${`Who the ${date(c.date)} contribution was from`}
      data-help="from" value=${c.contributor} onChange=${(/** @type {string} */ v) =>
        save.run(v).catch(() => {})} options=${[
        ['owner', a.ownerName],
        ...(c.contributor.startsWith('user:') ? [[c.contributor, c.name]] : []),
        ...(/** @type {any[]} */ (people.data) || []).map((p) => [`person:${p.id}`, p.name]),
      ]} />
  `;
}

/** @param {{ a: any }} p */
export function Withdrawals({ a }) {
  const res = useApi(`/accounts/${a.id}/withdrawals`, {}, ['import']);
  const v = /** @type {any} */ (res.data);
  if (res.error) return html`<${Failed} error=${res.error} />`;
  if (!v) return html`<${Loading} />`;
  return html`
    <div class="card" style=${{ padding: '4px 8px' }}>
      <h3 style=${{ padding: '8px 8px 0' }}>Each year</h3>
      ${v.years.length
        ? html`
          <div class="table-wrap">
            <table class="t">
              <caption class="sr-only">Distributions against qualified expenses</caption>
              <thead>
                <tr>
                  <th>Year</th>
                  <th class="num">Distributions</th>
                  <th class="num">Qualified expenses</th>
                  <th class="num">Not covered</th>
                </tr>
              </thead>
              <tbody>${v.years.map((/** @type {any} */ y) =>
                html`
                  <tr>
                    <td>${y.year}</td>
                    <td class="num">
                      <${Amt} v=${y.distributions} />
                    </td>
                    <td class="num">
                      <${Amt} v=${y.expenses} />
                    </td>
                    <td class="num">${Number(
                        y.notCovered,
                      )
                      ? html`<span class="pill warn"><${Amt} v=${y.notCovered} /></span>`
                      : html`<span class="dim">—</span>`}</td>
                  </tr>
                `
              )}</tbody>
            </table>
          </div>
          <p class="small dim" style=${{ padding: '0 8px' }}>Distributions are what was taken
                      out (Form 1099-Q). The earnings in what isn't covered by qualified expenses may be
                      taxable, with a 10% additional tax; your preparer applies the rules.</p>
        `
        : html`<${Empty}>No withdrawals yet. When school starts, each year lists what was taken
          out against the qualified expenses and their receipts.</${Empty}>`}
    </div>
    ${v.canWrite ? html`<${AddExpense} a=${a} kinds=${v.kinds} done=${res.reload} />` : null}
    ${v.expenses.length
      ? html`<div class="card mt"><h3>Qualified expenses</h3>${
        v.expenses.map((
          /** @type {any} */ x,
        ) => html`<${Expense} x=${x} canWrite=${v.canWrite} done=${res.reload} />`)
      }</div>`
      : null}
  `;
}

/** @param {{ a: any, kinds: [string, string][], done: () => void }} p */
function AddExpense({ a, kinds, done }) {
  const [f, setF] = useState({ date: today(), kind: 'tuition', description: '', amount: '' });
  const set = (/** @type {string} */ k) => (/** @type {any} */ x) => setF({ ...f, [k]: x });
  const save = useSubmit(async () => {
    await api.post(`/accounts/${a.id}/expenses`, {
      date: f.date,
      kind: f.kind,
      description: f.description || null,
      amount: clean(f.amount),
    });
    toast('Expense added');
    setF({ ...f, description: '', amount: '' });
    done();
  });
  const e = save.error;
  return html`
    <form class="card mt" onSubmit=${(/** @type {Event} */ ev) => {
      ev.preventDefault();
      save.run().catch(() => {});
    }}>
      <h3>Add a qualified expense</h3>
      <div class="row">
        <${Field} label="Paid on" id="paid-on" error=${errAt(e, 'date')}>
          <${Input} type="date"
            value=${f.date} onInput=${set('date')} />
          </${Field}>
          <${Field} label="Kind" error=${errAt(e, 'kind')}>
            <${Select} value=${f.kind}
              onChange=${set('kind')} options=${kinds} />
            </${Field}>
            <${Field} label="Amount" error=${errAt(e, 'amount')}>
              <${Input} value=${f.amount}
                onInput=${set('amount')} inputmode="decimal" required />
              </${Field}>
              </div>
              <${Field} label="Description" error=${errAt(e, 'description')}>
                <${Input}
                  value=${f.description} onInput=${set('description')}
                  placeholder="Fall tuition, State University" />
                </${Field}>
                <${FormError} error=${e} shown=${['date', 'kind', 'amount', 'description']} />
                <div class="toolbar"><span class="spacer"></span><button class="btn primary"
        disabled=${save.busy}>Add</button></div>
                </form>
  `;
}

/** @param {{ x: any, canWrite: boolean, done: () => void }} p */
function Expense({ x, canWrite, done }) {
  const [busy, setBusy] = useState(false);
  const send = async (/** @type {FileList} */ files) => {
    setBusy(true);
    for (const r of await uploadAll(files)) {
      await api.post(`/expenses/${x.id}/documents`, { receiptId: r.id });
    }
    setBusy(false);
    done();
  };
  const remove = useSubmit(async () => {
    await api.del(`/expenses/${x.id}`);
    toast('Expense removed');
    done();
  });
  const fid = `f-expense-files-${x.id}`;
  return html`
    <div class="list-item"><div class="grow">${x.description || x.kindLabel}<div
      class="small dim">${x.kindLabel} · ${date(x.date)}${x.year !== Number(x.date.slice(0, 4))
        ? ` · counts in ${x.year}`
        : ''}${x.documents.length
        ? html`
          · <${Icon} name="clip" /> ${x.documents.length} receipt${x.documents.length === 1
            ? ''
            : 's'}
        `
        : ''}</div></div><${Amt} v=${x.amount} />${canWrite
        ? html`
          <label class="btn sm" for=${fid}><${Icon} name="clip" /> ${busy
            ? 'Uploading…'
            : 'Receipt'}</label><input
            id=${fid} class="sr-only" type="file" multiple
            accept=${ACCEPT} data-help="receipts" onChange=${(/** @type {any} */ e) => {
              send(e.currentTarget.files);
              e.currentTarget.value = '';
            }} /><button type="button"
            class="icon-btn" aria-label=${'Remove ' +
              (x.description || x.kindLabel)} onClick=${() =>
              remove.run().catch(() => {})}><${Icon} name="x" /></button>
        `
        : null}</div>
  `;
}

/** @param {{ a: any }} p */
export function Goal({ a }) {
  const res = useApi(`/accounts/${a.id}/goal`, {}, ['import']);
  const v = /** @type {any} */ (res.data);
  const start = useSubmit(async () => {
    await api.post(`/accounts/${a.id}/goal`);
    toast('Education projection made');
    res.reload();
  });
  if (res.error) return html`<${Failed} error=${res.error} />`;
  if (!v) return html`<${Loading} />`;
  if (!v.beneficiary) {
    return html`<${Empty}>Choose the beneficiary in Settings to project their education.</${Empty}>`;
  }
  const x = v.projection;
  if (!x) {
    return html`<${Empty}>No education projection for ${v.beneficiary.name} yet.
      <div class="mt"><button type="button" class="btn primary" disabled=${start.busy}
        onClick=${() =>
      start.run().catch(
        () => {},
      )}><${Icon} name="plus" /> Project ${v.beneficiary.name}'s education</button></div></${Empty}>`;
  }
  const r = x.result;
  const ans = r.answer;
  return html`
    <div
      class="toolbar"><span class="small dim">Education projection <b>${x.name}</b>${x.active
        ? ' · active'
        : ' · a scenario'}</span>${x.status && x.status !== 'untracked'
        ? html`<span class="pill">${x.status}</span>`
        : null}<span class="spacer"></span><a class="small" href=${`/ui/projections/${x.id}`}>Change it in Projections</a></div>
    <div class="grid g-main">
      <div class="card">
        <h3>${ans.name}'s college fund<span class="spacer"></span><span
        class=${'pill ' + (ans.funded >= 100 ? 'ok' : 'warn')}>${Math.round(
          ans
            .funded,
        )}% funded</span></h3>
        <${FanChart} label=${`${x.name}: projected balance by year`} years=${r.years}
          p=${r.percentiles} marks=${[[ans.firstYear, 'school starts']]} />
        <p
          class="small dim">A model, not a forecast: ${ans.years} years from ${ans
            .firstYear}, each costing ${ans.costBasis === 'typed'
            ? 'the typed amount'
            : `the shipped ${ans.costBasis} average`} of ${money0(ans.costToday)} in today's
          dollars, rising ${r.assumptions.educationInflation}% a year.</p>
      </div>
      <div class="grid" style=${{ alignContent: 'start' }}>
        <${EducationAnswer} a=${ans} />
        <div class="card facts"><h3>Its years</h3>${ans.costs.map((
          /** @type {number} */ c,
          /** @type {number} */ i,
        ) =>
          html`<div class="list-item"><span class="grow dim">${ans.firstYear + i}</span>${
            money0(
              c,
            )
          }</div>`
        )}</div>
      </div>
    </div>
  `;
}

/** @param {number} v */
function money0(v) {
  return money(String(Math.round(v)), { cents: false });
}
