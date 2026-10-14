// Positions (requirements S3.1, S3.9, S12.2): what is held, from open to closed, with each lot's
// holding period, and gains by year, month, account, instrument or term.
import { useState } from 'preact/hooks';
import { html } from '../app/html.js';
import { useApi } from '../app/hooks.js';
import { date, quantity } from '../app/format.js';
import { useTitle } from '../components/frame.js';
import { useGuide } from '../components/help.js';
import { Amt } from '../components/amount.js';
import { Chips, Empty, Failed, Loading, Tabs } from '../components/bits.js';
import { openDialog } from '../components/dialog.js';
import { Icon } from '../components/icon.js';
import { OptionTrade } from '../components/optiontrade.js';

const TABS = /** @type {[string, string][]} */ ([
  ['open', 'Open'],
  ['closed', 'Closed'],
  ['gains', 'Gains'],
]);
const KIND = /** @type {[string, string][]} */ ([
  ['all', 'All'],
  ['stocks', 'Stocks and funds'],
  ['options', 'Options'],
  ['crypto', 'Crypto'],
]);
const TERM = /** @type {Record<string, string>} */ ({
  short: 'Short term',
  long: 'Long term',
  mixed: 'Mixed',
});

/** @param {{ tab?: string }} p */
export default function Positions({ tab }) {
  const current = TABS.some(([k]) => k === tab) ? /** @type {string} */ (tab) : 'open';
  useTitle('Positions');
  useGuide('positions-' + current);
  const [kind, setKind] = useState('all');
  const res = useApi('/positions', { kind }, ['import', 'prices']);
  const v = /** @type {any} */ (res.data);
  return html`
    ${v
      ? html`
        <div class="grid g4">
          <div class="card kpi">
            <div class="label">Unrealized gain</div>
            <div class="value">
              <${Amt}
                v=${v.summary.unrealized} signed cents=${false} />
            </div>
            <div class="delta dim">open
                  positions</div>
          </div>
          <div class="card kpi">
            <div class="label">Realized ${new Date().getFullYear()}</div>
            <div
              class="value">
              <${Amt} v=${v.summary.realizedThisYear} signed cents=${false} />
            </div>
            <div class="delta dim">short <${Amt} v=${v.summary
              .realizedShort} signed cents=${false} />
                    · long <${Amt} v=${v.summary.realizedLong} signed cents=${false} /></div>
          </div>
          <div class="card kpi">
            <div class="label">Open positions</div>
            <div class="value">${v.open
              .length}</div>
            <div class="delta dim">${v.open.filter((/** @type {any} */ r) => r.side === 'short')
              .length} short</div>
          </div>
          <div class="card kpi">
            <div class="label">Closed</div>
            <div class="value">${v.closed
              .length}</div>
            <div class="delta dim">closing trades</div>
          </div>
        </div>
      `
      : null}
    <div class="toolbar mt">
      <${Chips} label="Show" value=${kind} onChange=${setKind}
        options=${KIND} />
      <span class="spacer"></span>
      <button class="btn primary" onClick=${() =>
        openDialog(OptionTrade, {}).then((x) => x && res.reload())}><${Icon} name="plus" /> Record
        an option trade</button>
    </div>
    <${Tabs} tabs=${TABS} current=${current} base="/ui/positions" />
    ${res.error
      ? html`<${Failed} error=${res.error} />`
      : !v
      ? html`<${Loading} lines=${6} />`
      : current === 'open'
      ? html`<${Open} rows=${v.open} />`
      : current === 'closed'
      ? html`<${Closed} rows=${v.closed} />`
      : html`<${Gains} />`}
  `;
}

/** @param {{ rows: any[] }} p */
function Open({ rows }) {
  const [shown, setShown] = useState(/** @type {string | null} */ (null));
  if (!rows.length) return html`<${Empty}>Nothing open.</${Empty}>`;
  return html`
    <div class="card" style=${{ padding: '4px 8px' }}>
      <div class="table-wrap">
        <table class="t">
          <caption class="sr-only">Open positions</caption>
          <thead>
            <tr>
              <th>Instrument</th>
              <th>Account</th>
              <th>Side</th>
              <th class="num">Quantity</th>
              <th class="num">Cost</th>
              <th class="num">Market value</th>
              <th class="num">Unrealized</th>
              <th>Term</th>
            </tr>
          </thead>
          <tbody>${rows.map((r) => {
            const key = r.accountId + r.instrumentId;
            return html`
              <tr class="click" tabindex="0" aria-expanded=${shown === key ? 'true' : 'false'}
                onClick=${() => setShown(shown === key ? null : key)} onKeyDown=${(
                  /** @type {KeyboardEvent} */ e,
                ) => e.key === 'Enter' && setShown(shown === key ? null : key)}>
                <td><b>${r.symbol}</b>${r.name
                  ? html`<div class="small dim">${r.name}</div>`
                  : null}</td>
                <td class="small dim">${r.accountName}</td>
                <td><span class=${'pill ' + (r.side === 'short' ? 'warn' : '')}>${r.side === 'short'
                  ? 'Short'
                  : 'Long'}</span></td>
                <td class="num">${quantity(r.quantity)}</td>
                <td class="num">${r.cost ? html`<${Amt} v=${r.cost} />` : html`
                  <span
                    class="pill warn">missing</span>
                `}</td>
                <td class="num">${r.value ? html`<${Amt} v=${r.value} />` : '—'}</td>
                <td class="num">${r.unrealized
                  ? html`
                    <${Amt} v=${r.unrealized} signed />
                    <div class="small">${r.unrealizedPct}%</div>
                  `
                  : '—'}</td>
                <td class="small">${TERM[r.term]}<div class="dim">${r.days} days</div></td>
              </tr>
                        ${shown === key
                          ? html`
                            <tr>
                              <td colspan="8">
                                <div class="small" style=${{ padding: '4px 0' }}>${r.lots.map((
                                  /** @type {any} */ l,
                                ) =>
                                  html`
                                    <div
                                      class="list-item"><span class="grow">${quantity(
                                        l.quantity,
                                      )} bought ${date(
                                        l.acquiredOn,
                                      )} · ${l.days} days · ${l.longTerm
                                        ? 'long term'
                                        : 'short term'}</span>${l.basis
                                        ? html`<${Amt} v=${l.basis} />`
                                        : html`<span class="pill warn">no basis</span>`}</div>
                                  `
                                )}${Number(r.realized)
                                  ? html`<div class="dim">Realized so far: <${Amt} v=${r.realized} signed /></div>`
                                  : null}</div>
                              </td>
                            </tr>
                          `
                          : null}
            `;
          })}</tbody>
        </table>
      </div>
    </div>
  `;
}

