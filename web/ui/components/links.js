// Settings › Linked servers (requirements S11.1, S11.7): invite a server or enter its code,
// approve a request after comparing fingerprints, pause, resume, pull now or end a link, and
// each linked server's users.
import { useEffect, useState } from 'preact/hooks';
import { html } from '../app/html.js';
import { api } from '../api/client.js';
import { useApi, useSubmit } from '../app/hooks.js';
import { ago, date } from '../app/format.js';
import { Dialog, openDialog } from './dialog.js';
import { useDialogGuide } from './help.js';
import { errAt, Field, FormError, Input, Select } from './fields.js';
import { Failed, Loading } from './bits.js';
import { Icon } from './icon.js';
import { toast } from './toast.js';

const STATE = /** @type {Record<string, [string, string]>} */ ({
  invited: ['invitation', ''],
  requested: ['wants to link', 'info'],
  pending: ['waiting for approval', ''],
  active: ['active', 'ok'],
  paused: ['paused', 'warn'],
  ended: ['ended', ''],
});

export function LinksSection() {
  const res = useApi('/settings/links', {}, ['task']);
  const s = useApi('/settings');
  const v = /** @type {any} */ (res.data);
  const values = /** @type {any} */ (s.data)?.values;
  const [address, setAddress] = useState('');
  useEffect(() => {
    if (values) setAddress(values.linkAddress || '');
  }, [values]);
  const saveAddress = useSubmit(async () => {
    await api.patch('/settings', { linkAddress: address || null });
    toast('Saved');
    res.reload();
    s.reload();
  });
  const act = useSubmit(async (/** @type {string} */ id, /** @type {string} */ what) => {
    const out = await api.post(`/settings/links/${id}/${what}`);
    toast(
      what === 'pull'
        ? out.lastError ? `Not reached: ${out.lastError}` : 'Exchanged now'
        : `Link ${out.state === 'ended' ? 'ended' : out.state}`,
    );
    res.reload();
  });
  const [armed, setArmed] = useState(/** @type {string | null} */ (null));
  const copyAct = useSubmit(async (/** @type {string} */ id, /** @type {string} */ what) => {
    const out = await api.post(`/settings/links/${id}/${what}`);
    toast(what === 'lock' ? 'Locked' : 'Copy reset: make its new access key');
    res.reload();
    return out;
  });
  const release = useSubmit(async (/** @type {string} */ v) => {
    await api.patch('/settings', { linkReleaseMinutes: Number(v) });
    toast('Saved');
    s.reload();
  });
  if (res.error) return html`<${Failed} error=${res.error} />`;
  if (!v || !values) return html`<${Loading} />`;
  const live = v.links.filter((/** @type {any} */ l) => l.state !== 'ended');
  const ended = v.links.filter((/** @type {any} */ l) => l.state === 'ended');
  const people = live.filter((/** @type {any} */ l) => l.users.length);
  return html`
    <div class="card">
      <h3 style=${{ flexWrap: 'wrap' }}>Linked servers<span class="spacer"></span><button
        class="btn" onClick=${() =>
          openDialog(JoinLink, {}).then((x) => x && res.reload())}>Enter a link code</button>
        <button class="btn primary" onClick=${() =>
          openDialog(InviteLink, {}).then(() => res.reload())}><${Icon} name="plus" /> Invite a
          server</button></h3>
      <div class="notice" style=${{ marginBottom: '12px' }}>
        <${Icon} name="info" />
        <div>A link
        carries <b>read-only</b> shares between two MoneyKata servers. This server's key
        fingerprint: <code>${v.fingerprint}</code></div>
      </div>
      <form onSubmit=${(/** @type {Event} */ ev) => {
        ev.preventDefault();
        saveAddress.run().catch(() => {});
      }}>
        <${Field} label="This server's link address" id="link-address" error=${errAt(
          saveAddress.error,
          'linkAddress',
        )}
          hint=${`Where other servers reach this one's /link. Empty: the public URL${
            values.publicUrl ? ` (${values.publicUrl})` : ', which is not set'
          }.`}>
          <${Input} value=${address} onInput=${setAddress}
            placeholder="https://money.griffin.ts.net" />
        </${Field}>
        <div class="toolbar" style=${{ marginBottom: '12px' }}><button class="btn sm"
          disabled=${saveAddress.busy}>Save</button></div>
      </form>
      ${live.length
        ? html`
          <div class="table-wrap">
            <table class="t">
              <caption class="sr-only">Linked servers</caption>
              <thead>
                <tr>
                  <th>Server</th>
                  <th>State</th>
                  <th>Last exchange</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>${live.map((/** @type {any} */ l) =>
                html`
                  <tr>
                    <td>
                      <div class="acct-row">
                        <div class=${'tile ' +
                          (l.state === 'active' ? 't-linked' : 't-other')}>
                          <${Icon} name="server" />
                        </div>
                        <div><b>${l.peerName || l.householdName ||
                          'Invitation'}</b>${l.householdName &&
                            l.peerName
                          ? html`
                            <div class="small">${l.householdName}</div>
                          `
                          : null}<div class="small dim">${l.address || ''}${l.fingerprint
                          ? html`
                            · <code>${l.fingerprint}</code>
                          `
                          : ''}${l.peerVersion ? ` · MoneyKata ${l.peerVersion}` : ''}</div></div>
                      </div>
                    </td>
                    <td><span class=${'pill ' + (l.failingSince ? 'warn' : STATE[l.state][1])}>${l
                        .failingSince
                      ? `unreachable since ${date(l.failingSince)}`
                      : STATE[l.state][0]}</span>${l.lastError
                      ? html`<div class="small dim">${l.lastError}</div>`
                      : null}</td>
                    <td class="small dim">${l.state === 'invited'
                      ? `code valid until ${date(l.codeExpiresAt)}`
                      : l.state === 'requested'
                      ? 'Compare the fingerprint with them before approving.'
                      : ago(l.lastOkAt)}</td>
                    <td class="num">
                      <div style=${{
                        display: 'flex',
                        flexWrap: 'wrap',
                        gap: '4px',
                        justifyContent: 'flex-end',
                      }}>${l.state === 'requested'
                        ? html`
                          <button class="btn sm" onClick=${() =>
                            act.run(l.id, 'end')}>Reject</button> <button class="btn sm primary"
                            onClick=${() => act.run(l.id, 'approve')}>Approve</button>
                        `
                        : html`${
                          ['active', 'pending'].includes(l.state)
                            ? html`
                              <button class="btn sm" disabled=${act.busy} onClick=${() =>
                                act.run(l.id, 'pull')}>Pull now</button>
                            `
                            : null
                        }${
                          l.state === 'active'
                            ? html`
                              <button class="btn sm" onClick=${() =>
                                act.run(l.id, 'pause')}>Pause</button>
                            `
                            : l.state === 'paused'
                            ? html`
                              <button class="btn sm" onClick=${() =>
                                act.run(l.id, 'resume')}>Resume</button>
                            `
                            : null
                        }<button class="btn sm danger" onClick=${() =>
                          armed === l.id
                            ? act.run(l.id, 'end').then(() => setArmed(null))
                            : setArmed(
                              l.id,
                            )}>${
                          armed === l.id
                            ? 'Click again to end'
                            : l.state === 'invited'
                            ? 'Withdraw'
                            : 'End link'
                        }</button>`}</div>
                    </td>
                  </tr>
                `
              )}</tbody>
            </table>
          </div>
        `
        : html`<p class="small dim">No links yet.</p>`}
      ${ended.length
        ? html`<p class="small dim">Ended: ${
          ended.map((/** @type {any} */ l) =>
            `${l.peerName || 'an invitation'} (${date(l.endedAt)})`
          ).join(', ')
        }.</p>`
        : null}
      <${FormError} error=${act.error} />
    </div>
    ${copies(live, values, res.reload, copyAct, release, armed, setArmed)}
    <div class="card mt">
      <h3 data-help="linked-users">Users on linked servers</h3>
      <p class="small dim" style=${{ marginTop: '-6px' }}>Each linked server's active users,
        kept up to date at every exchange. People here can share with them, read only; they
        never sign in here.</p>
      ${people.length
        ? people.map((/** @type {any} */ l) =>
          html`<div class="small dim" style=${{ margin: '10px 0 2px' }}><${Icon} name="server" />
            <b>${l.peerName}</b></div>${
            l.users.map((/** @type {any} */ u) =>
              html`
                <div
                  class="list-item"><div class="grow">${u.displayName}<div class="small dim">${u
                    .username}${u.email
                    ? ` · ${u.email}`
                    : ''}</div></div><span class="pill">remote ·
                                read only</span></div>
              `
            )
          }`
        )
        : html`<p class="small dim">None yet.</p>`}
    </div>
  `;
}

