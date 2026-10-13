// Dialogs (requirements S12.1.3): one at a time, trapping focus and returning it when closed.
// openDialog() resolves with what the dialog closes with.
import { signal } from '@preact/signals';
import { useEffect, useRef } from 'preact/hooks';
import { html } from '../app/html.js';
import { Icon } from './icon.js';

/** @type {import('@preact/signals').Signal<{ comp: any, props: any, resolve: (v: any) => void,
 *   back: HTMLElement | null } | null>} */
export const current = signal(null);

/**
 * @param {any} comp  a component taking { close, ...props }
 * @param {any} [props]
 * @returns {Promise<any>}
 */
export function openDialog(comp, props = {}) {
  return new Promise((resolve) => {
    current.value = {
      comp,
      props,
      resolve,
      back: /** @type {HTMLElement | null} */ (document.activeElement),
    };
  });
}

/** @param {any} [value] */
export function closeDialog(value) {
  const d = current.value;
  if (!d) return;
  current.value = null;
  d.resolve(value);
  setTimeout(() => d.back?.focus?.(), 0);
}

export function DialogHost() {
  const d = current.value;
  if (!d) return null;
  const C = d.comp;
  return html`<${C} ...${d.props} close=${closeDialog} />`;
}

/**
 * The frame every dialog draws in.
 * @param {{ title: string, wide?: boolean, guide?: string, close: (v?: any) => void,
 *   footer?: any, note?: any, children: any, onSubmit?: () => void }} p
 */
export function Dialog({ title, wide, close, footer, note, children, onSubmit }) {
  const box = useRef(/** @type {HTMLDivElement | null} */ (null));
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const first = el.querySelector(
      'input:not([type=hidden]),select,textarea,button:not(.dialog-x)',
    );
    /** @type {HTMLElement | null} */ (first)?.focus();
    const onKey = (/** @type {KeyboardEvent} */ e) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        close();
      } else if (e.key === 'Tab') {
        const all = [...el.querySelectorAll(
          'a[href],button:not([disabled]),input,select,textarea,[tabindex]:not([tabindex="-1"])',
        )].filter((x) => /** @type {HTMLElement} */ (x).offsetParent !== null);
        if (!all.length) return;
        const firstEl = /** @type {HTMLElement} */ (all[0]);
        const lastEl = /** @type {HTMLElement} */ (all[all.length - 1]);
        if (e.shiftKey && document.activeElement === firstEl) {
          e.preventDefault();
          lastEl.focus();
        } else if (!e.shiftKey && document.activeElement === lastEl) {
          e.preventDefault();
          firstEl.focus();
        }
      }
    };
    // On the document: a button that disables while it works drops the focus to the body.
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);
  return html`
    <div class="scrim" onClick=${(/** @type {any} */ e) => e.target === e.currentTarget && close()}>
      <div class=${'dialog' + (wide ? ' wide' : '')} role="dialog" aria-modal="true"
        aria-labelledby="dialog-title" ref=${box}>
        <form onSubmit=${(/** @type {Event} */ e) => {
          e.preventDefault();
          onSubmit?.();
        }} class="dialog-form">
            <header><h2 id="dialog-title">${title}</h2>
              <button type="button" class="icon-btn dialog-x" aria-label="Close" onClick=${() =>
                close()}><${Icon} name="x" /></button></header>
            <div class="body">${children}</div>
            ${footer !== null
              ? html`<footer>${
                note ? html`<span class="note">${note}</span>` : null
              }${footer}</footer>`
              : null}
          </form>
      </div>
    </div>
  `;
}
