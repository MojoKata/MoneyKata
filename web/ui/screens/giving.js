// Giving (requirements S7.9, S12.2.9): the year's target and progress, donations,
// organisations, and the donor-advised fund.
import { useState } from 'preact/hooks';
import { html } from '../app/html.js';
import { api } from '../api/client.js';
import { useApi, useSubmit } from '../app/hooks.js';
import { date, money, quantity } from '../app/format.js';
import { useTitle } from '../components/frame.js';
import { useDialogGuide, useGuide } from '../components/help.js';
import { Amt } from '../components/amount.js';
import { Chips, Empty, Failed, Loading, Tabs } from '../components/bits.js';
import { Dialog, openDialog } from '../components/dialog.js';
import { errAt, Field, FormError, Input, Seg, Select, SwitchRow } from '../components/fields.js';
import { Icon } from '../components/icon.js';
import { ShareDialog } from '../components/share.js';
import { toast } from '../components/toast.js';
import { ACCEPT, uploadAll } from '../components/receipt.js';
import { TimeChart } from '../charts/chart.js';
import { dec, num } from '../app/dec.js';

const TABS = /** @type {[string, string][]} */ ([
  ['overview', 'Overview'],
  ['donations', 'Donations'],
  ['organisations', 'Organisations'],
  ['fund', 'Donor-advised fund'],
]);
const KINDS = /** @type {[string, string][]} */ ([
  ['cash', 'Cash (card, cheque, transfer)'],
  ['goods', 'Goods, at fair value'],
  ['securities', 'Appreciated shares'],
  ['qcd', 'QCD from an IRA'],
  ['daf-contribution', 'Into a donor-advised fund'],
  ['daf-grant', 'Grant from a donor-advised fund'],
]);
const clean = (/** @type {string} */ s) => (s ? String(s).replace(/[$,\s]/g, '') : '');
const today = () => new Date().toISOString().slice(0, 10);

/** @param {{ tab?: string }} p */
export default function Giving({ tab }) {
  const current = TABS.some(([k]) => k === tab) ? /** @type {string} */ (tab) : 'overview';
  const now = new Date().getFullYear();
  const [year, setYear] = useState(String(now));
  useTitle('Giving');
  useGuide('giving-' + current);
  const res = useApi('/giving', { year }, ['import']);
  const v = /** @type {any} */ (res.data);
  return html`
    <div class="toolbar"><${Tabs} tabs=${TABS} current=${current} base="/ui/giving" /><span
      class="spacer"></span><${Chips} label="Year" value=${year} onChange=${setYear}
      options=${[now - 1, now].map((y) => [String(y), String(y)])} /></div>
    ${res.error
      ? html`<${Failed} error=${res.error} />`
      : !v
      ? html`<${Loading} lines=${6} />`
      : current === 'overview'
      ? html`<${Overview} v=${v} reload=${res.reload} />`
      : current === 'donations'
      ? html`<${Donations} year=${year} reload=${res.reload} />`
      : current === 'organisations'
      ? html`<${Organisations} />`
      : html`<${Fund} v=${v} year=${year} />`}
  `;
}

