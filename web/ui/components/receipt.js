// A receipt (requirements S9): its card in a grid, uploading files, and the dialog that shows
// one with its fields, what it is attached to, and the transactions it may belong to.
import { useEffect, useState } from 'preact/hooks';
import { html } from '../app/html.js';
import { api } from '../api/client.js';
import { useApi, useSubmit } from '../app/hooks.js';
import { date, money } from '../app/format.js';
import { Dialog } from './dialog.js';
import { useDialogGuide } from './help.js';
import { errAt, Field, FormError, Input, SwitchRow } from './fields.js';
import { Icon } from './icon.js';
import { toast } from './toast.js';

export const ACCEPT = 'application/pdf,image/jpeg,image/png,image/webp,image/heic,.heic';
const KIND = /** @type {Record<string, string>} */ ({
  'application/pdf': 'PDF',
  'image/jpeg': 'JPG',
  'image/png': 'PNG',
  'image/webp': 'WebP',
  'image/heic': 'HEIC',
});

/**
 * Uploads files one request each, so a batch works through them; returns what was made.
 * @param {FileList | File[]} list
 */
export async function uploadAll(list) {
  const made = [];
  for (const f of [...list]) {
    try {
      made.push(await api.upload('/receipts', f));
    } catch (e) {
      toast(`${f.name}: ${/** @type {any} */ (e).message}`);
    }
  }
  if (made.length) toast(`Uploaded ${made.length} receipt${made.length === 1 ? '' : 's'}`);
  return made;
}

/**
 * A picture from the API, fetched with the session and shown from memory: thumbnails and
 * photos load the way every other answer does.
 * @param {{ src: string, alt: string, class?: string }} p
 */
export function ApiImg({ src, alt, class: cls }) {
  const [url, setUrl] = useState('');
  useEffect(() => {
    let made = '';
    let live = true;
    fetch(src, { credentials: 'same-origin' }).then((r) => (r.ok ? r.blob() : null)).then((b) => {
      if (live && b) setUrl(made = URL.createObjectURL(b));
    }, () => {});
    return () => {
      live = false;
      if (made) URL.revokeObjectURL(made);
    };
  }, [src]);
  return url ? html`<img src=${url} alt=${alt} class=${cls} />` : null;
}