/** @param {{ close: (v?: any) => void }} p */
function InviteLink({ close }) {
  useDialogGuide('dialog-link-invite');
  const [made, setMade] = useState(/** @type {any} */ (null));
  const make = useSubmit(async () => {
    setMade(await api.post('/settings/links/invitations'));
  });
  useEffect(() => {
    make.run().catch(() => {});
  }, []);
  return html`
    <${Dialog} title="Invite a server to link" close=${close} onSubmit=${() => close(true)}
      note="It works once, for 24 hours."
      footer=${html`
        <button type="button" class="btn" disabled=${!made} onClick=${() =>
          navigator.clipboard?.writeText(made.code).then(() => toast('Copied'))}>Copy</button>
        <button class="btn primary">Done</button>
      `}>
      <p class="small dim" style=${{ marginTop: 0 }}>Give this code to the other server's
        admin. It holds this server's link address and key fingerprint.</p>
      ${make.error ? html`<${FormError} error=${make.error} />` : made
        ? html`
          <div class="field"
            data-help="link-code"><code class="mono" style=${{
              display: 'block',
              padding: '10px 12px',
              background: 'var(--bg-3)',
              borderRadius: '8px',
            }}>${made.code}</code></div>
        `
        : html`<${Loading} lines=${2} />`}
      <div class="notice mt"><${Icon} name="info" /><div>When they enter it, their server shows
        here as <b>wants to link</b>, with its fingerprint. Compare fingerprints with them (by
        phone, in person) before approving.</div></div>
    </${Dialog}>
  `;
}

