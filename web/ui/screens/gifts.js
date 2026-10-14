// Gifts (requirements S7.7, S7.8, S12.2.8): Upcoming occasions, People, Gifts from idea to given
// (and received), and Spending by person, occasion and year.
import { useState } from 'preact/hooks';
import { html } from '../app/html.js';
import { api } from '../api/client.js';
import { useApi, useSubmit } from '../app/hooks.js';
import { date } from '../app/format.js';
import { useTitle } from '../components/frame.js';
import { useDialogGuide, useGuide } from '../components/help.js';
import { Amt } from '../components/amount.js';
import { Chips, Empty, Failed, Loading, Tabs } from '../components/bits.js';
import { Dialog, openDialog } from '../components/dialog.js';
import { errAt, Field, FormError, Input, Seg, Select, SwitchRow } from '../components/fields.js';
import { Icon } from '../components/icon.js';
import { ShareDialog } from '../components/share.js';
import { toast } from '../components/toast.js';
import { ACCEPT, uploadAll } from '../components/receipt.js';

const TABS = /** @type {[string, string][]} */ ([
  ['upcoming', 'Upcoming'],
  ['people', 'People'],
  ['gifts', 'Gifts'],
  ['spending', 'Spending'],
]);
export const STATUS = /** @type {[string, string][]} */ ([
  ['idea', 'Idea'],
  ['planned', 'Planned'],
  ['bought', 'Bought'],
  ['given', 'Given'],
  ['received', 'Received'],
]);
const TONE = /** @type {Record<string, string>} */ ({
  idea: '',
  planned: 'info',
  bought: 'ok',
  given: 'ok',
  received: '',
});
const clean = (/** @type {string} */ s) => (s ? String(s).replace(/[$,\s]/g, '') : '');

/** @param {{ status: string }} p */
function StatusPill({ status }) {
  return html`<span class=${'pill ' + (TONE[status] || '')}>${
    STATUS.find(([k]) => k === status)?.[1]
  }</span>`;
}

/** @param {{ tab?: string }} p */
export default function Gifts({ tab }) {
  const current = TABS.some(([k]) => k === tab) ? /** @type {string} */ (tab) : 'upcoming';
  useTitle('Gifts');
  useGuide('gifts-' + current);
  return html`
    <${Tabs} tabs=${TABS} current=${current} base="/ui/gifts" />
    ${current === 'upcoming' ? html`<${Upcoming} />` : null}
    ${current === 'people' ? html`<${People} />` : null}
    ${current === 'gifts' ? html`<${GiftList} />` : null}
    ${current === 'spending' ? html`<${Spending} />` : null}
  `;
}