/** @param {{ rows: any[] }} p */
function Closed({ rows }) {
  if (!rows.length) return html`<${Empty}>Nothing closed yet.</${Empty}>`;
  const total = rows.reduce((t, r) => t + Number(r.realized || 0), 0);
  return html`
    <div class="card" style=${{ padding: '4px 8px' }}>
      <div class="table-wrap">
        <table class="t">
          <caption class="sr-only">Closing trades</caption>
          <thead>
            <tr>
              <th>Instrument</th>
              <th>Account</th>
              <th>Opened</th>
              <th>Closed</th>
              <th>How</th>
              <th class="num">Proceeds</th>
              <th class="num">Cost</th>
              <th class="num">Realized</th>
              <th>Term</th>
            </tr>
          </thead>
          <tbody>${rows.map((r) =>
            html`
              <tr>
                <td><b>${r.symbol}</b> <span class="small dim">${quantity(r.quantity)}</span></td>
                <td class="small dim">${r.accountName}</td>
                <td class="small dim">${date(r.opened)}</td>
                <td class="small dim">${date(r.closed)}</td>
                <td class="small">${r.how}</td>
                <td class="num">
                  <${Amt} v=${r.proceeds} />
                </td>
                <td class="num">${r.cost
                  ? html`<${Amt} v=${r.cost} />`
                  : html`<span class="pill warn">missing</span>`}</td>
                <td class="num">${r.realized ? html`<${Amt} v=${r.realized} signed />` : '—'}</td>
                <td class="small">${TERM[r.term]}</td>
              </tr>
            `
          )}</tbody>
          <tfoot>
            <tr>
              <td colspan="7">Realized, all shown</td>
              <td class="num">
                <${Amt}
                  v=${String(total)} signed />
              </td>
              <td></td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  `;
}

function Gains() {
  const now = new Date().getFullYear();
  const [by, setBy] = useState('year');
  const [year, setYear] = useState('');
  const res = useApi('/positions/gains', { by, year: year || undefined }, ['import', 'prices']);
  const v = /** @type {any} */ (res.data);
  /** @param {any[]} rows @param {string} title */
  const table = (rows, title) =>
    html`<div class="card" style=${{ padding: '4px 8px' }}><h3 style=${{
      padding: '8px 8px 0',
    }}>${title}</h3>${
      rows.length
        ? html`
          <div class="table-wrap">
            <table class="t">
              <caption class="sr-only">${title}</caption>
              <thead>
                <tr>
                  <th></th>
                  <th class="num">Short term</th>
                  <th class="num">Long term</th>
                  <th class="num">Total</th>
                </tr>
              </thead>
              <tbody>${rows.map((g) =>
                html`
                  <tr>
                    <td>${g.label}</td>
                    <td class="num">
                      <${Amt} v=${g.shortTerm} signed />
                    </td>
                    <td class="num">
                      <${Amt} v=${g.longTerm} signed />
                    </td>
                    <td class="num"><b><${Amt}
                                v=${g.total} signed /></b></td>
                  </tr>
                `
              )}</tbody>
            </table>
          </div>
        `
        : html`<p class="small dim">None.</p>`
    }</div>`;
  return html`
    <div
      class="toolbar"><${Chips} label="By" value=${by} onChange=${setBy} options=${[
        ['year', 'Year'],
        ['month', 'Month'],
        ['account', 'Account'],
        ['instrument', 'Instrument'],
        ['term', 'Term'],
      ]} /><span class="spacer"></span><${Chips} label="Year" value=${year} onChange=${setYear}
      options=${[
        ['', 'All years'],
        ...[now - 2, now - 1, now].map((y) => [String(y), String(y)]),
      ]} /></div>
    ${res.error ? html`<${Failed} error=${res.error} />` : !v ? html`<${Loading} />` : html`
      <div class="grid g2">${table(v.realized, 'Realized')}${table(
        v.unrealized,
        by === 'instrument' ? 'Unrealized, by instrument' : 'Unrealized, by account',
      )}</div>
    `}
  `;
}