/** @param {{ v: any, reload: () => void }} p */
function Overview({ v, reload }) {
  const plan = v.plan;
  const editPlan = () => openDialog(PlanDialog, { v }).then((x) => x && reload());
  const record = () => openDialog(DonationDialog, {}).then((x) => x && reload());
  const behind = dec(v.pace).sub(dec(v.given));
  const months = v.byMonth.map((/** @type {string} */ x, /** @type {number} */ i) => [
    new Date(Date.UTC(v.year, i + 1, 0)).toISOString().slice(0, 10),
    x,
  ]).filter((/** @type {[string, string]} */ p) =>
    p[0] <= today() || v.year < new Date().getFullYear()
  );
  const pace = months.map((/** @type {[string, string]} */ [d]) => {
    const start = Date.UTC(v.year, 0, 1);
    const days = (Date.parse(d) - start) / 86400000 + 1;
    return [d, String(Math.round(num(v.target) * days / 365))];
  });
  if (!plan) {
    return html`<${Empty}>No giving plan for ${v.year} yet. Set a target, as a percentage of
      income or an amount, to follow your giving against it.
      <div class="mt"><button type="button" class="btn primary" onClick=${editPlan}>Set a
        target</button></div></${Empty}>
      ${
      num(v.given)
        ? html`<p class="small dim">Given so far in ${v.year}: <${Amt} v=${v.given} />.</p>`
        : null
    }`;
  }
  const most = Math.max(1, ...v.byCause.map((/** @type {any} */ c) => num(c.amount)));
  return html`
    <div class="grid g4">
      <div class="card kpi" data-help="target">
        <div class="label">Target ${v.year}</div>
        <div class="value">
          <${Amt} v=${v.target} cents=${false} />
        </div>
        <div class="delta dim">${plan.targetKind === 'percent'
          ? html`${String(plan.percent)}% of <${Amt} v=${v.income} cents=${false} /> ${
            {
              'take-home': 'take-home pay',
              gross: 'gross income',
              agi: 'estimated AGI',
            }[/** @type {'take-home'|'gross'|'agi'} */ (plan.incomeBasis)]
          }`
          : 'a fixed amount'} · ${plan.level === 'read'
          ? html`shared by ${plan.ownerName}`
          : html`<a href="#" onClick=${(/** @type {Event} */ e) => {
            e.preventDefault();
            editPlan();
          }}>Edit</a>`}${plan.level === 'owner'
          ? html`
            · <a href="#" onClick=${(/** @type {Event} */ e) => {
              e.preventDefault();
              openDialog(ShareDialog, {
                kind: 'giving-plan',
                id: plan.id,
                name: `Giving plan ${plan.year}`,
              });
            }}>Share</a>
          `
          : null}</div>
      </div>
      <div class="card kpi" data-help="given">
        <div class="label">Given</div>
        <div class="value">
          <${Amt} v=${v.given} cents=${false} />
        </div>
        <div class="bar" style=${{ marginTop: '8px' }}><i style=${{
          width: `${Math.min(100, (num(v.given) / Math.max(1, num(v.target))) * 100)}%`,
        }}></i></div>
      </div>
      <div class="card kpi" data-help="pace">
        <div class="label">Pace to date</div>
        <div class="value">
          <${Amt} v=${v.pace} cents=${false} />
        </div>
        <div class="delta">${behind.gt(0)
          ? html`<span class="down"><${Amt} v=${String(behind)} cents=${false} /> behind</span>`
          : html`<span class="up"><${Amt} v=${
            String(behind.neg())
          } cents=${false} /> ahead</span>`}</div>
      </div>
      <div class="card kpi" data-help="projected">
        <div class="label">Projected year end</div>
        <div class="value">
          <${Amt} v=${v.projected} cents=${false} />
        </div>
        <div class="delta dim">with <${Amt} v=${v.pledged} cents=${false} /> of pledges due</div>
      </div>
    </div>
    ${v.missingAcks
      ? html`
        <div class="notice warn mt">
          <${Icon} name="alert" />
          <div>${v.missingAcks} donation${v
              .missingAcks === 1
            ? ''
            : 's'} of $250 or more without a written acknowledgement. <a
                href="/ui/giving/donations">See the donations</a>.</div>
        </div>
      `
      : null}
    ${v.notes.map((/** @type {string} */ n) =>
      html`
        <div class="notice mt">
          <${Icon} name="info" />
          <div>${n}</div>
        </div>
      `
    )}
    <div class="grid g-main mt">
      <div class="card">
        <h3>Given against the target<span class="spacer"></span><button
        class="btn sm primary" onClick=${record}><${Icon} name="plus" /> Record a donation</button></h3>
        <${TimeChart} label=${`Given in ${v.year} against the target`} series=${[
          { name: 'Given', color: '--hue-giving', points: months },
          { name: 'Even pace to the target', color: '--fg-muted', dash: true, points: pace },
        ]} />
        <p class="small dim">${plan.dafCounted === 'funded'
          ? 'A donor-advised fund counts when it is funded; its grants are not counted again.'
          : 'A donor-advised fund counts when it grants, not when it is funded.'}</p>
      </div>
      <div class="grid" style=${{ alignContent: 'start' }}>
        <div class="card"><h3>By cause</h3>${v.byCause.length
          ? v.byCause.map((/** @type {any} */ c) =>
            html`<div class="list-item"><div class="grow"><div class="small">${c.label}</div><div
              class="bar" style=${{ marginTop: '6px' }}><i style=${{
              width: `${(num(c.amount) / most) * 100}%`,
              background: 'var(--hue-giving)',
            }}></i></div></div><span class="num small"><${Amt} v=${c.amount}
              cents=${false} /></span></div>`
          )
          : html`<p class="small dim">Nothing given yet.</p>`}</div>
        <div class="card"><h3>Percent of income</h3>${v.history.map((/** @type {any} */ h) =>
          html`
            <div
              class="list-item"><span class="small" style=${{ width: '48px' }}>${h
                .year}</span><div class="grow"><div class="bar"><i style=${{
                width: `${Math.min(100, num(h.percent) * 5)}%`,
                background: 'var(--hue-giving)',
              }}></i></div></div><span class="num small" style=${{ width: '52px' }}>${h.percent ==
                  null
                ? '—'
                : `${h.percent}%`}</span></div>
          `
        )}</div>
        <div class="card"><h3>By organisation</h3>${v.byOrganisation.map((/** @type {any} */ o) =>
          html`<div class="list-item"><span class="grow">${o.label}</span><${Amt} v=${o.amount}
            cents=${false} /></div>`
        )}</div>
      </div>
    </div>
  `;
}

