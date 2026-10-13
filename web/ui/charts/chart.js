// The chart wrapper (requirements S17.4): Apache ECharts, loaded by a native import() only when
// a chart first draws, themed from tokens.css in both themes, with a table view a screen reader
// can read (S12.8) and no animation when the system asks for reduced motion.
import { useEffect, useRef, useState } from 'preact/hooks';
import { html } from '../app/html.js';
import { date, money, short } from '../app/format.js';
import { theme } from '../store/prefs.js';

/** @type {Promise<typeof import('echarts')> | null} */
let loading = null;
function echarts() {
  loading ??= import('echarts');
  return loading;
}

/** @param {string} name */
function token(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/**
 * A line or area chart of money over time.
 * @param {{ label: string, series: { name: string, color: string, points: [string, string][],
 *   dash?: boolean, area?: boolean, stack?: string }[], tall?: boolean }} p
 */
export function TimeChart({ label, series, tall }) {
  const box = useRef(/** @type {HTMLDivElement | null} */ (null));
  const [table, setTable] = useState(false);
  const themeNow = theme.value;

  useEffect(() => {
    if (table || !box.current) return;
    /** @type {any} */
    let chart = null;
    let live = true;
    const observer = new ResizeObserver(() => chart?.resize());
    echarts().then((ec) => {
      if (!live || !box.current) return;
      chart = ec.init(box.current, null, { renderer: 'svg' });
      const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
      const values = series.flatMap((s) => s.points.map(([, v]) => Number(v)));
      const flat = values.every((v) => v === values[0]);
      // The step between the ticks ECharts chose, read once it has laid the axis out.
      const step = () => {
        const ticks = chart?.getModel().getComponent('yAxis').axis.scale.getTicks() || [];
        return ticks.length > 1 ? Math.abs(ticks[1].value - ticks[0].value) : 0;
      };
      chart.setOption({
        animation: !reduce,
        grid: { left: 64, right: 16, top: 16, bottom: 28 },
        textStyle: { fontFamily: token('--sans'), color: token('--fg-muted') },
        tooltip: {
          trigger: 'axis',
          backgroundColor: token('--bg-4'),
          borderColor: token('--border-strong'),
          textStyle: { color: token('--fg') },
          valueFormatter: (/** @type {number} */ v) => money(v.toFixed(2)),
        },
        xAxis: {
          type: 'time',
          axisLine: { lineStyle: { color: token('--border') } },
          axisLabel: { color: token('--fg-muted') },
        },
        yAxis: {
          type: 'value',
          scale: true,
          // A flat line (an account at $0) gets whole-dollar ticks, not $0.2 steps.
          minInterval: flat ? 1 : 0,
          splitLine: { lineStyle: { color: token('--border') } },
          axisLabel: {
            color: token('--fg-muted'),
            formatter: (/** @type {number} */ v) => short(v, step()),
          },
        },
        series: series.map((s) => ({
          name: s.name,
          type: 'line',
          stack: s.stack,
          // Every value stacks onto the running total, negatives too, so a stack's top edge is
          // the total (net worth: assets less liabilities).
          stackStrategy: s.stack ? 'all' : undefined,
          showSymbol: false,
          data: s.points.map(([d, v]) => [d, Number(v)]),
          lineStyle: {
            color: token(s.color) || s.color,
            width: s.dash ? 1.5 : 2,
            type: s.dash ? 'dashed' : 'solid',
          },
          itemStyle: { color: token(s.color) || s.color },
          areaStyle: s.area ? { opacity: s.stack ? 0.55 : 0.12 } : undefined,
        })),
      }, true);
      observer.observe(box.current);
    });
    return () => {
      live = false;
      observer.disconnect();
      chart?.dispose();
    };
  }, [
    table,
    themeNow,
    JSON.stringify(series.map((s) => [s.name, s.points.length, s.points[s.points.length - 1]])),
  ]);

  const days = [...new Set(series.flatMap((s) => s.points.map(([d]) => d)))].sort();
  const lookup = series.map((s) => new Map(s.points));
  return html`<div>
    ${
    table
      ? html`
        <div class="chart-table table-wrap">
          <table class="t">
            <caption class="sr-only">${label}</caption>
            <thead>
              <tr><th>Date</th>${series.map((s) => html`<th class="num">${s.name}</th>`)}</tr>
            </thead>
            <tbody>${days.map((d) =>
              html`<tr><td>${date(d)}</td>${
                lookup.map((m) =>
                  html`<td class="num amt">${m.has(d) ? money(m.get(d)) : '—'}</td>`
                )
              }</tr>`
            )}</tbody>
          </table>
        </div>
      `
      : html`
        <div class=${'chart-box amt' + (tall ? ' tall' : '')} ref=${box} role="img"
          aria-label=${label}></div>
      `
  }
    <div class="chart-tools">
      ${
    series.length > 1
      ? html`<div class="legend">${
        series.map((s) =>
          html`<span><i style=${{ background: `var(${s.color})` }}></i>${s.name}</span>`
        )
      }</div><span class="spacer"></span>`
      : null
  }
      <button type="button" class="linklike small" aria-pressed=${table ? 'true' : 'false'}
        onClick=${() => setTable(!table)}>${table ? 'Show as chart' : 'Show as table'}</button>
    </div>
  </div>`;
}

/** The range chips charts share (S5.2.1). */
export const RANGES = /** @type {[string, string][]} */ ([
  ['1M', '1M'],
  ['3M', '3M'],
  ['YTD', 'YTD'],
  ['1Y', '1Y'],
  ['5Y', '5Y'],
  ['All', 'All'],
]);

/**
 * Any other chart: ECharts with the given option, behind the same table view.
 * @param {{ label: string, option: (token: (n: string) => string) => any, head: string[],
 *   rows: string[][], legend?: [string, string][], deps: any[] }} p
 */
function Chart({ label, option, head, rows, legend, deps }) {
  const box = useRef(/** @type {HTMLDivElement | null} */ (null));
  const [table, setTable] = useState(false);
  const themeNow = theme.value;
  useEffect(() => {
    if (table || !box.current) return;
    /** @type {any} */
    let chart = null;
    let live = true;
    const observer = new ResizeObserver(() => chart?.resize());
    echarts().then((ec) => {
      if (!live || !box.current) return;
      chart = ec.init(box.current, null, { renderer: 'svg' });
      const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
      chart.setOption({
        animation: !reduce,
        textStyle: { fontFamily: token('--sans'), color: token('--fg-muted') },
        tooltip: {
          backgroundColor: token('--bg-4'),
          borderColor: token('--border-strong'),
          textStyle: { color: token('--fg') },
        },
        ...option(token),
      }, true);
      observer.observe(box.current);
    });
    return () => {
      live = false;
      observer.disconnect();
      chart?.dispose();
    };
  }, [table, themeNow, ...deps]);
  return html`<div>
    ${
    table
      ? html`
        <div class="chart-table table-wrap">
          <table class="t">
            <caption class="sr-only">${label}</caption>
            <thead>
              <tr>${head.map((h, i) => html`<th class=${i ? 'num' : ''}>${h}</th>`)}</tr>
            </thead>
            <tbody>${rows.map((r) =>
              html`<tr>${r.map((v, i) => html`<td class=${i ? 'num amt' : ''}>${v}</td>`)}</tr>`
            )}</tbody>
          </table>
        </div>
      `
      : html`<div class="chart-box amt" ref=${box} role="img" aria-label=${label}></div>`
  }
    <div class="chart-tools">
      ${
    legend
      ? html`<div class="legend">${
        legend.map(([name, color]) =>
          html`<span><i style=${{ background: `var(${color})` }}></i>${name}</span>`
        )
      }</div>`
      : null
  }<span class="spacer"></span>
      <button type="button" class="linklike small" aria-pressed=${table ? 'true' : 'false'}
        onClick=${() => setTable(!table)}>${table ? 'Show as chart' : 'Show as table'}</button>
    </div>
  </div>`;
}

/**
 * Bars per period, one series beside another: planned against actual spending (S7.4).
 * @param {{ label: string, periods: string[], series: { name: string, color: string,
 *   values: string[] }[] }} p
 */
export function BarChart({ label, periods, series }) {
  return html`
    <${Chart} label=${label} legend=${series.map((s) => [s.name, s.color])}
      head=${['', ...series.map((s) => s.name)]}
      rows=${periods.map((p, i) => [p, ...series.map((s) => money(s.values[i]))])}
      deps=${[JSON.stringify([periods, series])]}
      option=${(/** @type {(n: string) => string} */ t) => ({
        grid: { left: 64, right: 16, top: 16, bottom: 28 },
        tooltip: {
          trigger: 'axis',
          backgroundColor: t('--bg-4'),
          borderColor: t('--border-strong'),
          textStyle: { color: t('--fg') },
          valueFormatter: (/** @type {number} */ v) => money(v.toFixed(2)),
        },
        xAxis: {
          type: 'category',
          data: periods,
          axisLine: { lineStyle: { color: t('--border') } },
          axisLabel: { color: t('--fg-muted') },
        },
        yAxis: {
          type: 'value',
          splitLine: { lineStyle: { color: t('--border') } },
          axisLabel: { color: t('--fg-muted'), formatter: (/** @type {number} */ v) => short(v) },
        },
        series: series.map((s) => ({
          name: s.name,
          type: 'bar',
          barMaxWidth: 18,
          data: s.values.map(Number),
          itemStyle: { color: t(s.color) || s.color, borderRadius: [3, 3, 0, 0] },
        })),
      })} />
  `;
}

/**
 * Where the money went: income on the left flowing into spending on the right (S7.4).
 * @param {{ label: string, sources: { name: string, amount: string }[],
 *   uses: { name: string, amount: string }[] }} p
 */
export function FlowChart({ label, sources, uses }) {
  const colors = ['--c1', '--c2', '--c3', '--c4', '--c5', '--c6', '--c7', '--c8'];
  const total = sources.reduce((a, s) => a + Number(s.amount), 0);
  return html`
    <${Chart} label=${label} head=${['', 'Amount']}
      rows=${[
        ...sources.map((s) => [`In: ${s.name}`, money(s.amount)]),
        ...uses.map((u) => [`Out: ${u.name}`, money(u.amount)]),
      ]}
      deps=${[JSON.stringify([sources, uses])]}
      option=${(/** @type {(n: string) => string} */ t) => ({
        tooltip: {
          backgroundColor: t('--bg-4'),
          borderColor: t('--border-strong'),
          textStyle: { color: t('--fg') },
          valueFormatter: (/** @type {number} */ v) => money(v.toFixed(2)),
        },
        series: [{
          type: 'sankey',
          left: 8,
          right: 120,
          top: 8,
          bottom: 8,
          nodeGap: 10,
          draggable: false,
          label: { color: t('--fg'), fontSize: 12 },
          lineStyle: { color: 'gradient', opacity: 0.35 },
          data: [
            ...sources.map((s, i) => ({
              name: s.name,
              itemStyle: { color: t(colors[i % colors.length]) },
            })),
            { name: 'Income', itemStyle: { color: t('--accent') } },
            ...uses.map((u, i) => ({
              name: u.name,
              itemStyle: { color: t(colors[(i + 2) % colors.length]) },
            })),
          ],
          // Every source into one Income node, which spreads into the uses in proportion.
          links: [
            ...sources.map((s) => ({ source: s.name, target: 'Income', value: Number(s.amount) })),
            ...uses.map((u) => ({
              source: 'Income',
              target: u.name,
              value: Math.min(Number(u.amount), total || Number(u.amount)),
            })),
          ],
        }],
      })} />
  `;
}