/** @param {{ close: (v?: any) => void }} p */
function JoinLink({ close }) {
  useDialogGuide('dialog-link-join');
  const [code, setCode] = useState('');
  const save = useSubmit(async () => {
    const out = await api.post('/settings/links/join', { code });
    toast(`Asked ${out.peerName || 'the server'} to link`);
    close(out);
  });
  return html`
    <${Dialog} title="Enter a link code" close=${close} onSubmit=${() => save.run().catch(() => {})}
      footer=${html`<button class="btn primary" disabled=${save.busy || !code}>Connect</button>`}>
      <${Field} label="Link code" error=${errAt(save.error, 'code')}>
        <textarea class="in mono" rows="3" value=${code} onInput=${(/** @type {any} */ e) =>
          setCode(e.currentTarget.value)} placeholder="mkl1.…"
          spellcheck="false"></textarea>
        </${Field}>
        <p class="small dim">MoneyKata connects to the address in the code, checks that server's
        key against the fingerprint in it, and sends this server's address and key. Their admin
        approves it.</p>
        <${FormError} error=${save.error} shown=${['code']} />
        </${Dialog}>
  `;
}

/** @param {number} n */
const size = (n) =>
  n >= 1048576 ? `${(n / 1048576).toFixed(n >= 10485760 ? 0 : 1)} MB` : `${Math.ceil(n / 1024)} KB`;

/**
 * The Linked copies card (S11.7, S11.9): each copy's access key, size and lock, Create the
 * access key, Lock now and Reset copy, and how long an unused copy stays unlocked.
 * @param {any[]} live @param {any} values @param {() => void} reload @param {any} act
 * @param {any} release @param {string | null} armed @param {(v: string | null) => void} setArmed
 */