/** @param {{ year: string, reload: () => void }} p */
function Donations({ year, reload }) {
  const res = useApi('/giving/donations', { year }, ['import']);
  const rows = /** @type {any[]} */ (res.data);
  const again = () => {
    res.reload();
    reload();
  };
  const record = (/** @type {any} */ from) =>
    openDialog(DonationDialog, { from }).then((x) => x && again());
  const open = (/** @type {any} */ d) =>
    d.id ? openDialog(DonationView, { d }).then((x) => x && again()) : record(d);
  if (res.error) return html`<${Failed} error=${res.error} />`;
  if (!rows) return html`<${Loading} />`;
  return html`
    <div class="toolbar"><span class="small dim">Donations come from transactions categorised
      Giving, or are recorded here.</span><span class="spacer"></span><button class="btn primary"
      onClick=${() => record(null)}><${Icon} name="plus" /> Record a donation</button></div>
    ${rows.length
      ? html`
        <div class="card" style=${{ padding: '4px 8px' }}>
          <div class="table-wrap">
            <table
              class="t">
              <caption class="sr-only">Donations</caption>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Organisation</th>
                  <th>Type</th>
                  <th class="num">Amount</th>
                  <th>Deductible</th>
                  <th>Acknowledgement</th>
                </tr>
              </thead>
              <tbody>${rows.map((d) =>
                html`
                  <tr class="click" tabindex="0" onClick=${() => open(d)} onKeyDown=${(
                    /** @type {KeyboardEvent} */ e,
                  ) => e.key === 'Enter' && open(d)}>
                    <td class="small dim" style=${{ whiteSpace: 'nowrap' }}>${date(d.date)}</td>
                    <td>${d.name}${d.id
                      ? null
                      : html`<div class="small dim">from a transaction</div>`}</td>
                    <td class="small">${d.kindLabel}${d.symbol
                      ? html`<div class="dim">${quantity(d.quantity)} ${d.symbol} · ${
                        d.longTerm ? 'held over a year' : 'held under a year'
                      }</div>`
                      : null}</td>
                    <td class="num">
                      <${Amt} v=${d.amount} />
                    </td>
                    <td>${d.kind === 'daf-grant'
                      ? html`<span class="small dim">a grant · not deducted again</span>`
                      : d.deductible
                      ? html`<${Icon} name="check" label="Deductible" />`
                      : html`<span class="pill">no</span>`}</td>
                    <td>${d.acknowledged
                      ? html`<span class="small"><${Icon} name="clip" /> received</span>`
                      : d.needsAck
                      ? html`<span class="pill warn">missing · needed at $250+</span>`
                      : html`<span class="dim">—</span>`}</td>
                  </tr>
                `
              )}</tbody>
            </table>
          </div>
        </div>
      `
      : html`<${Empty}>No donations in ${year} yet.</${Empty}>`}
  `;
}

