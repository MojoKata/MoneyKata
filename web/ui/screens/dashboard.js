// The Dashboard (requirements S12.2.1): net worth and its change, the net-worth chart with its
// composition by account group, the accounts by group, and what needs attention.
import { useState } from 'preact/hooks';
import { html } from '../app/html.js';
import { useApi } from '../app/hooks.js';
import { ago } from '../app/format.js';
import { useTitle } from '../components/frame.js';
import { useGuide } from '../components/help.js';
import { Amt } from '../components/amount.js';
import { Chips, Failed, GROUP_LABELS, Loading, Tile } from '../components/bits.js';
import { Icon } from '../components/icon.js';
import { RANGES, TimeChart } from '../charts/chart.js';
import { openDialog } from '../components/dialog.js';
import { NewAccount } from './new-account.js';

const GROUP_COLORS = /** @type {Record<string, string>} */ ({
  banking: '--hue-banking',
  investing: '--hue-investing',
  retirement: '--hue-retirement',
  education: '--hue-education',
  crypto: '--hue-crypto',
  giving: '--hue-giving',
  liabilities: '--hue-liability',
  'physical-assets': '--hue-other',
});

export default function Dashboard() {
  useTitle('Dashboard');
  useGuide('dashboard');
  const [range, setRange] = useState('1Y');
  const dash = useApi('/dashboard', {}, ['prices', 'import', 'share']);
  const series = useApi('/dashboard/series', { range }, ['prices', 'import', 'share']);
  if (dash.error) return html`<${Failed} error=${dash.error} />`;
  const d = /** @type {any} */ (dash.data);
  if (!d) return html`<${Loading} lines=${6} />`;
  const s = /** @type {any} */ (series.data);
  const labels = /** @type {Record<string, string>} */ (GROUP_LABELS);
  return html`
    <div class="grid g4">
      <div class="card kpi" data-help="net-worth">
        <div class="label">Net worth</div>
        <div class="value">
          <${Amt} v=${d.netWorth} cents=${false} />
        </div>
        <div class="delta"><${Amt} v=${d.change.day} signed /> today · <${Amt} v=${d.change.month}
          signed cents=${false} /> this month · <${Amt} v=${d.change
            .year} signed cents=${false} /> this year</div>
      </div>
      <div class="card kpi">
        <div class="label">Investments</div>
        <div class="value">
          <${Amt} v=${d.investments} cents=${false} />
        </div>
        <div class="delta">${d.investmentsDay != null
          ? html`<${Amt} v=${d.investmentsDay} signed /> today`
          : html`<span class="dim">none yet</span>`}</div>
      </div>
      <div class="card kpi">
        <div class="label">Cash</div>
        <div class="value">
          <${Amt} v=${d.cash} cents=${false} />
        </div>
        <div class="delta dim">${d.cashAccounts} account${d.cashAccounts === 1 ? '' : 's'} ·
          updated ${ago(d.lastUpdated)}</div>
      </div>
      <div class="card kpi">
        <div class="label">Needs attention</div>
        <div class="value">${d.attention.length}</div>
        <div class="delta dim">${d.attention.length ? 'see below' : 'nothing right now'}</div>
      </div>
    </div>
    <div class="card mt"><h3>Net worth<span class="spacer"></span><${Chips} label="Range"
      value=${range} onChange=${setRange} options=${RANGES} /></h3>
      ${s
        ? html`<${TimeChart} label="Net worth over time, by account group" series=${
          s.groups.map((
            /** @type {string} */ g,
          ) => ({
            name: labels[g] || g,
            color: GROUP_COLORS[g] || '--c8',
            area: true,
            stack: 'groups',
            points: s.points.map((/** @type {any} */ p) => [p.date, p.groups[g]]),
          }))
        } />`
        : html`<${Loading} lines=${4} />`}
    </div>
    <div class="grid g-main mt">
      <div class="card"><h3>Accounts<span class="spacer"></span><button type="button" class="btn sm"
        onClick=${() => openDialog(NewAccount)}><${Icon} name="plus" /> New account</button></h3>
        ${d.groups.length
          ? d.groups.map((/** @type {any} */ g) =>
            html`<a class="list-item" href="/ui/accounts" style=${{ color: 'inherit' }}>
              <${Tile} group=${g.group} /><div class="grow"><b>${labels[g.group] || g.group}</b>
              <div class="small dim">${g.accounts.join(' · ')}</div></div>
              <div class="num"><b><${Amt} v=${g.total} /></b></div></a>`
          )
          : html`<p class="small dim">No accounts yet. Make one, then import its files.</p>`}
      </div>
      <div class="card" data-help="needs-attention"><h3>Needs attention</h3>
        ${d.attention.length
          ? d.attention.map((/** @type {any} */ a) =>
            html`
              <div
                class="list-item"><${Icon} name=${a.kind === 'uncategorised'
                  ? 'info'
                  : 'alert'} /><div class="grow small">${a.text}</div><a href=${a
                  .link}>See</a></div>
            `
          )
          : html`<p class="small dim">Nothing needs you right now.</p>`}
      </div>
    </div>
  `;
}
