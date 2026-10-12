// The chart wrapper (requirements §20.4): Apache ECharts, loaded by a native import() only when
// a chart first draws, themed from tokens.css in both themes, with a table view a screen reader
// can read (§15.8) and no animation when the system asks for reduced motion.
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
          splitLine: { lineStyle: { color: token('--border') } },
          axisLabel: {
            color: token('--fg-muted'),
            formatter: (/** @type {number} */ v) => short(v),
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

/** The range chips charts share (§8.2.1). */
export const RANGES = /** @type {[string, string][]} */ ([
  ['1M', '1M'],
  ['3M', '3M'],
  ['YTD', 'YTD'],
  ['1Y', '1Y'],
  ['5Y', '5Y'],
  ['All', 'All'],
]);