function Organisations() {
  const res = useApi('/giving/organisations');
  const rows = /** @type {any[]} */ (res.data);
  const open = (/** @type {any} */ o) =>
    openDialog(OrganisationDialog, { o }).then((x) => x && res.reload());
  if (res.error) return html`<${Failed} error=${res.error} />`;
  if (!rows) return html`<${Loading} />`;
  return html`
    <div
      class="toolbar"><span class="spacer"></span><button class="btn primary" onClick=${() =>
        open(null)}><${Icon} name="plus" /> Add an organisation</button></div>
    ${rows.length
      ? html`
        <div class="card" style=${{ padding: '4px 8px' }}>
          <div class="table-wrap">
            <table
              class="t">
              <caption class="sr-only">Organisations</caption>
              <thead>
                <tr>
                  <th>Organisation</th>
                  <th>EIN</th>
                  <th>Deductible</th>
                  <th>Causes</th>
                  <th>Pledge</th>
                  <th class="num">Given this year</th>
                </tr>
              </thead>
              <tbody>${rows.map((o) =>
                html`
                  <tr class="click" tabindex="0" onClick=${() => open(o)} onKeyDown=${(
                    /** @type {KeyboardEvent} */ e,
                  ) => e.key === 'Enter' && open(o)}>
                    <td>${o.name}</td>
                    <td class="small dim" style=${{ whiteSpace: 'nowrap' }}>${o.ein ||
                      '—'}</td>
                    <td>${o.deductible
                      ? html`<${Icon} name="check" label="Deductible" />`
                      : html`<span class="pill">no</span>`}</td>
                    <td class="small">${o.causes.join(', ') ||
                      html`<span class="dim">—</span>`}</td>
                    <td class="small">${o.pledge
                      ? html`<${Amt} v=${o.pledge} cents=${false} /> a ${o.pledgeEvery}`
                      : html`<span class="dim">—</span>`}</td>
                    <td class="num">
                      <${Amt} v=${o.given} cents=${false} />
                    </td>
                  </tr>
                `
              )}</tbody>
            </table>
          </div>
        </div>
      `
      : html`<${Empty}>No organisations yet. Add the charities, churches and causes you give
        to, with their EIN, and any pledges.</${Empty}>`}
  `;
}

/** @param {{ v: any, year: string }} p */
function Fund({ v, year }) {
  const res = useApi('/giving/donations', { year });
  const grants = (/** @type {any[]} */ (res.data) || []).filter((d) => d.kind === 'daf-grant');
  if (!v.funds.length) {
    return html`<${Empty}>No donor-advised fund. Add one as an account of type
      <b>Donor-advised fund</b>: contributions to it are deducted when made, and its grants are
      not deducted again.</${Empty}>`;
  }
  return html`
    ${v.funds.map((/** @type {any} */ f) =>
      html`
        <div class="grid g4 mt">
          <div class="card kpi">
            <div class="label">${f.name}</div>
            <div class="value">
              <${Amt}
                v=${f.balance} cents=${false} />
            </div>
            <div class="delta dim">${f.institution ||
              'the fund'} · not in net worth</div>
          </div>
          <div class="card kpi">
            <div class="label">Contributed ${v.year}</div>
            <div class="value">
              <${Amt}
                v=${f.contributed} cents=${false} />
            </div>
            <div class="delta dim">deducted this year</div>
          </div>
          <div class="card kpi">
            <div class="label">Granted ${v.year}</div>
            <div class="value">
              <${Amt}
                v=${f.granted} cents=${false} />
            </div>
            <div class="delta dim">not deducted again</div>
          </div>
          <div class="card kpi">
            <div class="label">Account</div>
            <div class="value small"><a
                  href=${`/ui/accounts/${f.accountId}`}>Holdings and transactions</a></div>
          </div>
        </div>
      `
    )}
    <div class="card mt"><h3>Grants</h3>${grants.length
      ? grants.map((g) =>
        html`
          <div
            class="list-item"><div class="grow">${g.name}<div class="small dim">${date(
              g.date,
            )}</div></div><span class=${'pill ' + (g.granted ? 'ok' : 'info')}>${g.granted
              ? 'paid'
              : 'pending'}</span> <${Amt} v=${g.amount} cents=${false} /></div>
        `
      )
      : html`<p class="small dim">No grants in ${year}.</p>`}
      <p class="small dim">${v.plan?.dafCounted === 'granted'
        ? 'This plan counts the fund toward the target when it grants.'
        : "This plan counts the fund toward the target when it's funded, so grants aren't counted again."}</p>
    </div>
  `;
}