function Upcoming() {
  const res = useApi('/gifts/upcoming');
  const rows = /** @type {any[]} */ (res.data);
  if (res.error) return html`<${Failed} error=${res.error} />`;
  if (!rows) return html`<${Loading} />`;
  const add = (/** @type {any} */ u) =>
    openDialog(GiftDialog, {
      start: u
        ? { people: [u.person.id], occasion: u.key, occasionYear: u.date.slice(0, 4) }
        : null,
    }).then(res.reload);
  const open = (/** @type {any} */ g) => openDialog(GiftDialog, { gift: g }).then(res.reload);
  return html`
    <div class="card"><h3>Next 60 days<span class="spacer"></span><button class="btn sm"
      onClick=${() => add(null)}><${Icon} name="plus" /> Add a gift</button></h3>
      ${rows.length
        ? rows.map((u) =>
          html`
            <div class="list-item" style=${{ alignItems: 'flex-start' }}>
              <div class="tile t-giving">
                <${Icon} name="gift" />
              </div>
              <div class="grow"><b>${u.person.name}</b> · ${u.label}${u.turns
                ? ` (${u.label === 'Birthday' ? 'turns' : ''} ${u.turns}${
                  u.label === 'Birthday' ? '' : ' years'
                })`
                : ''}
                          <div class="small dim">${date(u.date)} · ${u.days === 0
                            ? 'today'
                            : `in ${u.days} day${u.days === 1 ? '' : 's'}`}${u.inLead
                            ? html`
                              · <span class="pill warn">inside the reminder time</span>
                            `
                            : null}</div>
                          <div class="toolbar" style=${{
                            margin: '6px 0 0',
                            flexWrap: 'wrap',
                          }}>${u.gifts.length
                            ? u.gifts.map((/** @type {any} */ g) =>
                              html`
                                <button type="button" class="chip"
                                  onClick=${() => open(g)}>${g
                                    .description} <${StatusPill} status=${g.status} /></button>
                              `
                            )
                            : html`<span class="small dim">${u.missing}</span>`}</div></div>
              <div
                class="num small"><b><${Amt} v=${u.planned} /></b>${u.budget
                  ? html`<div class="dim">of <${Amt} v=${u.budget} cents=${false} /></div>`
                  : null}<button class="btn sm mt" onClick=${() =>
                  add(
                    u,
                  )} aria-label=${`Add a gift for ${u.person.name}'s ${u.label.toLowerCase()}`}>Add</button></div>
            </div>
          `
        )
        : html`<${Empty}>Nothing in the next 60 days. Add people, with their birthdays,
          anniversaries and holidays, on the People tab.</${Empty}>`}
    </div>
  `;
}

function People() {
  const res = useApi('/people', {}, ['share']);
  const rows = /** @type {any[]} */ (res.data);
  if (res.error) return html`<${Failed} error=${res.error} />`;
  if (!rows) return html`<${Loading} />`;
  const open = (/** @type {any} */ p) => openDialog(PersonDialog, { p }).then(res.reload);
  return html`
    <div class="card" style=${{ padding: '4px 8px' }}>
      <h3 style=${{ padding: '8px 8px 0' }}>People<span class="spacer"></span><button class="btn sm"
        onClick=${() => open(null)}><${Icon} name="plus" /> Add a person</button></h3>
      ${rows.length
        ? html`
          <div class="table-wrap">
            <table class="t">
              <caption class="sr-only">People</caption>
              <thead>
                <tr>
                  <th>Person</th>
                  <th>Next</th>
                  <th class="num">Budget</th>
                  <th class="num">Spent this year</th>
                  <th>Last gift</th>
                </tr>
              </thead>
              <tbody>${rows.map((p) =>
                html`
                  <tr class="click" tabindex="0" onClick=${() => open(p)} onKeyDown=${(
                    /** @type {KeyboardEvent} */ e,
                  ) => e.key === 'Enter' && open(p)}>
                    <td style=${{ whiteSpace: 'nowrap' }}><b>${p.name}</b><div class="small dim">${[
                      p.relationship,
                      p.level === 'owner' ? null : `shared by ${p.ownerName}`,
                    ].filter(Boolean).join(' · ')}</div></td>
                    <td class="small">${p.next
                      ? html`${p.next.label} · ${
                        date(p.next.date)
                      }<div class="dim">in ${p.next.days} days</div>`
                      : html`<span class="dim">—</span>`}</td>
                    <td class="num">${p.giftBudget
                      ? html`<${Amt} v=${p.giftBudget} cents=${false} />`
                      : html`<span class="dim">—</span>`}</td>
                    <td class="num">
                      <${Amt} v=${p.spent} cents=${false} />
                    </td>
                    <td class="small dim">${p.lastGift || '—'}</td>
                  </tr>
                `
              )}</tbody>
            </table>
          </div>
        `
        : html`<${Empty}>No people yet. Add the people you give gifts to, with their dates.</${Empty}>`}
    </div>
    <p class="small dim">Your people and gifts are yours alone, unless you share a person. A gift
      for someone who is a user here is never shown to them, even through a share.</p>
  `;
}

