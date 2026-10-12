// Form fields: a label, the control, a hint and the server's refusal at that field (§3.7).
// Each control's id is "f-" and its label's slug, which the help pane follows (§15.7.3).
import { cloneElement, isValidElement } from 'preact';
import { html } from '../app/html.js';
import { slug } from '../app/format.js';

/**
 * @param {{ label: string, id?: string, hint?: any, error?: string | null, help?: string,
 *   children: any }} p
 */
export function Field({ label, id, hint, error, help, children }) {
  // A control that repeats (a split's parts) keeps a unique id and names its heading with
  // data-help instead (§15.7.3).
  const fid = (help ? 'x-' : 'f-') + (id || slug(label));
  const kids = Array.isArray(children) ? children : [children];
  const control = kids.map((c) =>
    isValidElement(c) && !(/** @type {any} */ (c).props.id)
      ? cloneElement(/** @type {any} */ (c), {
        id: fid,
        'data-help': help,
        'aria-invalid': error ? 'true' : undefined,
        'aria-describedby': error ? fid + '-err' : undefined,
      })
      : c
  );
  return html`<div class="field">
    <label for=${fid}>${label}</label>
    ${control}
    ${hint ? html`<div class="hint">${hint}</div>` : null}
    ${error ? html`<div class="err" id=${fid + '-err'} role="alert">${error}</div>` : null}
  </div>`;
}

/**
 * A text input bound to a value.
 * @param {{ value: any, onInput: (v: string) => void, type?: string, placeholder?: string,
 *   bad?: boolean, autocomplete?: string, id?: string, inputmode?: string, required?: boolean }} p
 */
export function Input({ value, onInput, type = 'text', placeholder, bad, ...rest }) {
  return html`
    <input class=${'in' + (bad ? ' bad' : '')} type=${type} value=${value ?? ''}
      placeholder=${placeholder} onInput=${(/** @type {any} */ e) => onInput(e.currentTarget.value)}
      ...${rest} />
  `;
}

/**
 * @param {{ value: any, onChange: (v: string) => void, options: ([string, string] | string)[],
 *   id?: string }} p
 */
export function Select({ value, onChange, options, ...rest }) {
  return html`
    <select class="in" value=${value ?? ''}
      onChange=${(/** @type {any} */ e) => onChange(e.currentTarget.value)} ...${rest}>
        ${options.map((o) => {
          const [v, l] = Array.isArray(o) ? o : [o, o];
          return html`<option value=${v}>${l}</option>`;
        })}
      </select>
  `;
}

/**
 * A switch: a button with role=switch.
 * One switch per row of a table names its heading with help, keeping a unique id.
 * @param {{ on: boolean, onChange: (v: boolean) => void, label: string, id?: string,
 *   disabled?: boolean, help?: string }} p
 */
export function Switch({ on, onChange, label, id, disabled, help }) {
  return html`
    <button type="button" class=${'switch' + (on ? ' on' : '')} role="switch"
      aria-checked=${on ? 'true' : 'false'} aria-label=${label} id=${(help ? 'x-' : 'f-') +
        (id || slug(label))} data-help=${help}
      disabled=${disabled} onClick=${() => onChange(!on)}></button>
  `;
}

/**
 * A row with a label and a switch, as Settings and account forms use.
 * @param {{ label: string, hint?: string, on: boolean, onChange: (v: boolean) => void,
 *   disabled?: boolean }} p
 */
export function SwitchRow({ label, hint, on, onChange, disabled }) {
  return html`
    <div
      class="list-item"><span class="grow">${label}${hint
        ? html`<div class="small dim">${hint}</div>`
        : null}</span><${Switch} on=${on} onChange=${onChange} label=${label} disabled=${disabled} /></div>
  `;
}

/**
 * A segmented choice, such as None · Read · Write.
 * @param {{ value: string, onChange: (v: string) => void, options: [string, string][],
 *   label: string, disabled?: string[] }} p
 */
export function Seg({ value, onChange, options, label, disabled = [] }) {
  return html`<div class="seg" role="radiogroup" aria-label=${label}>${
    options.map(([v, l]) =>
      html`
        <button type="button" role="radio" aria-checked=${value === v ? 'true' : 'false'}
          class=${value === v ? 'on' : ''} disabled=${disabled.includes(v)}
          onClick=${() => onChange(v)}>${l}</button>
      `
    )
  }</div>`;
}

/**
 * The server's refusal of the form as a whole, or of fields this form doesn't show.
 * @param {{ error: any, shown?: string[] }} p
 */
export function FormError({ error, shown = [] }) {
  if (!error) return null;
  const errs = (error.errors || []).filter((/** @type {any} */ e) => !shown.includes(e.field));
  const text = errs.length
    ? errs.map((/** @type {any} */ e) => e.message).join(' ')
    : error.message;
  if (error.errors?.length && !errs.length) return null;
  return html`<div class="notice bad" role="alert">${text}${
    error.errorId
      ? html`
        <span class="small dim">(${error.errorId})</span>
      `
      : null
  }</div>`;
}

/**
 * The message for a field from an ApiError, if any.
 * @param {any} error
 * @param {string} field
 */
export function errAt(error, field) {
  return error?.errors?.find((/** @type {any} */ e) => e.field === field)?.message ?? null;
}