/** @param {{ close: (v?: any) => void, v: any }} p */
function PlanDialog({ close, v }) {
  useDialogGuide('dialog-giving-plan');
  const p = v.plan;
  const [f, setF] = useState({
    targetKind: p?.targetKind || 'percent',
    percent: p?.percent ? String(p.percent) : '10',
    amount: p?.amount || '',
    incomeBasis: p?.incomeBasis || 'take-home',
    income: p?.income || '',
    dafCounted: p?.dafCounted || 'funded',
  });
  const set = (/** @type {string} */ k) => (/** @type {any} */ x) => setF({ ...f, [k]: x });
  const save = useSubmit(async () => {
    await api.put('/giving/plan', {
      year: v.year,
      targetKind: f.targetKind,
      percent: f.targetKind === 'percent' ? clean(f.percent) : null,
      amount: f.targetKind === 'amount' ? clean(f.amount) : null,
      incomeBasis: f.incomeBasis,
      income: f.incomeBasis === 'take-home' ? null : clean(f.income),
      dafCounted: f.dafCounted,
    });
    toast('Giving plan saved');
    close(true);
  });
  const e = save.error;
  return html`
    <${Dialog} title=${`Giving plan ${v.year}`} close=${close} onSubmit=${() =>
      save.run().catch(() => {})}
      footer=${html`<button class="btn primary" disabled=${save.busy}>Save</button>`}>
      <div class="field" data-help="target-kind" id="x-target-kind"><label>Target</label>
        <${Seg} label="Target" value=${f.targetKind} onChange=${set('targetKind')} options=${[
          ['percent', 'Percent of income'],
          ['amount', 'A fixed amount'],
        ]} /></div>
      ${f.targetKind === 'percent'
        ? html`
          <div class="row">
            <${Field} label="Percent of income" id="percent" error=${errAt(e, 'percent')}>
              <${Input} value=${f.percent} onInput=${set('percent')} inputmode="decimal" />
              </${Field}>
              <${Field} label="Income" id="income-basis" error=${errAt(e, 'incomeBasis')}>
                      <${Select} value=${f.incomeBasis} onChange=${set('incomeBasis')} options=${[
                        ['take-home', 'Income transactions (take-home)'],
                        ['gross', 'Gross income, typed'],
                        ['agi', 'AGI estimate, typed'],
                      ]} /></${Field}>
                  </div>
                  ${f.incomeBasis === 'take-home' ? null : html`
                    <${Field} label=${f.incomeBasis === 'gross' ? 'Gross income' : 'AGI estimate'}
                      id="income" error=${errAt(
                        e,
                        'income',
                      )} hint="From your W-2, pay stubs or last return.">
                      <${Input} value=${f.income} onInput=${set('income')} inputmode="decimal" />
                      </${Field}>
                  `}
        `
        : html`
          <${Field} label="Target amount" id="amount" error=${errAt(e, 'amount')}>
            <${Input} value=${f.amount} onInput=${set('amount')} inputmode="decimal" />
            </${Field}>
        `}
      <${Field} label="Count the donor-advised fund" id="daf-counted" error=${errAt(
        e,
        'dafCounted',
      )} hint="Either way, a dollar through the fund counts once.">
        <${Select} value=${f.dafCounted} onChange=${set('dafCounted')} options=${[
          ['funded', 'When it is funded'],
          ['granted', 'When it grants'],
        ]} /></${Field}>
      <${FormError} error=${e} />
    </${Dialog}>
  `;
}

