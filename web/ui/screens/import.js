// Importing a file into an account (requirements S1.3.2): OFX, QFX or CSV. A CSV from an
// institution seen for the first time asks for its columns, then remembers them.
import { useEffect, useState } from 'preact/hooks';
import { html } from '../app/html.js';
import { api } from '../api/client.js';
import { changes } from '../app/stream.js';
import { date } from '../app/format.js';
import { Dialog } from '../components/dialog.js';
import { useDialogGuide } from '../components/help.js';
import { errAt, Field, FormError, Input, Select } from '../components/fields.js';
import { Icon } from '../components/icon.js';
import { toast } from '../components/toast.js';

/**
 * Wait for a job to finish: the live stream says when, and a slow poll covers a lost event.
 * @param {string} id
 */
async function finished(id) {
  for (let i = 0; i < 600; i++) {
    const job = await api.get(`/jobs/${id}`);
    if (job.state === 'done' || job.state === 'failed') return job;
    await new Promise((r) => setTimeout(r, i < 10 ? 200 : 1000));
  }
  throw new Error('The import is taking too long; it carries on, and its result shows later.');
}

const COLUMNS = /** @type {[string, string, string][]} */ ([
  ['date', 'Date column', 'The posting or trade date.'],
  ['payee', 'Description column', 'The payee, merchant or description.'],
  ['amount', 'Amount column', 'One column with + for money in and − for money out.'],
  ['debit', 'Debit column', 'If money out has its own column.'],
  ['credit', 'Credit column', 'If money in has its own column.'],
  ['balance', 'Running balance column', 'Optional: every row then checks the balance.'],
  ['memo', 'Memo column', 'Optional.'],
  ['id', 'Transaction id column', "Optional: the institution's own id for each row."],
]);

/** @param {{ close: (v?: any) => void, accounts: any[], accountId?: string }} p */
export function ImportDialog({ close, accounts, accountId }) {
  useDialogGuide('dialog-import');
  const writable = accounts.filter((a) => a.level !== 'read');
  const [target, setTarget] = useState(accountId || writable[0]?.id || '');
  const [file, setFile] = useState(/** @type {File | null} */ (null));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(/** @type {any} */ (null));
  const [result, setResult] = useState(/** @type {any} */ (null));
  const [mapping, setMapping] = useState(/** @type {any} */ (null));

  const start = async () => {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const job = await finished((await api.upload(`/accounts/${target}/imports`, file)).id);
      if (job.state === 'failed') setError({ message: job.error.message });
      else if (job.result.needsMapping) setMapping(job.result);
      else setResult(job.result);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };
  const applyMapping = async () => {
    setBusy(true);
    setError(null);
    try {
      const job = await finished(
        (await api.post(`/imports/${mapping.uploadId}/mapping`, {
          mapping: mapping.mapping,
          save: true,
        })).id,
      );
      if (job.state === 'failed') setError({ message: job.error.message });
      else {
        setMapping(null);
        setResult(job.result);
      }
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    if (result) changes.value = { ...changes.value, import: (changes.value.import || 0) + 1 };
  }, [result]);

  if (result) {
    return html`<${Dialog} title="Imported" close=${close} footer=${html`
      <button type="button"
        class="btn primary" onClick=${() => {
          toast(`${result.added} new transactions`);
          close(result);
        }}>Done</button>
    `}>
      <div class="kv">
        <div><div class="k">New</div><div class="v">${result.added}</div></div>
        <div><div class="k">Already here</div><div class="v">${result.matched}</div></div>
        <div><div class="k">Changed since last time</div><div class="v">${result.changed}</div></div>
        <div><div class="k">Transfers matched</div><div class="v">${result.transfers}</div></div>
      </div>
      <p class="small dim">Covers ${date(result.coveredFrom)} to ${
      date(result.coveredTo)
    }. Importing the
        same file again adds nothing.</p>
      ${result.warnings.map((/** @type {string} */ w) => html`<div class="notice warn">${w}</div>`)}
    </${Dialog}>`;
  }

  if (mapping) {
    const headers = [['', '(none)'], ...mapping.headers.map((/** @type {string} */ h) => [h, h])];
    const m = mapping.mapping;
    const set = (/** @type {string} */ k) => (/** @type {string} */ v) =>
      setMapping({ ...mapping, mapping: { ...m, [k]: v || null } });
    return html`
      <${Dialog} title="Which columns are which?" wide close=${close}
        onSubmit=${applyMapping} note="Saved for the next file from this institution."
        footer=${html`<button class="btn primary" disabled=${busy}>Import</button>`}>
        <p class="small dim" style=${{
          marginTop: 0,
        }}>A CSV from this institution for the first time.
              Check the columns MoneyKata guessed.</p>
        <div class="split-form">
              ${COLUMNS.map(([k, label, hint]) =>
                html`
                  <${Field} label=${label} id=${'map-' + k} hint=${hint}
                    error=${errAt(error, 'mapping.' + k)}>
                    <${Select} value=${m[k] || ''} onChange=${set(k)}
                      options=${headers} />
                    </${Field}>
                `
              )}
              <${Field} label="Date format" id="map-date-format" hint="As the file writes its dates."
                error=${errAt(error, 'mapping.dateFormat')}><${Input} value=${m.dateFormat || ''}
                onInput=${set('dateFormat')} placeholder="%m/%d/%Y" /></${Field}>
              <${Field} label="Spending is positive" id="map-negate"
                hint="Card exports often show purchases as positive amounts."><${Select}
                value=${m.negateAmounts ? 'yes' : 'no'} onChange=${(/** @type {string} */ v) =>
                  setMapping({ ...mapping, mapping: { ...m, negateAmounts: v === 'yes' } })}
                options=${[['no', 'No'], ['yes', 'Yes: flip the signs']]} /></${Field}>
            </div>
            <div class="table-wrap"><table class="t"><caption class="sr-only">The file's first rows</caption>
              <thead><tr>${mapping.headers.map((/** @type {string} */ h) =>
                html`<th>${h}</th>`
              )}</tr></thead>
              <tbody>${mapping.sample.slice(0, 5).map((/** @type {string[]} */ r) =>
                html`<tr>${r.map((c) => html`<td class="small">${c}</td>`)}</tr>`
              )}</tbody></table></div>
            <${FormError} error=${error} shown=${COLUMNS.map(([k]) => 'mapping.' + k).concat([
              'mapping.dateFormat',
            ])} />
          </${Dialog}>
    `;
  }

  return html`
    <${Dialog} title="Import transactions" close=${close} onSubmit=${start}
      note="OFX, QFX or CSV. Re-importing a file adds only what's new."
      footer=${html`<button class="btn primary" disabled=${busy || !file || !target}>${
        busy ? 'Importing…' : 'Import'
      }</button>`}>
      <${Field} label="Into account" id="into-account">
        <${Select} value=${target} onChange=${setTarget}
          options=${writable.map((a) => [a.id, a.name])} />
        </${Field}>
        <${Field} label="File"
          hint="Downloaded from your bank or broker."><input class="in" type="file"
          accept=".ofx,.qfx,.csv,.txt" onChange=${(/** @type {any} */ e) =>
            setFile(e.currentTarget.files?.[0] || null)} /></${Field}>
        ${file
          ? html`<p class="small dim"><${Icon} name="upload" /> ${file.name} · ${
            Math.ceil(
              file.size / 1024,
            )
          } KB</p>`
          : null}
        <${FormError} error=${error} />
      </${Dialog}>
  `;
}