function copies(live, values, reload, act, release, armed, setArmed) {
  const rows = live.filter((l) => l.linkedCopy);
  return html`
    <div class="card mt">
      <h3 data-help="linked-copies">Linked copies</h3>
      <p class="small dim" style=${{ marginTop: '-6px' }}>Each link's copy is encrypted under its
        own <b>access key</b>: 12 words made here once and kept in the household's password
        manager. The first person its shares name who opens it enters the words; it then stays
        unlocked for everyone it shares with until it goes unused. This server's master key
        can't open it.</p>
      ${rows.length
        ? html`
          <div class="table-wrap">
            <table class="t">
              <caption class="sr-only">Linked copies</caption>
              <thead>
                <tr>
                  <th>Link</th>
                  <th>Copy</th>
                  <th>Access key</th>
                  <th>State</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>${rows.map((l) => {
                const c = l.linkedCopy;
                const reset = armed === 'reset-' + l.id;
                return html`
                  <tr>
                    <td><b>${l.peerName}</b><div class="small dim">${c.items} item${c.items === 1
                      ? ''
                      : 's'} shared</div></td>
                    <td class="small">${size(c.sizeBytes)}${c.receipts
                      ? ` · ${c.receipts} receipt${c.receipts === 1 ? '' : 's'}`
                      : ''}</td>
                    <td class="small">${c.keyMadeAt
                      ? html`${date(c.keyMadeAt)}<div class="dim">by ${
                        c.keyMadeBy || 'an admin'
                      }</div>`
                      : html`<span class="pill warn">not made</span>`}</td>
                    <td class="small">${c.unlocked
                      ? html`<span class="pill info">unlocked</span><div class="dim">by ${c.unlockedBy} · locks in ${
                        Math.ceil((c.locksInSeconds || 0) / 60)
                      } min
                  unused</div>`
                      : html`<span class="pill"><${Icon} name="lock" /> locked</span>`}</td>
                    <td class="num" style=${{ whiteSpace: 'nowrap' }}>${!c.keyMadeAt
                      ? html`<button class="btn sm primary" onClick=${() =>
                        openDialog(CopyKey, { link: l }).then(
                          reload,
                        )}>Create the access key</button>`
                      : html`${
                        c.unlocked
                          ? html`
                            <button class="btn sm" onClick=${() =>
                              act.run(l.id, 'lock').catch(() => {})}>Lock now</button>
                          `
                          : null
                      }<button class="btn sm danger" onClick=${() =>
                        reset
                          ? act.run(l.id, 'reset-copy').then(() => setArmed(null), () => {})
                          : setArmed('reset-' + l.id)}>${
                        reset ? 'Click again to reset' : 'Reset copy'
                      }</button>`}</td>
                  </tr>
                `;
              })}</tbody>
            </table>
          </div>
        `
        : html`<p class="small dim">None yet: a copy is kept once a link is active.</p>`}
      <${Field} label="Release linked keys after" id="link-release"
        hint="An unlocked copy's key is dropped from memory after this long without anyone viewing it.">
        <${Select} value=${String(values.linkReleaseMinutes)} onChange=${(
          /** @type {string} */ v,
        ) => release.run(v).catch(() => {})} options=${[
          ['15', '15 minutes unused'],
          ['60', '1 hour unused'],
          ['240', '4 hours unused'],
        ]} />
      </${Field}>
      <${FormError} error=${act.error || release.error} />
    </div>
  `;
}

/** Create the access key (S11.9.2.1): the 12 words, shown once. */
/** @param {{ close: (v?: any) => void, link: any }} p */
function CopyKey({ close, link }) {
  useDialogGuide('dialog-copy-key');
  const [words, setWords] = useState(/** @type {string[] | null} */ (null));
  const [saved, setSaved] = useState(false);
  const make = useSubmit(async () => {
    setWords((await api.post(`/settings/links/${link.id}/copy-key`)).words);
  });
  useEffect(() => {
    make.run().catch(() => {});
  }, []);
  return html`
    <${Dialog} title=${`Access key for ${link.peerName}`} close=${close}
      onSubmit=${() => saved && close(true)} note="They are shown once."
      footer=${html`
        <button type="button" class="btn" disabled=${!words} onClick=${() =>
          navigator.clipboard?.writeText((words || []).join(' ')).then(() =>
            toast('Copied')
          )}>Copy</button>
        <button class="btn primary" disabled=${!saved}>Done, words saved</button>
      `}>
      <div class="notice" style=${{ marginBottom: '12px' }}><${Icon} name="link" /><div>
        <b>${link.peerName}</b>'s copy is kept encrypted under these 12 words. <b>They are
          shown once.</b></div></div>
      ${make.error
        ? html`<${FormError} error=${make.error} />`
        : words
        ? html`<div class="words" data-help="words">${
          words.map((w, i) => html`<div class="word"><span>${i + 1}</span><b>${w}</b></div>`)
        }</div>`
        : html`<${Loading} lines=${3} />`}
      <p class="small dim">Save them in the household's password manager, where the people its
        shares name can reach them. Whoever opens it first enters them. The words open only what
        is shared with each person. If they are lost, <b>Reset copy</b> makes new ones.</p>
      <label class="list-item" style=${{ cursor: 'pointer' }}><input type="checkbox"
        id="f-words-saved" checked=${saved} onChange=${(/** @type {any} */ e) =>
          setSaved(e.currentTarget.checked)} /> <span class="grow">I have saved the 12
          words</span></label>
    </${Dialog}>
  `;
}