/** @param {{ close: (v?: any) => void, from?: any }} p */
function DonationDialog({ close, from }) {
  useDialogGuide('dialog-donation');
  const orgs = useApi('/giving/organisations');
  const accounts = useApi('/accounts');
  const [f, setF] = useState({
    kind: 'cash',
    organisationId: '',
    date: from?.date || today(),
    amount: from?.amount || '',
    description: '',
    fromAccountId: '',
    dafAccountId: '',
    lotId: '',
    quantity: '',
    acknowledged: false,
  });
  const set = (/** @type {string} */ k) => (/** @type {any} */ x) => setF({ ...f, [k]: x });
  const all = /** @type {any[]} */ (accounts.data) || [];
  const writable = all.filter((a) => a.active && ['owner', 'write'].includes(a.level));
  const funds = writable.filter((a) => a.type === 'daf');
  const shares = f.kind === 'securities' ||
    (f.kind === 'daf-contribution' && writable.find((a) => a.id === f.fromAccountId)?.investing);
  const holdings = useApi(
    shares && f.fromAccountId ? `/accounts/${f.fromAccountId}/holdings` : null,
  );
  /** @type {[string, string][]} */
  const lots = [];
  for (const h of /** @type {any} */ (holdings.data)?.holdings || []) {
    for (const l of h.lots) {
      if (!l.lotId) continue;
      lots.push([
        `${l.lotId}|${h.price || ''}`,
        `${h.symbol} · ${quantity(l.quantity)} · bought ${date(l.acquiredOn)}${
          l.basis ? ` · basis ${money(l.basis, { cents: false })}` : ''
        }${l.longTerm ? ' · held over a year' : ''}`,
      ]);
    }
  }
  const [lotId, price] = f.lotId.split('|');
  const sources = f.kind === 'securities'
    ? writable.filter((a) => a.investing && a.type !== 'daf')
    : f.kind === 'qcd'
    ? writable.filter((a) => ['ira', '401k', '403b', '457b'].includes(a.type))
    : writable.filter((a) => a.type !== 'daf' && (a.group === 'banking' || a.investing));
  const save = useSubmit(async () => {
    const body = {
      date: f.date,
      kind: f.kind,
      organisationId: f.kind === 'daf-contribution' ? null : f.organisationId || null,
      amount: clean(f.amount) || null,
      description: f.description || null,
      transactionId: from?.transactionId || null,
      fromAccountId: from ? null : f.fromAccountId || null,
      dafAccountId: ['daf-contribution', 'daf-grant'].includes(f.kind)
        ? f.dafAccountId || null
        : null,
      lotId: shares ? lotId || null : null,
      quantity: shares ? clean(f.quantity) || null : null,
      acknowledged: f.acknowledged,
      granted: f.kind === 'daf-grant' ? true : null,
    };
    const out = await api.post('/giving/donations', body, { idempotent: true });
    toast('Donation recorded');
    close(out);
  });
  const e = save.error;
  return html`
    <${Dialog} title=${from ? `Record ${from.name}` : 'Record a donation'} close=${close}
      onSubmit=${() => save.run().catch(() => {})}
      footer=${html`<button class="btn primary" disabled=${save.busy}>Save</button>`}>
      <${Field} label="Type" id="kind" error=${errAt(e, 'kind')}>
        <${Select} value=${f.kind} onChange=${set('kind')} options=${from
          ? KINDS.filter(([k]) => k === 'cash')
          : KINDS} />
        </${Field}>
        <div class="row">
        ${f.kind === 'daf-contribution' ? null : html`
          <${Field} label="Organisation" id="organisation" error=${errAt(
            e,
            'organisationId',
          )}>
            <${Select} value=${f.organisationId} onChange=${set('organisationId')} options=${[
              ['', 'Choose…'],
              ...(/** @type {any[]} */ (orgs.data) || []).map((o) => [o.id, o.name]),
            ]} />
            </${Field}>
        `}
        <${Field} label="Date" error=${errAt(e, 'date')}><${Input} type="date" value=${f.date}
          onInput=${set('date')} /></${Field}>
      </div>
      ${['daf-contribution', 'daf-grant'].includes(f.kind)
        ? html`
          <${Field} label="Donor-advised fund" id="fund" error=${errAt(e, 'dafAccountId')}>
            <${Select} value=${f.dafAccountId} onChange=${set('dafAccountId')} options=${[
              ['', funds.length ? 'Choose…' : 'Add one as an account first'],
              ...funds.map((a) => [a.id, a.name]),
            ]} />
            </${Field}>
        `
        : null}
      ${from || f.kind === 'goods' || f.kind === 'daf-grant' ? null : html`
        <${Field} label="From account" id="from-account" error=${errAt(e, 'fromAccountId')}
          hint=${f.kind === 'cash'
            ? 'Its withdrawal is recorded, categorised Giving. Leave it for one already imported.'
            : ''}>
          <${Select} value=${f.fromAccountId} onChange=${set('fromAccountId')} options=${[
            ['', f.kind === 'cash' ? 'Not recorded here' : 'Choose…'],
            ...sources.map((a) => [a.id, a.name]),
          ]} />
          </${Field}>
      `}
      ${shares
        ? html`
          <${Field} label="From lot" id="lot" error=${errAt(e, 'lotId')}>
            <${Select} value=${f.lotId} onChange=${set('lotId')} options=${[
              ['', lots.length ? 'Choose…' : 'No lots in that account'],
              ...lots,
            ]} />
            </${Field}>
            <div class="row">
              <${Field} label="Shares" id="quantity" error=${errAt(e, 'quantity')}>
                <${Input}
                  value=${f.quantity} onInput=${(/** @type {string} */ x) =>
                    setF({
                      ...f,
                      quantity: x,
                      amount: price && /^\d+(\.\d+)?$/.test(x.trim()) && Number(x)
                        ? String(dec(price).mul(x.trim()).round(2))
                        : f.amount,
                    })} inputmode="decimal" />
                </${Field}>
                <${Field} label="Market value" id="amount" error=${errAt(e, 'amount')}
                  hint="On the day given.">
                  <${Input} value=${f.amount} onInput=${set('amount')}
                    inputmode="decimal" />
                  </${Field}>
                  </div>
                  <div class="notice" style=${{ marginBottom: '12px' }}>
                    <${Icon} name="info" />
                    <div>No gain
                      is realized on donated shares. Held over a year, the deduction is the market value;
                      otherwise it is the basis.</div>
                  </div>
        `
        : html`
          <${Field} label=${f.kind === 'goods' ? 'Fair market value' : 'Amount'} id="amount"
            error=${errAt(e, 'amount')}>
            <${Input} value=${f.amount} onInput=${set('amount')}
              inputmode="decimal" />
            </${Field}>
        `}
      ${f.kind === 'goods'
        ? html`
          <${Field} label="What was given" id="description" error=${errAt(
            e,
            'description',
          )}>
            <${Input} value=${f.description} onInput=${set('description')}
              placeholder="Two bags of clothes" />
            </${Field}>
        `
        : null}
      <${SwitchRow} label="Acknowledgement received"
        hint="A written acknowledgement is needed for any single gift of $250 or more."
        on=${f.acknowledged} onChange=${set('acknowledged')} />
      <${FormError} error=${e} />
    </${Dialog}>
  `;
}