function GiftList() {
  const [status, setStatus] = useState('');
  const res = useApi('/gifts', { status: status || undefined });
  const rows = /** @type {any[]} */ (res.data);
  const open = (/** @type {any} */ g) => openDialog(GiftDialog, { gift: g }).then(res.reload);
  return html`
    <div class="toolbar"><${Chips} label="Show" value=${status} onChange=${setStatus}
      options=${[['', 'All'], ...STATUS]} /><span class="spacer"></span><button
      class="btn primary" onClick=${() =>
        open(null)}><${Icon} name="plus" /> Add a gift</button></div>
    ${res.error ? html`<${Failed} error=${res.error} />` : !rows ? html`<${Loading} />` : rows
        .length
      ? html`
        <div class="card" style=${{ padding: '4px 8px' }}>
          <div class="table-wrap">
            <table
              class="t">
              <caption class="sr-only">Gifts</caption>
              <thead>
                <tr>
                  <th>For</th>
                  <th>Occasion</th>
                  <th>Gift</th>
                  <th>Status</th>
                  <th class="num">Cost</th>
                </tr>
              </thead>
              <tbody>${rows.map((g) =>
                html`
                  <tr class="click" tabindex="0" onClick=${() => open(g)} onKeyDown=${(
                    /** @type {KeyboardEvent} */ e,
                  ) => e.key === 'Enter' && open(g)}>
                    <td style=${{ whiteSpace: 'nowrap' }}>${g.status === 'received'
                      ? 'From '
                      : ''}${g
                      .people.map((/** @type {any} */ p) => p.name).join(', ')}</td>
                    <td class="small" style=${{ whiteSpace: 'nowrap' }}>${g
                      .occasionLabel}${g.occasionYear ? ` ${g.occasionYear}` : ''}</td>
                    <td>${g.description}${g.status === 'received' && g.thankYou
                      ? html`
                        <span class="small dim">· thanked</span>
                      `
                      : null}</td>
                    <td>
                      <${StatusPill} status=${g.status} />
                    </td>
                    <td class="num">${g.cost ? html`<${Amt} v=${g.cost} />` : html`
                      <span
                        class="dim">—</span>
                    `}</td>
                  </tr>
                `
              )}</tbody>
            </table>
          </div>
        </div>
      `
      : html`<${Empty}>No gifts${status ? ' with that status' : ''} yet.</${Empty}>`}
  `;
}

function Spending() {
  const now = new Date().getFullYear();
  const [year, setYear] = useState(String(now));
  const res = useApi('/gifts/spending', { year });
  const v = /** @type {any} */ (res.data);
  if (res.error) return html`<${Failed} error=${res.error} />`;
  if (!v) return html`<${Loading} />`;
  const most = Math.max(1, ...v.byYear.map((/** @type {any} */ y) => Number(y.amount)));
  return html`
    <div class="toolbar">
      <${Chips} label="Year" value=${year} onChange=${setYear}
        options=${[now - 2, now - 1, now].map((y) => [String(y), String(y)])} />
    </div>
    ${v.flagged.length
      ? html`<div class="notice warn">${
        v.flagged.map((/** @type {any} */ f) =>
          html`<div>Money given to ${f.person.name} in ${v.year} comes to <${Amt} v=${f.given}
          cents=${false} />, above the <${Amt} v=${f.exclusion} cents=${false} /> annual
          exclusion: a gift-tax return (Form 709) is needed, even when no tax is due.</div>`
        )
      }</div>`
      : null}
    <div class="grid g-main mt">
      <div class="card"><h3>By person, ${v.year}</h3>${v.byPerson.length
        ? v.byPerson.map((/** @type {any} */ p) => {
          const share = p.budget ? Math.min(100, (Number(p.spent) / Number(p.budget)) * 100) : 0;
          return html`
            <div class="list-item">
              <div class="grow">${p.person.name}${p.budget
                ? html`<div class="bar" style=${{ marginTop: '6px' }}><i style=${{
                  width: `${share}%`,
                }}></i></div>`
                : null}</div>
              <div class="num small"><b><${Amt} v=${p.spent} cents=${false} /></b>${p
                  .budget
                ? html`<div class="dim">of <${Amt} v=${p.budget} cents=${false} /></div>`
                : null}</div>
            </div>
          `;
        })
        : html`<p class="small dim">No people yet.</p>`}</div>
      <div class="grid" style=${{ alignContent: 'start' }}>
        <div class="card"><h3>By occasion, ${v.year}</h3>${v.byOccasion.length
          ? v.byOccasion.map((/** @type {any} */ o) =>
            html`
              <div
                class="list-item"><span class="grow">${o.label}</span><${Amt} v=${o
                  .amount} cents=${false} /></div>
            `
          )
          : html`<p class="small dim">Nothing bought or given yet.</p>`}</div>
        <div class="card"><h3>By year</h3>${v.byYear.map((/** @type {any} */ y) =>
          html`
            <div
              class="list-item"><span class="small" style=${{ width: '48px' }}>${y
                .label}</span><div class="grow"><div class="bar"><i style=${{
                width: `${(Number(y.amount) / most) * 100}%`,
                background: 'var(--hue-giving)',
              }}></i></div></div><span class="num small" style=${{ width: '72px' }}><${Amt}
                        v=${y.amount} cents=${false} /></span></div>
          `
        )}</div>
      </div>
    </div>
  `;
}

