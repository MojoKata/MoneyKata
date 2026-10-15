// Strategies (requirements S3.5): legs held together, shown as one with their figures at
// expiry and capital at risk now and at open; the groupings and rolls proposed; a strategy's
// settings (its name, cash-secured, the margin for undefined risk) and undoing it. Grouping is a
// label: each leg keeps its own lots, gains and wash sales.
import { useState } from 'preact/hooks';
import { html } from '../app/html.js';
import { api } from '../api/client.js';
import { useApi, useSubmit } from '../app/hooks.js';
import { date, quantity } from '../app/format.js';
import { Amt } from './amount.js';
import { Dec, dec } from '../app/dec.js';
import { Empty, Failed, Loading } from './bits.js';
import { Dialog, openDialog } from './dialog.js';
import { errAt, Field, FormError, Input, SwitchRow } from './fields.js';
import { useDialogGuide } from './help.js';
import { Icon } from './icon.js';
import { toast } from './toast.js';

/** "Short 1 SPY 20NOV26 540 P", or "Long 100 AAPL". @param {any} x */
const legLine = (x) => {
  const n = dec(x.quantity);
  if (n.isZero()) return `${x.symbol} · closed ${x.closedOn ? date(x.closedOn) : ''}`;
  return `${n.isNegative() ? 'Short' : 'Long'} ${quantity(n.abs())} ${x.symbol}`;
};

/** @param {any} v @param {boolean} cents */
const money = (v, cents = false) =>
  v == null ? html`<span class="dim">unlimited</span>` : html`<${Amt} v=${v} cents=${cents} />`;

