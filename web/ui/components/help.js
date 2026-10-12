// The help pane (requirements §15.7): F1 toggles it; it shows the guide of the screen, tab or
// dialog in view, and follows the focus to the field's heading. Its width drags (up to half the
// window) and moves with the arrow keys; the browser remembers both.
import { signal } from '@preact/signals';
import { useEffect, useRef, useState } from 'preact/hooks';
import { html } from '../app/html.js';
import { guides } from '../app/config.js';
import { helpOpen, helpWidth } from '../store/prefs.js';
import { assemble, render } from './markdown.js';
import { Icon } from './icon.js';

/** The guide of the screen in view: its key, and values its parts need (the account type). */
export const screenGuide = signal(
  /** @type {{ key: string, vars?: Record<string, string> }} */ ({
    key: 'dashboard',
  }),
);
/** A dialog's guide, while it is open. */
export const dialogGuide = signal(/** @type {string | null} */ (null));

/**
 * @param {string} key
 * @param {Record<string, string>} [vars]
 */
export function useGuide(key, vars) {
  const v = JSON.stringify(vars || {});
  useEffect(() => {
    screenGuide.value = { key, vars };
  }, [key, v]);
}

/** @param {string} key */
export function useDialogGuide(key) {
  useEffect(() => {
    dialogGuide.value = key;
    return () => {
      dialogGuide.value = null;
    };
  }, [key]);
}

const cache = new Map();
/** @param {string} name */
function load(name) {
  if (!cache.has(name)) {
    cache.set(
      name,
      fetch(`${guides}/${name}.md`).then((r) => {
        if (!r.ok) throw new Error(`no guide ${name}`);
        return r.text();
      }),
    );
  }
  return cache.get(name);
}

export function HelpPane() {
  const ref = useRef(/** @type {HTMLElement | null} */ (null));
  const [md, setMd] = useState(/** @type {string | null} */ (null));
  const key = dialogGuide.value || screenGuide.value.key;
  const vars = dialogGuide.value ? {} : screenGuide.value.vars || {};

  useEffect(() => {
    let live = true;
    load(key).then((text) => assemble(text, load, vars)).then(
      (text) => live && setMd(text),
      () => live && setMd(`# ${key}\n\nThis screen's guide is missing.`),
    );
    return () => {
      live = false;
    };
  }, [key, JSON.stringify(vars)]);

  useEffect(() => {
    const follow = (/** @type {FocusEvent} */ e) => {
      const el = /** @type {HTMLElement} */ (e.target);
      const id = el?.id?.startsWith('f-') ? el.id.slice(2) : el?.closest?.('[data-help]')
        ?.getAttribute('data-help');
      if (!id || !ref.current) return;
      const target = ref.current.querySelector(`[data-anchor="${id}"]`);
      if (!target) return;
      const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
      target.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
      target.classList.add('flash');
      setTimeout(() => target.classList.remove('flash'), 1200);
    };
    document.addEventListener('focusin', follow);
    return () => document.removeEventListener('focusin', follow);
  }, []);

  const drag = (/** @type {PointerEvent} */ e) => {
    e.preventDefault();
    const move = (/** @type {PointerEvent} */ m) => {
      helpWidth.value = Math.max(260, Math.min(innerWidth / 2, innerWidth - m.clientX));
    };
    const up = () => {
      removeEventListener('pointermove', move);
      removeEventListener('pointerup', up);
    };
    addEventListener('pointermove', move);
    addEventListener('pointerup', up);
  };
  const keys = (/** @type {KeyboardEvent} */ e) => {
    if (e.key === 'ArrowLeft') helpWidth.value = Math.min(innerWidth / 2, helpWidth.value + 20);
    if (e.key === 'ArrowRight') helpWidth.value = Math.max(260, helpWidth.value - 20);
  };

  return html`
    <aside class="help" aria-label="Help" ref=${ref} style=${{ width: helpWidth.value + 'px' }}>
      <div class="resizer" role="separator" aria-orientation="vertical" aria-label="Resize help"
        tabindex="0" onPointerDown=${drag} onKeyDown=${keys}></div>
      <button type="button" class="icon-btn help-close" aria-label="Close help (F1)"
        onClick=${() => (helpOpen.value = false)}><${Icon} name="x" /></button>
      <div class="guide" data-guide=${key}>${md === null
        ? null
        : render(md, (src) => /^https?:|^\//.test(src) ? src : `${guides}/${src}`)}</div>
    </aside>
  `;
}

export function HelpCorner() {
  return html`
    <button type="button" class="help-corner" aria-label="Show help (F1)"
      data-tip="Show help (F1)" onClick=${() => (helpOpen.value = true)}><span></span></button>
  `;
}