/** @param {any} p */
function personForm(p) {
  return {
    name: p?.name || '',
    relationship: p?.relationship || '',
    userId: p?.userId || '',
    birthday: p?.birthMonth
      ? `${p.birthYear || ''}-${String(p.birthMonth).padStart(2, '0')}-${
        String(p.birthDay)
          .padStart(2, '0')
      }`.replace(/^-/, '')
      : '',
    giftBudget: p?.giftBudget || '',
    leadDays: String(p?.leadDays ?? 14),
    notes: p?.notes || '',
    holidays: (p?.occasions || []).filter((/** @type {any} */ o) => o.kind === 'holiday').map((
      /** @type {any} */ o,
    ) => o.holiday),
    dated: (p?.occasions || []).filter((/** @type {any} */ o) => o.kind !== 'holiday').map((
      /** @type {any} */ o,
    ) => ({
      kind: o.kind,
      name: o.name || '',
      date: `${o.year || ''}-${String(o.month).padStart(2, '0')}-${String(o.day).padStart(2, '0')}`
        .replace(/^-/, ''),
      budget: o.budget || '',
    })),
  };
}

/** "2018-10-20" or "10-20": month, day and the year if given. */
/** @param {string} s */
function parseDay(s) {
  const m = s.trim().match(/^(?:(\d{4})-)?(\d{1,2})-(\d{1,2})$/);
  if (!m) return null;
  return { year: m[1] ? Number(m[1]) : null, month: Number(m[2]), day: Number(m[3]) };
}