/** A recorded donation: its acknowledgement, a grant paid. */
/** @param {{ close: (v?: any) => void, d: any }} p */
function DonationView({ close, d }) {
  useDialogGuide('dialog-donation');
  const [busy, setBusy] = useState(false);
  const send = async (/** @type {FileList} */ files) => {
    setBusy(true);
    for (const r of await uploadAll(files)) {
      await api.post(`/giving/donations/${d.id}/acknowledgement`, { receiptId: r.id });
    }
    setBusy(false);
    toast('Acknowledgement kept');
    close(true);
  };
  const flip = useSubmit(async (/** @type {any} */ change) => {
    await api.patch(`/giving/donations/${d.id}`, change);
    toast('Saved');
    close(true);
  });
  const remove = useSubmit(async () => {
    await api.del(`/giving/donations/${d.id}`);
    toast('Donation deleted');
    close(true);
  });
  return html`
    <${Dialog} title=${`${d.kindLabel} · ${d.name}`} close=${close} footer=${d.canWrite
      ? html`<button type="button" class="btn danger" onClick=${() =>
        remove.run().catch(() => {})}>Delete</button>`
      : null}>
      <div class="list-item"><span class="grow dim">Date</span>${date(d.date)}</div>
      <div class="list-item"><span class="grow dim">Amount</span><${Amt} v=${d.amount} /></div>
      ${d.symbol
        ? html`
          <div
            class="list-item"><span class="grow dim">Shares</span>${quantity(d.quantity)} ${d
              .symbol} · basis <${Amt} v=${d.basis} /></div>
        `
        : null}
      ${d.description
        ? html`<div class="list-item"><span class="grow dim">Given</span>${d.description}</div>`
        : null}
      <div class="list-item"><span class="grow dim">Deductible</span>${d.deductible
        ? 'yes'
        : 'no'}</div>
      ${d.kind === 'daf-grant' && d.canWrite
        ? html`<${SwitchRow} label="Paid by the fund" on=${!!d.granted} onChange=${(
          /** @type {boolean} */ x,
        ) => flip.run({ granted: x }).catch(() => {})} />`
        : null}
      ${d.canWrite
        ? html`
          <${SwitchRow} label="Acknowledgement received" on=${d.acknowledged}
            onChange=${(/** @type {boolean} */ x) =>
              flip.run({ acknowledged: x }).catch(() => {})} />
          <div
            class="toolbar"><label class="btn sm" for="f-ack-files"><${Icon} name="clip" /> ${busy
              ? 'Uploading…'
              : 'Attach the acknowledgement'}</label><input id="f-ack-files" class="sr-only"
                      type="file" accept=${ACCEPT} data-help="acknowledgement" onChange=${(
                        /** @type {any} */ ev,
                      ) => {
                        send(ev.currentTarget.files);
                        ev.currentTarget.value = '';
                      }} /></div>
        `
        : null}
    </${Dialog}>
  `;
}

