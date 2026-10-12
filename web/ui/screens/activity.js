// Activity (requirements §13.8): the changes worth showing, newest first, filtered by account
// and person; amounts are never named.
import { useEffect, useState } from 'preact/hooks';
import { html } from '../app/html.js';
import { api } from '../api/client.js';
import { useApi } from '../app/hooks.js';
import { changes } from '../app/stream.js';
import { moment } from '../app/format.js';
import { useTitle } from '../components/frame.js';
import { useGuide } from '../components/help.js';
import { Avatar, Empty, Failed, Loading } from '../components/bits.js';
import { Pager } from '../components/pager.js';
import { pageSize } from '../store/prefs.js';

export default function Activity() {
  useTitle('Activity');
  useGuide('activity');
  const [account, setAccount] = useState('');
  const [after, setAfter] = useState(/** @type {(string | null)[]} */ ([null]));
  const [newer, setNewer] = useState(0);
  const accounts = useApi('/accounts');
  const page = after.length;
  const res = useApi('/activity', {
    account: account || undefined,
    limit: pageSize.value,
    after: after[page - 1] ?? undefined,
  });
  const d = /** @type {any} */ (res.data);
  const first = d?.items?.[0]?.id;
  useEffect(() => {
    if (first && page === 1) {
      api.get('/activity/newer', { since: first }).then((r) => setNewer(r.count), () => {});
    }
  }, [first, Object.values(changes.value).reduce((a, b) => a + b, 0)]);
  return html`
    <div class="toolbar"><label class="sr-only" for="f-account">Account</label>
      <select class="in" id="f-account" style=${{ maxWidth: '240px' }} value=${account}
        onChange=${(/** @type {any} */ e) => {
          setAccount(e.currentTarget.value);
          setAfter([null]);
        }}><option value="">Everything</option>
        ${(/** @type {any[]} */ (accounts.data) || []).map((a) =>
          html`<option value=${a.id}>${a.name}</option>`
        )}</select></div>
    ${res.error
      ? html`<${Failed} error=${res.error} />`
      : !d
      ? html`<${Loading} lines=${8} />`
      : d.items.length
      ? html`
        <div class="card" style=${{ padding: '4px 8px' }}>
          <table class="t">
            <caption class="sr-only">Activity</caption>
            <thead>
              <tr>
                <th>When</th>
                <th>Who</th>
                <th>What</th>
              </tr>
            </thead>
            <tbody>${d.items.map((/** @type {any} */ a) =>
              html`
                <tr>
                  <td class="dim small" style=${{ whiteSpace: 'nowrap' }}>${moment(a.at)}</td>
                  <td>${a.actorName
                    ? html`
                      <span
                        class="mark"><${Avatar} sm name=${a.actorName} image=${a.actorAvatar} id=${a
                          .actorId} /> ${a.actorName}</span>
                    `
                    : html`<span class="pill">${
                      a.via === 'host' ? 'On the host' : 'MoneyKata'
                    }</span>`}</td>
                  <td>${a.text}</td>
                </tr>
              `
            )}</tbody>
          </table>
        </div>
      `
      : html`<${Empty}>Nothing yet.</${Empty}>`}
    ${d
      ? html`
        <${Pager} label="activity" shown=${d.items.length} page=${page} hasNext=${!!d.next}
          newer=${newer}
          onNewer=${() => {
            setNewer(0);
            setAfter([null]);
            res.reload();
          }} onPage=${(/** @type {number} */ n) =>
            setAfter(n === 1 ? [null] : n > page ? [...after, d.next] : after.slice(0, n))} />
      `
      : null}
  `;
}