/** @param {{ r: any, onOpen: () => void }} p */
export function ReceiptCard({ r, onOpen }) {
  return html`
    <button type="button" class="receipt" onClick=${onOpen} aria-label=${'Receipt ' +
      (r.payee || r.fileName)}>
      <div class="thumb"><span class="pill kind">${KIND[r.mediaType] || ''}</span>
        ${r.hasThumbnail
          ? html`<${ApiImg} src=${`/ui/api/receipts/${r.id}/thumbnail`} alt="" />`
          : html`<div class="paper"><i></i><i style=${{ width: '70%' }}></i><i></i><i style=${{
            width: '50%',
          }}></i></div>`}</div>
      <div class="meta">
        <div class="ellipsis" style=${{ fontWeight: 550 }}>${r.payee ||
          r.fileName}</div>
        <div class="dim">${r.date ? date(r.date) : date(r.uploadedAt)}${r.amount
          ? html`
            ${'\u00a0· '}<span class="amt">${money(r.amount)}</span>
          `
          : ''}</div>
        <div style=${{
          marginTop: '4px',
        }}>${r.readStatus === 'waiting' || r.readStatus === 'reading'
          ? html`<span class="pill info">Reading…</span>`
          : r.readStatus === 'failed'
          ? html`<span class="pill bad">couldn't read it</span>`
          : r.links.length
          ? html`<span class="pill ok">${r.links[0].accountName}${
            r.links.length > 1 ? ` +${r.links.length - 1}` : ''
          }</span>`
          : html`<span class="pill warn">inbox</span>`}</div>
      </div>
    </button>
  `;
}

/**
 * One receipt: the picture or PDF, its fields, and what it is attached to.
 * @param {{ close: (v?: any) => void, id: string }} p
 */
export function ReceiptDialog({ close, id }) {
  useDialogGuide('dialog-receipt');
  const res = useApi(`/receipts/${id}`, {}, ['receipt']);
  const r = /** @type {any} */ (res.data);
  const [f, setF] = useState(/** @type {any} */ (null));
  useEffect(() => {
    if (r) {
      setF({
        date: r.date || '',
        amount: r.amount || '',
        payee: r.payee || '',
        notes: r.notes || '',
        tags: r.tags.join(', '),
      });
    }
  }, [r?.version]);
  const save = useSubmit(async () => {
    await api.patch(`/receipts/${id}`, {
      date: f.date || null,
      amount: f.amount ? String(f.amount).trim() : null,
      payee: f.payee || null,
      notes: f.notes || null,
      tags: f.tags.split(',').map((/** @type {string} */ t) => t.trim()).filter(Boolean),
    }, r.version);
    toast('Saved');
    close(true);
  });
  const attach = useSubmit(async (/** @type {string} */ tid) => {
    await api.post(`/receipts/${id}/links`, { transactionId: tid });
    toast('Attached');
    res.reload();
  });
  const detach = useSubmit(async (/** @type {string} */ tid) => {
    await api.del(`/receipts/${id}/links/${tid}`);
    toast('Detached');
    res.reload();
  });
  const again = useSubmit(async () => {
    await api.post(`/receipts/${id}/read`);
    toast('Queued to read again');
    res.reload();
  });
  const remove = useSubmit(async () => {
    await api.del(`/receipts/${id}`, r.version);
    toast('Receipt deleted');
    close(true);
  });
  // The dialog opens once the receipt has come, so its first field takes the focus.
  if (!r || !f) return null;
  const canEdit = r.level === 'owner' || r.level === 'write';
  const reading = r.readStatus === 'waiting' || r.readStatus === 'reading';
  /** "Read from the receipt" under a field still holding what was read from it. */
  const hint = (/** @type {string} */ field, /** @type {string} */ key) =>
    r.filled.includes(field) && r.suggested[key]
      ? `Read from the receipt · ${r.suggested[key].confidence}% sure`
      : undefined;
  const set = (/** @type {string} */ k) => (/** @type {string} */ v) => setF({ ...f, [k]: v });
  const file = `/ui/api/receipts/${id}/file`;
  const keep = useSubmit(async (/** @type {boolean} */ on) => {
    await api.patch(`/receipts/${id}`, { keep: on }, r.version);
    res.reload();
  });
  return html`
    <${Dialog} title=${r.fileName} wide close=${close}
      onSubmit=${() => save.run().catch(() => {})}
      footer=${html`${
        r.level === 'owner'
          ? html`
            <button type="button" class="btn danger" style=${{ marginRight: 'auto' }}
              disabled=${remove.busy || r.links.length > 0}
              title=${r.links.length ? 'Detach it first' : undefined}
              onClick=${() => remove.run().catch((e) => toast(e.message))}>Delete</button>
          `
          : null
      }${canEdit ? html`<button class="btn primary" disabled=${save.busy}>Save</button>` : null}`}>
      <div class="split" style=${{ alignItems: 'flex-start' }}>
        <div class="receipt-view">
          ${r.filePrunedAt
            ? html`
              <div class="notice" role="note">
                <${Icon} name="info" />
                <div>${r.kept}: its
                            record keeps its amounts, dates and links.</div>
              </div>
            `
            : r.mediaType === 'application/pdf'
            ? html`<a href=${file} target="_blank" rel="noopener" class="pdf-open">
              ${
              r.hasThumbnail
                ? html`
                  <${ApiImg} src=${`/ui/api/receipts/${id}/thumbnail`}
                    alt="The PDF's first page" />
                `
                : null
            }
              <span class="btn sm"><${Icon} name="download" /> Open the PDF</span></a>`
            : html`<a href=${file} target="_blank" rel="noopener" title="Open full size"><${ApiImg}
              src=${file} alt=${'Receipt ' + r.fileName} /></a>`}
          ${r.text
            ? html`
              <details class="mt">
                <summary class="small">Text read from the receipt (searchable)</summary>
                <div class="ocr-text mt">${r.text}</div>
              </details>
            `
            : null}
          <div class="toolbar mt" style=${{
            margin: '8px 0 0',
          }}><span class="small dim">${r.readMethod ===
              'text'
            ? "Read from the PDF's text layer"
            : r.readMethod === 'ocr'
            ? 'Read with OCR'
            : ''}${r.suggested.card ? ` · card ending ${r.suggested.card.value}` : ''}</span>
            <span class="spacer"></span>${canEdit && !reading
              ? html`
                <button type="button" class="btn sm" disabled=${again.busy}
                  onClick=${() =>
                    again.run().catch((e) =>
                      toast(e.message)
                    )}><${Icon} name="refresh" /> Read again</button>
              `
              : null}</div>
          ${r.filePrunedAt ? null : html`
            <${SwitchRow} label="Keep" hint=${r.keep
              ? 'Kept for ever, whatever its retention.'
              : html`${r.keptSoon ? html`<b>${r.kept}</b>` : r.kept}${
                r.keptWhy ? ` · ${r.keptWhy}` : ''
              }`} on=${r.keep} disabled=${!canEdit || keep.busy}
              onChange=${(/** @type {boolean} */ on) => keep.run(on).catch((e) => toast(e.message))}
            />
          `}
          <p class="small dim">${KIND[r.mediaType]} · ${(r.size / 1024).toFixed(
            0,
          )} KB · uploaded ${date(r.uploadedAt)}${r.level !== 'owner'
            ? ` by ${r.ownerName}`
            : ''}</p>
        </div>
        <div style=${{ flex: '0 1 280px' }}>
          ${reading
            ? html`
              <div class="notice" role="status">
                <${Icon} name="refresh" />
                <div>Reading this receipt on
                            the server. The fields fill in when it's done; you can type them now.</div>
              </div>
            `
            : r.readStatus === 'failed'
            ? html`
              <div class="notice bad" role="status">
                <${Icon} name="alert" />
                <div>Couldn't read it: ${r
                  .readError}. Type the fields by hand.</div>
              </div>
            `
            : null}
          <div class="row">
            <${Field} label="Date" id="receipt-date" error=${errAt(save.error, 'date')}
              hint=${hint('date', 'date')}>
              <${Input} type="date" value=${f.date} onInput=${set('date')} disabled=${!canEdit} />
              </${Field}>
              <${Field} label="Amount" id="receipt-amount" error=${errAt(save.error, 'amount')}
              hint=${hint('amount', 'total')}>
                <${Input} value=${f.amount} onInput=${set('amount')} inputmode="decimal"
                  disabled=${!canEdit} />
                </${Field}>
                </div>
                <${Field} label="Payee" id="receipt-payee" error=${errAt(save.error, 'payee')}
            hint=${hint('payee', 'merchant')}>
                  <${Input} value=${f.payee} onInput=${set('payee')} disabled=${!canEdit} />
                  </${Field}>
                  <${Field} label="Notes" id="receipt-notes" error=${errAt(save.error, 'notes')}>
                    <${Input} value=${f.notes} onInput=${set('notes')} disabled=${!canEdit} />
                    </${Field}>
                    <${Field} label="Tags" id="receipt-tags" hint="Separated by commas.">
            <${Input} value=${f.tags} onInput=${set('tags')} disabled=${!canEdit} />
          </${Field}>
          <h4 class="small dim" data-help="attached-to" id="x-attached-to">Attached to</h4>
          ${r.links.length
            ? r.links.map((/** @type {any} */ l) =>
              l.transactionId
                ? html`<div class="list-item"><div class="grow small">${
                  l.payee || 'Transaction'
                } · <span
                    class="amt">${money(l.amount)}</span><div class="dim">${l.accountName} · ${
                  date(l.date)
                }</div></div>${
                  canEdit
                    ? html`<button type="button" class="btn sm" onClick=${() =>
                      detach.run(l.transactionId).catch((e) => toast(e.message))}>Detach</button>`
                    : null
                }</div>`
                : html`
                  <div class="list-item">
                    <div class="grow small">The statement of ${l.accountName}</div>
                  </div>
                `
            )
            : html`<p class="small dim">Nothing yet: it waits in the inbox.</p>`}
          ${r.matches.length
            ? html`
              <div class="notice mt">
                <${Icon} name="clip" />
                <div><b>Attach to</b> ${r.matches[0].payee || 'a transaction'} · ${money(
                  r.matches[0].amount,
                )} · ${date(r.matches[0].date)} · ${r.matches[0].accountName}?
                            <div class="toolbar" style=${{ margin: '8px 0 0' }}>${r.matches.map((
                              /** @type {any} */ m,
                              /** @type {number} */ i,
                            ) =>
                              html`
                                <button type="button" class=${'btn sm' + (i ? '' : ' primary')}
                                  disabled=${attach.busy} onClick=${() =>
                                    attach.run(m.transactionId).catch((e) => toast(e.message))}>${i
                                    ? `${m.payee || 'Transaction'} · ${date(m.date)}`
                                    : 'Attach'}</button>
                              `
                            )}</div></div>
              </div>
            `
            : !r.links.length
            ? html`<p class="small dim">${
              r.amount
                ? 'No transaction of this amount within five days of its date yet. Attach it from the transaction when it arrives.'
                : 'Give it a date and amount to find the transaction it belongs to, or attach it from the transaction itself.'
            }</p>`
            : null}
          <${FormError} error=${save.error || attach.error || detach.error} shown=${[
            'date',
            'amount',
            'payee',
            'notes',
          ]} />
        </div>
      </div>
    </${Dialog}>
  `;
}