export function Strategies() {
  const res = useApi('/positions/strategies', {}, ['import', 'prices']);
  const v = /** @type {any} */ (res.data);
  const act = useSubmit(async (/** @type {() => Promise<any>} */ f) => {
    await f();
    res.reload();
  });
  if (res.error) return html`<${Failed} error=${res.error} />`;
  if (!v) return html`<${Loading} lines=${4} />`;
  const group = (/** @type {any} */ p, /** @type {boolean} */ dismiss) =>
    act.run(() =>
      api.post('/strategies', {
        accountId: p.accountId,
        legs: p.legs.map((/** @type {any} */ l) => ({
          instrumentId: l.instrumentId,
          ...(l.quantity ? { quantity: l.quantity } : {}),
        })),
        dismiss,
      }).then(() => toast(dismiss ? 'Left as they are' : `Grouped as a ${p.shape.toLowerCase()}`))
    ).catch((e) => toast(e.message));
  const roll = (/** @type {any} */ p, /** @type {boolean} */ keep) => {
    const st = v.strategies.find((/** @type {any} */ x) => x.id === p.strategyId);
    if (!st) return;
    act.run(() =>
      api.patch(
        `/strategies/${st.id}`,
        keep ? { roll: [{ instrumentId: p.legs[0].instrumentId }] } : {
          declineRoll: [p.legs[0].instrumentId],
        },
        st.version,
      ).then(() => toast(keep ? 'Rolled into the strategy' : 'Left on its own'))
    ).catch((e) => toast(e.message));
  };
  const open = v.strategies.filter((/** @type {any} */ x) => !x.closedOn);
  const closed = v.strategies.filter((/** @type {any} */ x) => x.closedOn);
  const total = (/** @type {string} */ k) =>
    Dec.sum(
      open.filter((/** @type {any} */ x) => x[k] != null).map((/** @type {any} */ x) => dec(x[k])),
    );
  return html`
    ${v.proposals.map((/** @type {any} */ p) =>
      html`
        <div class="notice mb" role="status">
          <${Icon} name="info" />
          <div>${p.kind === 'roll'
            ? html`
              ${p.legs[0].symbol} opened ${date(p.openedOn)} in ${p.accountName}, the day a leg of
                        <b>${p.shape}</b> on ${p
                          .underlying} closed: a roll? <button type="button" class="btn sm
                        primary" disabled=${act.busy} onClick=${() =>
                          roll(p, true)}>Keep it in the strategy</button> <button
                type="button" class="btn sm"
                disabled=${act.busy} onClick=${() => roll(p, false)}>Not a roll</button>
            `
            : html`
              ${p.legs.length} legs on ${p.underlying} ${p.kind === 'covered-call'
                ? 'in'
                : `opened ${date(p.openedOn)} in`} ${p.accountName} look like a <b>${p.shape
                .toLowerCase()}</b>: ${p.legs.map((/** @type {any} */ l) =>
                  l.quantity ? `${quantity(l.quantity)} ${l.symbol}` : l.symbol
                ).join(', ')}. <button
                type="button" class="btn sm primary" disabled=${act.busy}
                onClick=${() =>
                  group(p, false)}>Group them</button> <button type="button" class="btn sm"
                disabled=${act.busy} onClick=${() => group(p, true)}>Not a strategy</button>
            `}</div>
        </div>
      `
    )}
    ${v.strategies.length
      ? html`
        <div class="card" style=${{ padding: '4px 8px' }}>
          <div class="table-wrap">
            <table class="t">
                <caption class="sr-only">Strategies</caption>
                <thead><tr><th>Strategy</th><th class="num">Credit</th><th class="num">P/L</th><th
                  class="num">Max profit</th><th class="num">Max loss</th><th>Breakeven</th><th class="num"
                  data-help="at-risk-now">At risk now</th><th class="num" data-help="at-open">At open</th><th
                  ></th></tr></thead>
                <tbody>${[...open, ...closed].map((/** @type {any} */ x) =>
                  html`
                    <tr class=${x.closedOn ? 'dim' : ''}>
                      <td
                        style=${{ whiteSpace: 'nowrap' }}><b>${x.name}</b> · ${x
                          .underlying}${x.name !==
                            x.shape
                          ? html`
                            <span class="small dim">(${x.shape})</span>
                          `
                          : null}<div class="small dim">${x.accountName} · opened ${date(
                            x.openedOn,
                          )}${x
                            .closedOn
                          ? ` · closed ${date(x.closedOn)}`
                          : ''}</div>${x.legs.map((/** @type {any} */ l) =>
                            html`<div class="small dim">└ ${legLine(l)}</div>`
                          )}</td>
                      <td class="num">
                        <${Amt} v=${x.credit} signed cents=${false} />
                      </td>
                      <td class="num">${x.pl == null
                        ? '—'
                        : html`<${Amt} v=${x.pl} signed cents=${false} />`}</td>
                      <td class="num">${x.expiryKnown
                        ? money(x.maxProfit)
                        : html`<span class="dim">—</span>`}</td>
                      <td class="num">${x.expiryKnown
                        ? money(x.maxLoss)
                        : html`<span class="dim">—</span>`}</td>
                      <td class="small">${x.expiryKnown
                        ? x.breakevens.map((/** @type {any} */ b) => String(b)).join(' · ') || '—'
                        : 'P/L only: it rests on volatility'}</td>
                      <td class="num">${x.closedOn ? '—' : money(x.capitalAtRiskNow)}</td>
                      <td class="num">${money(x.capitalAtRiskAtOpen)}${x.returnPct != null
                        ? html`<div class="small">${x.returnPct}%</div>`
                        : null}</td>
                      <td>${x.canWrite
                        ? html`<button type="button" class="btn sm" onClick=${() =>
                          openDialog(StrategyDialog, { x }).then((ok) =>
                            ok && res.reload()
                          )}>Edit…</button>`
                        : null}</td>
                    </tr>
                  `
                )}</tbody>
                ${open.length
                  ? html`
                    <tfoot>
                      <tr>
                        <td>Open strategies</td>
                        <td></td>
                        <td class="num">
                          <${Amt} v=${String(
                            total('pl'),
                          )} signed cents=${false} />
                        </td>
                        <td colspan="3"></td>
                        <td class="num">
                          <${Amt} v=${String(
                            total('capitalAtRiskNow'),
                          )} cents=${false} />
                        </td>
                        <td class="num">
                          <${Amt} v=${String(
                            total('capitalAtRiskAtOpen'),
                          )} cents=${false} />
                        </td>
                        <td></td>
                      </tr>
                    </tfoot>
                  `
                  : null}
              </table>
          </div>
        </div>
      `
      : html`<${Empty}>No strategies yet. Legs opened together are offered here; or select legs on
        the Open tab and Group them.</${Empty}>`}
    <p class="small dim mt">Grouping is a label: each leg keeps its own lots, gains and wash sales.
      Capital at risk is the most the strategy can lose at expiry; for undefined risk, the margin
      you type.</p>
  `;
}