/** @param {{ close: (v?: any) => void, o: any }} p */
function OrganisationDialog({ close, o }) {
  useDialogGuide('dialog-organisation');
  const [f, setF] = useState({
    name: o?.name || '',
    ein: o?.ein || '',
    deductible: o ? o.deductible : true,
    causes: (o?.causes || []).join(', '),
    pledge: o?.pledge || '',
    pledgeEvery: o?.pledgeEvery || 'month',
    notes: o?.notes || '',
  });
  const set = (/** @type {string} */ k) => (/** @type {any} */ x) => setF({ ...f, [k]: x });
  const canWrite = !o || o.canWrite;
  const save = useSubmit(async () => {
    const body = {
      name: f.name,
      ein: f.ein || null,
      deductible: f.deductible,
      causes: f.causes.split(',').map((/** @type {string} */ x) => x.trim()).filter(Boolean),
      pledge: clean(f.pledge) || null,
      pledgeEvery: clean(f.pledge) ? f.pledgeEvery : null,
      notes: f.notes || null,
    };
    const out = o
      ? await api.put(`/giving/organisations/${o.id}`, body)
      : await api.post('/giving/organisations', body);
    toast('Saved');
    close(out);
  });
  const e = save.error;
  return html`
    <${Dialog} title=${o ? o.name : 'Add an organisation'} close=${close} onSubmit=${() =>
      canWrite && save.run().catch(() => {})}
      footer=${canWrite
        ? html`<button class="btn primary" disabled=${save.busy}>Save</button>`
        : null}>
      <fieldset disabled=${!canWrite} style=${{ border: 0, padding: 0, margin: 0, minWidth: 0 }}>
        <${Field} label="Name" error=${errAt(e, 'name')}>
          <${Input} value=${f.name}
            onInput=${set('name')} required placeholder="Greater Chicago Food Depository" />
          </${Field}>
          <${Field} label="EIN" error=${errAt(e, 'ein')} hint="Optional: 36-3136294.">
            <${Input} value=${f.ein} onInput=${set('ein')} />
            </${Field}>
            <${SwitchRow} label="Deductible"
              hint="A 501(c)(3) charity. Not a political campaign or a person." on=${f.deductible}
              onChange=${set('deductible')} />
            <${Field} label="Causes" error=${errAt(
              e,
              'causes',
            )} hint="Separated by commas: Hunger, Local.">
              <${Input} value=${f.causes} onInput=${set('causes')} />
              </${Field}>
              <div class="row">
                <${Field} label="Pledge" error=${errAt(
                  e,
                  'pledge',
                )} hint="Shown as expected donations.">
                  <${Input} value=${f.pledge} onInput=${set('pledge')} inputmode="decimal" />
                  </${Field}>
                  <${Field} label="Every" id="pledge-every" error=${errAt(e, 'pledgeEvery')}>
                    <${Select} value=${f.pledgeEvery} onChange=${set('pledgeEvery')} options=${[
                      ['month', 'Month'],
                      ['year', 'Year'],
                    ]} />
                    </${Field}>
                    </div>
                    <${Field} label="Notes" error=${errAt(e, 'notes')}>
                      <textarea class="in" rows="2"
                        value=${f.notes} onInput=${(/** @type {any} */ ev) =>
                          set('notes')(ev.currentTarget.value)}></textarea>
                      </${Field}>
                      <${FormError} error=${e} />
                      </fieldset>
                      </${Dialog}>
  `;
}
