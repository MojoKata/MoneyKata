// The pager for long lists (requirements §15.1.3): a page size of 100, 500 or 1000 kept per
// browser, pages by cursor, and rows that arrived while reading counted on an orange +N new
// pill instead of shifting the page.
import { html } from '../app/html.js';
import { pageSize } from '../store/prefs.js';

/**
 * @param {{ shown: number, page: number, hasNext: boolean, onPage: (n: number) => void,
 *   newer?: number, onNewer?: () => void, label: string }} p
 */
export function Pager({ shown, page, hasNext, onPage, newer = 0, onNewer, label }) {
  const first = (page - 1) * pageSize.value + 1;
  return html`<div class="pager">
    <label class="small dim" for=${'pg-' + label}>Page size</label>
    <select class="in" id=${'pg-' + label} style=${{ width: '90px', height: '30px' }}
      value=${String(pageSize.value)} onChange=${(/** @type {any} */ e) => {
    pageSize.value = Number(e.currentTarget.value);
    onPage(1);
  }}>
      ${[100, 500, 1000].map((n) => html`<option value=${n}>${n}</option>`)}
    </select>
    <span class="small dim">${shown ? `${first}–${first + shown - 1}` : 'none'}</span>
    <div class="jump">
      <button type="button" disabled=${page <= 1} onClick=${() =>
    onPage(page - 1)} aria-label="Previous page">‹</button>
      <button type="button" class="on" aria-current="page">${page}</button>
      <button type="button" disabled=${!hasNext} onClick=${() =>
    onPage(page + 1)} aria-label="Next page">›</button>
    </div>
    <span class="spacer"></span>
    ${
    newer
      ? html`<button type="button" class="pill new" onClick=${onNewer}>+${newer} new</button>`
      : null
  }
  </div>`;
}