/** @param {{ close: (v?: any) => void, p: any }} p */
function PersonDialog({ close, p }) {
  useDialogGuide('dialog-person');
  const hols = useApi('/holidays');
  const me = useApi('/profile');
  const [f, setF] = useState(personForm(p));
  const set = (/** @type {string} */ k) => (/** @type {any} */ x) => setF({ ...f, [k]: x });
  const canWrite = !p || p.level !== 'read';
  const save = useSubmit(async () => {
    const b = f.birthday ? parseDay(f.birthday) : null;
    const body = {
      name: f.name,
      relationship: f.relationship || null,
      userId: f.userId || null,
      birthMonth: b?.month ?? null,
      birthDay: b?.day ?? null,
      birthYear: b?.year ?? null,
      giftBudget: clean(f.giftBudget) || null,
      leadDays: Number(f.leadDays) || 0,
      notes: f.notes || null,
      occasions: [
        ...f.holidays.map((/** @type {string} */ h) => ({ kind: 'holiday', holiday: h })),
        ...f.dated.map((/** @type {any} */ o) => {
          const d = parseDay(o.date) || { year: null, month: 0, day: 0 };
          return {
            kind: o.kind,
            name: o.name || null,
            month: d.month,
            day: d.day,
            year: d.year,
            budget: clean(o.budget) || null,
          };
        }),
      ],
    };
    const out = p ? await api.put(`/people/${p.id}`, body) : await api.post('/people', body);
    toast(p ? 'Saved' : `${out.name} added`);
    close(out);
  });
  const e = save.error;
  const dated = (/** @type {number} */ i, /** @type {string} */ k) => (/** @type {string} */ x) =>
    set('dated')(
      f.dated.map((/** @type {any} */ o, /** @type {number} */ j) =>
        j === i ? { ...o, [k]: x } : o
      ),
    );
  const toggle = (/** @type {string} */ h) =>
    set('holidays')(
      f.holidays.includes(h)
        ? f.holidays.filter((/** @type {string} */ x) => x !== h)
        : [...f.holidays, h],
    );
  return html`
    <${Dialog} title=${p ? p.name : 'Add a person'} wide close=${close} onSubmit=${() =>
      canWrite && save.run().catch(() => {})}
      footer=${html`${
        p && p.level === 'owner'
          ? html`<button type="button" class="btn" onClick=${() =>
            openDialog(ShareDialog, { kind: 'person', id: p.id, name: p.name })}><${Icon}
            name="share" /> Share</button><span class="spacer"></span>`
          : null
      }${canWrite ? html`<button class="btn primary" disabled=${save.busy}>Save</button>` : null}`}>
      <fieldset disabled=${!canWrite} style=${{ border: 0, padding: 0, margin: 0, minWidth: 0 }}>
        <${Field} label="Name" error=${errAt(e, 'name')}>
          <${Input} value=${f.name}
            onInput=${set('name')} required placeholder="Emma Griffin" />
          </${Field}>
          <div class="row">
            <${Field} label="Relationship" error=${errAt(e, 'relationship')}>
              <${Input}
                value=${f.relationship} onInput=${set('relationship')}
                placeholder="daughter, friend…" />
              </${Field}>
              <${Field} label="Linked user" id="linked-user" error=${errAt(e, 'userId')}
                hint="Gifts for them are never shown to them.">
                <${Select} value=${f.userId} onChange=${set('userId')} options=${[
                  ['', 'None'],
                  ...((/** @type {any} */ (me.data))?.people || []).map((/** @type {any} */ u) => [
                    u.id,
                    u.displayName,
                  ]),
                ]} />
                </${Field}>
                </div>
                <div class="row">
                  <${Field} label="Birthday" error=${errAt(e, 'birthDay') ||
                    errAt(e, 'birthMonth') ||
                    errAt(e, 'birthYear')}
                    hint="2018-10-20, or 10-20 without the year.">
                    <${Input} value=${f.birthday} onInput=${set(
                      'birthday',
                    )} placeholder="YYYY-MM-DD" />
                    </${Field}>
                    <${Field} label="Yearly gift budget" id="gift-budget" error=${errAt(
                      e,
                      'giftBudget',
                    )}>
            <${Input} value=${f.giftBudget} onInput=${set('giftBudget')} inputmode="decimal"
              placeholder="600" /></${Field}>
        </div>
        <div class="field" data-help="holidays" id="x-holidays"><label>Holidays</label>
          <div class="chips" style=${{
            flexWrap: 'wrap',
          }}>${(/** @type {any[]} */ (hols.data) || []).map((h) =>
            html`
              <button type="button" class=${'chip' + (f.holidays.includes(h.key) ? ' on' : '')}
                aria-pressed=${f.holidays.includes(h.key) ? 'true' : 'false'} onClick=${() =>
                  toggle(h.key)}>${h.label}</button>
            `
          )}</div></div>
        <div class="toolbar"><b class="small" data-help="dates">Anniversaries and other dates</b><span
          class="spacer"></span><button type="button" class="btn sm" onClick=${() =>
            set('dated')([...f.dated, {
              kind: 'anniversary',
              name: '',
              date: '',
              budget: '',
            }])}><${Icon}
            name="plus" /> Add a date</button></div>
        ${f.dated.map((/** @type {any} */ o, /** @type {number} */ i) =>
          html`
            <div class="row">
              <${Field} label="What" help="dates" id=${'date-kind-' + i}>
                <${Select} value=${o.kind}
                  onChange=${dated(i, 'kind')} options=${[
                    ['anniversary', 'Anniversary'],
                    ['custom', 'Other occasion'],
                  ]} />
                </${Field}>
                <${Field} label="Called" help="dates" id=${'date-name-' + i}
                  error=${errAt(e, `occasions.${f.holidays.length + i}.name`)}>
                  <${Input} value=${o.name}
                    onInput=${dated(i, 'name')} placeholder=${o.kind === 'anniversary'
                      ? 'Wedding'
                      : 'Name day'} />
                  </${Field}>
                  <${Field} label="On" help="dates" id=${'date-on-' + i}
                    error=${errAt(e, `occasions.${f.holidays.length + i}.month`)}>
                    <${Input} value=${o.date}
                      onInput=${dated(i, 'date')} placeholder="YYYY-MM-DD" />
                    </${Field}>
                    <${Field} label="Budget" help="dates" id=${'date-budget-' + i}>
                      <${Input} value=${o.budget}
                        onInput=${dated(i, 'budget')} inputmode="decimal" />
                      </${Field}>
                      <button type="button" class="icon-btn" aria-label="Remove the date"
                        onClick=${() =>
                          set('dated')(
                            f.dated.filter((/** @type {any} */ _, /** @type {number} */ j) =>
                              j !== i
                            ),
                          )}><${Icon} name="x" /></button>
                      </div>
          `
        )}
        <${Field} label="Remind me" id="lead-days" error=${errAt(e, 'leadDays')}>
          <${Select} value=${f.leadDays} onChange=${set('leadDays')} options=${[
            ['7', '7 days before'],
            ['14', '14 days before'],
            ['30', '30 days before'],
          ]} /></${Field}>
        <${Field} label="Notes" error=${errAt(
          e,
          'notes',
        )} hint="Sizes, likes, what they already have.">
          <textarea class="in" rows="3" value=${f.notes} onInput=${(/** @type {any} */ ev) =>
            set('notes')(ev.currentTarget.value)}></textarea></${Field}>
        <${FormError} error=${e} />
      </fieldset>
      ${p ? html`<${History} p=${p} />` : null}
    </${Dialog}>
  `;
}