/** A strategy's name, cash-secured tick and margin, or undo it. @param {{ close: (v?: any) => void, x: any }} p */
function StrategyDialog({ close, x }) {
  useDialogGuide('dialog-strategy');
  const [f, setF] = useState({
    name: x.name === x.shape ? '' : x.name,
    cashSecured: x.cashSecured,
    margin: x.marginRequirement || '',
  });
  const save = useSubmit(async () => {
    await api.patch(`/strategies/${x.id}`, {
      name: f.name || null,
      cashSecured: f.cashSecured,
      marginRequirement: f.margin ? String(f.margin).replace(/[$,\s]/g, '') : null,
    }, x.version);
    toast('Saved');
    close(true);
  });
  const [armed, setArmed] = useState(false);
  const undo = useSubmit(async () => {
    if (!armed) return setArmed(true);
    await api.del(`/strategies/${x.id}`, x.version);
    toast('Ungrouped: the legs stand on their own');
    close(true);
  });
  const shortPut = x.legs.some((/** @type {any} */ l) =>
    l.kind === 'put' && dec(l.quantity).isNegative()
  );
  return html`
    <${Dialog} title=${`${x.name} · ${x.underlying}`} close=${close}
      onSubmit=${() => save.run().catch(() => {})}
      footer=${html`
        <button type="button" class="btn danger" disabled=${undo.busy}
          onClick=${() => undo.run().catch(() => {})}>${armed
            ? 'Ungroup it?'
            : 'Ungroup'}</button><span
          class="spacer"></span><button class="btn primary" disabled=${save.busy}>Save</button>
      `}>
      <${Field} label="Name" id="strategy-name" hint=${`Empty: its shape, ${x.shape.toLowerCase()}.`}>
        <${Input} value=${f.name} onInput=${(/** @type {string} */ v) => setF({ ...f, name: v })} />
      </${Field}>
      ${shortPut
        ? html`
          <${SwitchRow} label="Cash-secured" hint="The cash to buy the shares is set aside."
            on=${f.cashSecured} onChange=${(/** @type {boolean} */ v) =>
              setF({ ...f, cashSecured: v })} />
        `
        : null}
      <${Field} label="Margin requirement" id="margin-requirement"
        error=${errAt(save.error, 'marginRequirement')}
        hint="Your broker's, for a strategy whose loss has no limit: its capital at risk.">
        <${Input} value=${f.margin} onInput=${(/** @type {string} */ v) =>
          setF({ ...f, margin: v })}
          inputmode="decimal" placeholder="unlimited" />
      </${Field}>
      <p class="small dim">Ungrouping leaves each leg as it is: its lots, gains and history don't
        change.</p>
      <${FormError} error=${save.error || undo.error} shown=${['marginRequirement']} />
    </${Dialog}>
  `;
}

/**
 * Group the legs selected on the Open tab.
 * @param {{ rows: any[], done: () => void }} p
 */
export function GroupButton({ rows, done }) {
  const act = useSubmit(async () => {
    await api.post('/strategies', {
      accountId: rows[0].accountId,
      legs: rows.map((r) => ({
        instrumentId: r.instrumentId,
        ...(r.instrumentClass === 'option' ? {} : { quantity: r.quantity }),
      })),
    });
    toast('Grouped as a strategy');
    done();
  });
  const one = new Set(rows.map((r) => r.accountId)).size === 1;
  return html`
    <button type="button" class="btn" disabled=${act.busy || !rows.length || !one}
      title=${one ? undefined : 'Legs in one account'}
      onClick=${() => act.run().catch((e) => toast(e.message))}><${Icon} name="plus" /> Group ${rows
        .length} leg${rows.length === 1 ? '' : 's'}</button>
  `;
}
