// Importing a file into an account (requirements S1.3.2–S1.3.3): OFX, QFX or CSV, or a
// statement (a PDF or a photo of one) read on the server and checked before it is saved. A CSV
// from an institution seen for the first time asks for its columns, then remembers them.
import { useEffect, useState } from 'preact/hooks';
import { html } from '../app/html.js';
import { api } from '../api/client.js';
import { changes } from '../app/stream.js';
import { cents, date, fromCents, money } from '../app/format.js';
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
  const [review, setReview] = useState(/** @type {any} */ (null));

  const start = async () => {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const job = await finished((await api.upload(`/accounts/${target}/imports`, file)).id);
      if (job.state === 'failed') setError({ message: job.error.message });
      else if (job.result.needsMapping) setMapping(job.result);
      else if (job.result.needsReview) {
        setReview({
          ...job.result,
          rows: job.result.rows.map((/** @type {any} */ r) => ({ ...r, include: !r.present })),
          accept: false,
        });
      } else setResult(job.result);
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

  if (review) {
    return html`
      <${StatementReview} review=${review} setReview=${setReview} close=${close}
        done=${(/** @type {any} */ r) => {
          setReview(null);
          setResult(r);
        }} />
    `;
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
      note="OFX, QFX or CSV, or a statement (PDF or photo). Re-importing adds only what's new."
      footer=${html`<button class="btn primary" disabled=${busy || !file || !target}>${
        busy ? 'Importing…' : 'Import'
      }</button>`}>
      <${Field} label="Into account" id="into-account">
        <${Select} value=${target} onChange=${setTarget}
          options=${writable.map((a) => [a.id, a.name])} />
        </${Field}>
        <${Field} label="File"
          hint="Downloaded from your bank or broker, or a statement: its PDF, or a photo."><input class="in" type="file"
          accept=".ofx,.qfx,.csv,.txt,.pdf,.jpg,.jpeg,.png,.webp,.heic" onChange=${(
            /** @type {any} */ e,
          ) => setFile(e.currentTarget.files?.[0] || null)} /></${Field}>
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

/**
 * A statement read on the server, to check before anything is saved: its period and balances,
 * and each transaction, which can be corrected or left out. It is saved only when the
 * transactions add up from the opening to the closing balance, or the difference is accepted.
 * @param {{ review: any, setReview: (v: any) => void, close: (v?: any) => void,
 *   done: (r: any) => void }} p
 */
function StatementReview({ review, setReview, close, done }) {
  useDialogGuide('dialog-statement');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(/** @type {any} */ (null));
  const kept = review.rows.filter((/** @type {any} */ r) => r.include);
  const sum = kept.reduce(
    (/** @type {bigint} */ a, /** @type {any} */ r) => a + (cents(r.amount) ?? 0n),
    0n,
  );
  const diff = (cents(review.closing) ?? 0n) - (cents(review.opening) ?? 0n) - sum;
  const set = (/** @type {string} */ k) => (/** @type {string} */ v) =>
    setReview({ ...review, [k]: v });
  const setRow = (/** @type {number} */ i, /** @type {string} */ k, /** @type {any} */ v) =>
    setReview({
      ...review,
      rows: review.rows.map((/** @type {any} */ r, /** @type {number} */ j) =>
        i === j ? { ...r, [k]: v } : r
      ),
    });
  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      const job = await api.post(`/imports/${review.uploadId}/statement`, {
        periodStart: review.periodStart,
        periodEnd: review.periodEnd,
        opening: review.opening,
        closing: review.closing,
        acceptDifference: review.accept,
        rows: review.rows.map((/** @type {any} */ r) => ({
          date: r.date,
          description: r.description,
          amount: r.amount,
          include: r.include,
        })),
      });
      done(job.result);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };
  const fresh = kept.filter((/** @type {any} */ r) => !r.present).length;
  return html`
    <${Dialog} title="Check the statement" wide close=${close} onSubmit=${save}
      note=${review.learned
        ? `Read with what was learned of ${review.institution || 'this institution'}'s statements.`
        : 'What you correct here is remembered for the next statement from this institution.'}
      footer=${html`<button class="btn primary" disabled=${
        busy || (diff !== 0n && !review.accept)
      }>${busy ? 'Saving…' : `Import ${fresh} new`}</button>`}>
      <p class="small dim" style=${{ marginTop: 0 }}>${review.fileName} · ${review.method === 'text'
        ? 'read from its text layer'
        : 'read with OCR'}${review.institution ? ` · ${review.institution}` : ''}</p>
      <div class="row">
        <${Field} label="Period from" id="period-start" error=${errAt(error, 'periodStart')}>
          <${Input} type="date" value=${review.periodStart || ''} onInput=${set(
            'periodStart',
          )} required />
          </${Field}>
          <${Field} label="Period to" id="period-end" error=${errAt(error, 'periodEnd')}>
            <${Input} type="date" value=${review.periodEnd || ''} onInput=${set(
              'periodEnd',
            )} required />
            </${Field}>
            <${Field} label="Opening balance" id="opening">
              <${Input} value=${review.opening || ''} onInput=${set(
                'opening',
              )} inputmode="decimal" required />
              </${Field}>
              <${Field} label="Closing balance" id="closing">
          <${Input} value=${review.closing || ''} onInput=${set(
            'closing',
          )} inputmode="decimal" required />
        </${Field}>
      </div>
      <div class="kv">
        <div><div class="k">${kept.length} transactions</div><div class="v amt">${money(
          fromCents(sum),
        )}</div></div>
        <div><div class="k">Adds up</div><div class="v" style=${{
          color: diff === 0n ? 'var(--ok)' : 'var(--deny)',
        }}>${diff === 0n
          ? html`<${Icon} name="check" /> yes`
          : `${money(fromCents(diff))} short`}</div></div>
      </div>
      <div class="table-wrap mt"><table class="t">
        <thead><tr><th></th><th>Date</th><th>Description</th><th class="num">Amount</th><th></th></tr></thead>
        <tbody>${review.rows.map((/** @type {any} */ r, /** @type {number} */ i) =>
          html`
            <tr class=${r.include ? '' : 'dim'}>
              <td><input type="checkbox" checked=${r.include} aria-label=${'Import ' +
                r.description}
                          data-help="include" onChange=${() =>
                            setRow(i, 'include', !r.include)} /></td>
              <td class="dim">${date(r.date)}</td>
              <td><input class="in" value=${r
                .description} aria-label="Description" data-help="description"
                          onInput=${(/** @type {any} */ e) =>
                            setRow(i, 'description', e.currentTarget.value)} />${r.confidence < 80
                            ? html`<div class="small ocr"><${Icon} name="info" /> its sign was guessed · check it</div>`
                            : null}</td>
              <td class="num"><input class="in num" value=${r.amount} aria-label="Amount"
                          data-help="amount" style=${{ maxWidth: '120px' }}
                          onInput=${(/** @type {any} */ e) =>
                            setRow(i, 'amount', e.currentTarget.value)} /></td>
              <td>${r.present
                ? html`<span class="pill">already here</span>`
                : html`<span class="pill info">new</span>`}</td>
            </tr>
          `
        )}</tbody>
      </table></div>
      ${diff !== 0n
        ? html`<label class="list-item" style=${{ cursor: 'pointer' }}><input type="checkbox"
            id="f-accept-difference" checked=${review.accept}
            onChange=${() =>
          setReview({ ...review, accept: !review.accept })} /><span class="grow">Import
            anyway: the Reconcile tab will show the ${
          money(fromCents(diff))
        } it is short</span></label>`
        : null}
      <${FormError} error=${error} shown=${['periodStart', 'periodEnd']} />
    </${Dialog}>
  `;
}