/** What was given a person in past years, so it isn't given twice. */
/** @param {{ p: any }} p */
function History({ p }) {
  const res = useApi('/gifts', { person: p.id, status: 'given' });
  const rows = /** @type {any[]} */ (res.data) || [];
  if (!rows.length) return null;
  return html`<h4 style=${{ margin: '14px 0 8px' }} data-help="given-before">Given before</h4>
    ${
    rows.map((g) =>
      html`<div class="list-item"><span class="grow">${g.description}<span class="small dim">
        · ${g.occasionLabel} ${g.occasionYear || ''}</span></span>${
        g.cost ? html`<${Amt} v=${g.cost} />` : null
      }</div>`
    )
  }`;
}

/** @param {any} g @param {any} start */
function giftForm(g, start) {
  return {
    people: g ? g.people.map((/** @type {any} */ p) => p.id) : start?.people || [],
    occasion: g
      ? (g.occasion ? `${g.occasion}|${g.occasionYear}` : '')
      : start?.occasion
      ? `${start.occasion}|${start.occasionYear}`
      : '',
    description: g?.description || '',
    status: g?.status || (start ? 'planned' : 'idea'),
    cost: g?.cost || '',
    transactionId: g?.paid?.transactionId || '',
    store: g?.store || '',
    link: g?.link || '',
    notes: g?.notes || '',
    cash: g?.cash || false,
    thankYou: g?.thankYou || false,
  };
}

