// Styled tooltips that also show on keyboard focus and reach screen readers (S12.1.3): any
// element with data-tip shows it; the text is also its aria-label when it has no text of its own.
// With data-tip-title it shows as a card: a guide's acronym (data-tip-term), what it stands for,
// and the text under them (S12.7.7). A tooltip that would run off the bottom shows above.
import { signal } from '@preact/signals';
import { useLayoutEffect, useRef } from 'preact/hooks';
import { html } from '../app/html.js';

const tip = signal(
  /** @type {{ text: string, title: string, term: string, x: number, y: number, above: number } | null} */ (null),
);

/** @param {Event} e */
function show(e) {
  const el = /** @type {HTMLElement} */ (e.target)?.closest?.('[data-tip]');
  if (!el) return;
  const r = el.getBoundingClientRect();
  tip.value = {
    text: el.getAttribute('data-tip') || '',
    title: el.getAttribute('data-tip-title') || '',
    term: el.getAttribute('data-tip-term') || '',
    x: r.left,
    y: r.bottom + 6,
    above: r.top - 6,
  };
}

function hide() {
  tip.value = null;
}

export function installTooltips() {
  document.addEventListener('mouseover', show);
  document.addEventListener('focusin', show);
  document.addEventListener('mouseout', hide);
  document.addEventListener('focusout', hide);
}

export function TooltipHost() {
  const ref = useRef(/** @type {HTMLDivElement | null} */ (null));
  const t = tip.value;
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el || !t) return;
    const fits = t.y + el.offsetHeight <= innerHeight - 8;
    el.style.top = (fits ? t.y : Math.max(8, t.above - el.offsetHeight)) + 'px';
  }, [t]);
  if (!t) return null;
  const style = { left: Math.min(t.x, innerWidth - 330) + 'px', top: t.y + 'px' };
  if (!t.title) {
    return html`<div class="tooltip" role="tooltip" ref=${ref} style=${style}>${t.text}</div>`;
  }
  const term = t.term ? html`<span class="term-abbr">${t.term}</span>` : null;
  return html`
    <div class="tooltip term-tip" role="tooltip" ref=${ref} style=${style}>
      <div class="term-head">${term}<b>${t.title}</b></div>
      <div class="term-text">${t.text}</div>
    </div>
  `;
}