/** @param {{ close: (v?: any) => void, gift?: any, start?: any }} p */
function GiftDialog({ close, gift, start }) {
  useDialogGuide('dialog-gift');
  const people = useApi('/people');
  const buys = useApi('/gifts/purchases');
  const [f, setF] = useState(giftForm(gift, start));
  const set = (/** @type {string} */ k) => (/** @type {any} */ x) => setF({ ...f, [k]: x });
  const list = /** @type {any[]} */ (people.data) || [];
  const canWrite = !gift || gift.canWrite;
  const year = new Date().getFullYear();
  // The occasions of the chosen people, this year and next.
  const chosen = list.filter((p) => f.people.includes(p.id));
  /** @type {[string, string][]} */
  const occasions = [['', 'No date (an idea)']];
  for (const y of [year, year + 1]) {
    const keys = new Map();
    for (const p of chosen) {
      if (p.birthMonth) keys.set('birthday', 'Birthday');
      for (const o of p.occasions) {
        keys.set(o.kind === 'holiday' ? `holiday:${o.holiday}` : `occasion:${o.id}`, o.label);
      }
    }
    for (const [k, l] of keys) occasions.push([`${k}|${y}`, `${l} ${y}`]);
  }
  if (f.occasion && !occasions.some(([k]) => k === f.occasion)) {
    occasions.push([
      f.occasion,
      `${gift?.occasionLabel || 'Occasion'} ${f.occasion.split('|')[1]}`,
    ]);
  }
  const save = useSubmit(async () => {
    const [occ, y] = f.occasion ? f.occasion.split('|') : [null, null];
    const body = {
      people: f.people,
      occasion: occ,
      occasionYear: y ? Number(y) : null,
      description: f.description,
      status: f.status,
      cost: clean(f.cost) || null,
      transactionId: f.transactionId || null,
      store: f.store || null,
      link: f.link || null,
      notes: f.notes || null,
      cash: f.cash,
      thankYou: f.thankYou,
    };
    const out = gift ? await api.put(`/gifts/${gift.id}`, body) : await api.post('/gifts', body);
    toast('Gift saved');
    close(out);
  });
  const remove = useSubmit(async () => {
    await api.del(`/gifts/${gift.id}`);
    toast('Gift deleted');
    close(true);
  });
  const [busy, setBusy] = useState(false);
  const send = async (/** @type {FileList} */ files) => {
    setBusy(true);
    for (const r of await uploadAll(files)) {
      await api.post(`/gifts/${gift.id}/documents`, { receiptId: r.id });
    }
    setBusy(false);
    toast('Receipt kept with the gift');
  };
  const e = save.error;
  const received = f.status === 'received';
  return html`
    <${Dialog} title=${gift ? gift.description : 'Add a gift'} close=${close} onSubmit=${() =>
      canWrite && save.run().catch(() => {})}
      footer=${html`${
        gift && canWrite
          ? html`
            <button type="button" class="btn danger" onClick=${() =>
              remove.run().catch(() => {})}>Delete</button><span
              class="spacer"></span>
          `
          : null
      }${canWrite ? html`<button class="btn primary" disabled=${save.busy}>Save</button>` : null}`}>
      <fieldset disabled=${!canWrite} style=${{ border: 0, padding: 0, margin: 0, minWidth: 0 }}>
        <div class="field" data-help="status" id="x-status"><label>Status</label>
          <${Seg} label="Status" value=${f.status} onChange=${set(
            'status',
          )} options=${STATUS} /></div>
        <${Field} label=${received ? 'From' : 'For'} id="people" error=${errAt(e, 'people')}
          hint=${received ? '' : 'One or more people.'}>
          <select class="in" multiple size=${Math.min(4, Math.max(2, list.length))} value=${f
            .people}
            onChange=${(/** @type {any} */ ev) =>
              set('people')([...ev.currentTarget.selectedOptions].map((o) => o.value))}>
            ${list.map((p) =>
              html`<option value=${p.id} selected=${f.people.includes(p.id)}>${p.name}</option>`
            )}</select></${Field}>
        <${Field} label="Occasion" error=${errAt(e, 'occasionYear')}>
          <${Select} value=${f.occasion} onChange=${set(
            'occasion',
          )} options=${occasions} /></${Field}>
        <${Field} label="Description" error=${errAt(e, 'description')}><${Input}
          value=${f.description} onInput=${set('description')} required
          placeholder="Watercolour set" /></${Field}>
        ${received
          ? html`
            <${SwitchRow} label="Thank-you sent" on=${f.thankYou}
              onChange=${set('thankYou')} />
          `
          : html`
            <div class="row">
              <${Field} label="Cost" error=${errAt(e, 'cost')}>
                <${Input} value=${f.cost}
                  onInput=${set('cost')} inputmode="decimal" />
                </${Field}>
                <${Field} label="Paid with" id="paid-with" error=${errAt(e, 'transactionId')}
                  hint="Its transaction; one purchase can pay for several gifts.">
                  <${Select} value=${f.transactionId} onChange=${(/** @type {string} */ x) => {
                    const t = (/** @type {any[]} */ (buys.data) || []).find((b) =>
                      b.transactionId === x
                    );
                    setF({
                      ...f,
                      transactionId: x,
                      cost: f.cost || (t ? String(-Number(t.amount)) : ''),
                    });
                  }} options=${[
                    ['', 'Typed, or not bought yet'],
                    ...(gift?.paid &&
                        !(/** @type {any[]} */ (buys.data) || []).some((b) =>
                          b.transactionId === gift.paid.transactionId
                        )
                      ? [[
                        gift.paid.transactionId,
                        `${gift.paid.payee || 'Purchase'} · ${
                          date(
                            gift.paid.date,
                          )
                        }`,
                      ]]
                      : []),
                    ...(/** @type {any[]} */ (buys.data) || []).map((b) => [
                      b.transactionId,
                      `${b.payee || 'Purchase'} · ${date(b.date)} · ${b.accountName} ${b.amount}`,
                    ]),
                  ]} />
                  </${Field}>
                  </div>
                  <${SwitchRow} label="Given in money"
                    hint="Cash or a cheque: counted against the annual gift exclusion."
                    on=${f.cash} onChange=${set('cash')} />
                  <div class="row">
                    <${Field} label="Where bought" id="store" error=${errAt(e, 'store')}>
                      <${Input}
                        value=${f.store} onInput=${set('store')} />
                      </${Field}>
                      <${Field} label="Link" error=${errAt(e, 'link')}>
                        <${Input} value=${f.link}
                          onInput=${set('link')} placeholder="https://" />
                        </${Field}>
                        </div>
          `}
        <${Field} label="Notes" error=${errAt(e, 'notes')}><textarea class="in" rows="2"
          value=${f.notes} onInput=${(/** @type {any} */ ev) =>
            set('notes')(ev.currentTarget.value)}></textarea></${Field}>
        <${FormError} error=${e} />
      </fieldset>
      ${gift && canWrite
        ? html`
          <div
            class="toolbar"><label class="btn sm" for="f-gift-files"><${Icon} name="clip" /> ${busy
              ? 'Uploading…'
              : `Attach a receipt${
                gift.documents.length ? ` (${gift.documents.length})` : ''
              }`}</label><input
                    id="f-gift-files" class="sr-only" type="file" multiple accept=${ACCEPT} data-help="receipts"
                    onChange=${(/** @type {any} */ ev) => {
                      send(ev.currentTarget.files);
                      ev.currentTarget.value = '';
                    }} /></div>
        `
        : null}
    </${Dialog}>
  `;
}
