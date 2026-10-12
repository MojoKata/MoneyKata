// Users and Groups, for admins (requirements §13.1): invitations, the active switch, groups and
// the built-in Admins group.
import { useState } from 'preact/hooks';
import { html } from '../app/html.js';
import { api } from '../api/client.js';
import { useApi, useSubmit } from '../app/hooks.js';
import { ago, date } from '../app/format.js';
import { useTitle } from '../components/frame.js';
import { useDialogGuide, useGuide } from '../components/help.js';
import { Avatar, Chips, Failed, Loading } from '../components/bits.js';
import { Icon } from '../components/icon.js';
import { Dialog, openDialog } from '../components/dialog.js';
import { errAt, Field, FormError, Input, Switch } from '../components/fields.js';
import { toast } from '../components/toast.js';

export default function Users() {
  useTitle('Users and Groups');
  useGuide('users');
  const users = useApi('/users');
  const groups = useApi('/groups');
  const [show, setShow] = useState('active');
  const [busy, setBusy] = useState('');
  const u = /** @type {any[]} */ (users.data);
  const g = /** @type {any[]} */ (groups.data);
  if (users.error) return html`<${Failed} error=${users.error} />`;
  if (!u || !g) return html`<${Loading} lines=${8} />`;
  const name = (/** @type {string} */ id) => g.find((x) => x.id === id)?.name;
  const reload = () => {
    users.reload();
    groups.reload();
  };
  const setActive = async (/** @type {any} */ x, /** @type {boolean} */ on) => {
    setBusy(x.id);
    try {
      await api.patch(`/users/${x.id}`, { active: on }, x.version);
      toast(`${x.displayName} is ${on ? 'active again' : 'inactive: their sessions ended'}`);
    } catch (e) {
      toast(/** @type {any} */ (e).message);
    } finally {
      setBusy('');
      reload();
    }
  };
  const asked = u.filter((x) => !x.active && x.reactivationAskedAt);
  const list = u.filter((x) => show === 'all' || x.active);
  return html`
    ${asked.length
      ? html`<div class="card"><h3>Asked to be made active again<span class="pill warn">${asked.length}</span></h3>
      ${
        asked.map((x) =>
          html`<div class="list-item"><${Avatar} name=${x.displayName} image=${x.avatar} id=${x.id} />
        <div class="grow">${x.displayName} · ${x.email}<div class="small dim">asked ${
            ago(x.reactivationAskedAt)
          }</div></div>
        <button type="button" class="btn sm primary" onClick=${() =>
            setActive(x, true)}>Make active</button></div>`
        )
      }</div>`
      : null}
    <div class="toolbar mt"><h2 style=${{
      margin: 0,
      fontSize: '15px',
    }}>Users</h2><span class="spacer"></span>
      <${Chips} label="Show" value=${show} onChange=${setShow} options=${[['active', 'Active'], [
        'all',
        'All, with inactive',
      ]]} />
      <button type="button" class="btn primary" onClick=${() =>
        openDialog(NewUser, { groups: g }).then((x) => x && reload())}>
        <${Icon} name="plus" /> New user</button></div>
    <div class="card" style=${{ padding: '4px 8px' }}>
      <table class="t">
        <caption class="sr-only">Users</caption>
        <thead>
          <tr>
            <th>Name</th>
            <th>Username</th>
            <th>Email</th>
            <th></th>
            <th class="num">Active</th>
          </tr>
        </thead>
        <tbody>${list.map((x) =>
          html`
            <tr>
              <td>
                <div class="acct-row">
                  <${Avatar} name=${x.displayName} image=${x.avatar} id=${x.id} />
                  <div>
                    <div class="name">${x.displayName}</div>
                    <div class="small">${x.groupIds.length
                      ? x.groupIds.map((/** @type {string} */ id) =>
                        html`
                          <span class="pill">${name(id)}</span>
                        `
                      )
                      : html`<span class="dim">no groups</span>`}</div>
                  </div>
                </div>
              </td>
              <td class="dim">${x.username}</td>
              <td class="dim">${x.email}</td>
              <td>${x.invited
                ? html`
                  <span class="pill warn">invited</span> <button type="button" class="btn sm"
                    onClick=${() =>
                      api.post(`/users/${x.id}/invitation`).then(
                        () => toast('Invitation sent again'),
                        (e) => toast(e.message),
                      )}>Resend invitation</button>
                `
                : html`<span class="small dim">${
                  x.lastSignInAt ? 'signed in ' + ago(x.lastSignInAt) : 'never signed in'
                }</span>`}
                      <button type="button" class="btn sm" onClick=${() =>
                        openDialog(EditUser, { user: x, groups: g }).then((r) =>
                          r && reload()
                        )}>Edit</button></td>
              <td class="num">
                <${Switch} on=${x.active} label=${'Active: ' +
                  x.displayName} disabled=${busy === x.id}
                  id=${'active-' + x.username} help="active" onChange=${(
                    /** @type {boolean} */ v,
                  ) => setActive(x, v)} />
              </td>
            </tr>
          `
        )}</tbody>
      </table>
    </div>
    <div class="toolbar mt"><h2 style=${{
      margin: 0,
      fontSize: '15px',
    }}>Groups</h2><span class="spacer"></span>
      <button type="button" class="btn" onClick=${() =>
        openDialog(GroupDialog, { users: u }).then((x) => x && reload())}>
        <${Icon} name="plus" /> New group</button></div>
    <div class="card" style=${{ padding: '4px 8px' }}>
      <table class="t">
        <caption class="sr-only">Groups</caption>
        <thead>
          <tr>
            <th>Name</th>
            <th>Members</th>
            <th>Made</th>
            <th class="num">Active</th>
          </tr>
        </thead>
        <tbody>${g.map((x) =>
          html`
            <tr class="click" onClick=${() =>
              openDialog(GroupDialog, { users: u, group: x }).then((r) => r && reload())}>
              <td><b>${x.name}</b>${x.builtIn
                ? html`
                  <span class="pill">built in</span>
                `
                : null}</td>
              <td>${x.memberIds.map((/** @type {string} */ m) => {
                const who = u.find((y) => y.id === m);
                return who
                  ? html`
                    <span title=${who.displayName}><${Avatar} sm name=${who.displayName} image=${who
                      .avatar} id=${who.id} /></span>
                  `
                  : null;
              })}</td>
              <td class="dim">${date(x.createdAt.slice(0, 10))}</td>
              <td class="num">${x.active ? 'yes' : 'no'}</td>
            </tr>
          `
        )}</tbody>
      </table>
    </div>
  `;
}

/** @param {{ close: (v?: any) => void, groups: any[] }} p */
function NewUser({ close, groups }) {
  useDialogGuide('dialog-new-user');
  const [f, setF] = useState({ displayName: '', username: '', email: '' });
  const [ids, setIds] = useState(/** @type {string[]} */ ([]));
  const set = (/** @type {string} */ k) => (/** @type {string} */ v) => setF({ ...f, [k]: v });
  const save = useSubmit(async () => {
    const u = await api.post('/users', { ...f, groupIds: ids }, { idempotent: true });
    toast(`Invitation sent to ${u.email}`);
    close(u);
  });
  const e = save.error;
  return html`
    <${Dialog} title="New user" close=${close} onSubmit=${() => save.run().catch(() => {})}
      note="They choose their own password from the invitation."
      footer=${html`<button class="btn primary" disabled=${save.busy}>Send the invitation</button>`}>
      <${Field} label="Name" id="display-name" error=${errAt(e, 'displayName')}>
        <${Input} value=${f.displayName} onInput=${set('displayName')} required />
        </${Field}>
        <div class="row">
          <${Field} label="Username" error=${errAt(e, 'username')}>
            <${Input} value=${f.username} onInput=${set('username')} required />
            </${Field}>
            <${Field} label="Email address" id="email" error=${errAt(e, 'email')}>
              <${Input} type="email" value=${f.email} onInput=${set('email')} required />
              </${Field}>
              </div>
              <${GroupPicker} groups=${groups} ids=${ids} setIds=${setIds} error=${errAt(
                e,
                'groupIds',
              )} />
              <${FormError} error=${e} shown=${['displayName', 'username', 'email', 'groupIds']} />
              </${Dialog}>
  `;
}

/** @param {{ close: (v?: any) => void, user: any, groups: any[] }} p */
function EditUser({ close, user, groups }) {
  useDialogGuide('dialog-edit-user');
  const [displayName, setName] = useState(user.displayName);
  const [email, setEmail] = useState(user.email || '');
  const [ids, setIds] = useState(/** @type {string[]} */ (user.groupIds));
  const save = useSubmit(async () => {
    const body = /** @type {Record<string, any>} */ ({ displayName, groupIds: ids });
    if (user.invited) body.email = email;
    close(await api.patch(`/users/${user.id}`, body, user.version));
    toast('Saved');
  });
  return html`
    <${Dialog} title=${user.displayName} close=${close} onSubmit=${() => save.run().catch(() => {})}
      footer=${html`<button class="btn primary" disabled=${save.busy}>Save</button>`}>
      <${Field} label="Name" id="display-name" error=${errAt(save.error, 'displayName')}>
        <${Input} value=${displayName} onInput=${setName} required />
        </${Field}>
        <${Field} label="Email address" id="email" error=${errAt(save.error, 'email')}
          hint=${user.invited
            ? 'Fix it before they join; the invitation then goes to the new address.'
            : 'Once a user has joined, they change it themselves.'}>
          <${Input} type="email" value=${email} onInput=${setEmail} disabled=${!user.invited} />
          </${Field}>
          <${GroupPicker} groups=${groups} ids=${ids} setIds=${setIds} error=${errAt(
            save.error,
            'groupIds',
          ) || errAt(save.error, 'memberIds')} />
          <${FormError} error=${save.error} shown=${[
            'displayName',
            'email',
            'groupIds',
            'memberIds',
          ]} />
          </${Dialog}>
  `;
}

/** @param {{ groups: any[], ids: string[], setIds: (v: string[]) => void, error?: string | null }} p */
function GroupPicker({ groups, ids, setIds, error }) {
  return html`<fieldset class="field" style=${{ border: 0, padding: 0, margin: '0 0 14px' }}>
    <legend class="small" style=${{ color: 'var(--fg-dim)' }}>Groups</legend>
    ${
    groups.filter((g) => g.active).map((g) =>
      html`<label class="list-item" style=${{ cursor: 'pointer' }}><input type="checkbox"
      checked=${ids.includes(g.id)} onChange=${() =>
        setIds(ids.includes(g.id) ? ids.filter((x) => x !== g.id) : [...ids, g.id])} />
      <span class="grow">${g.name}${
        g.builtIn
          ? html`
            <span class="small dim">· manages users, groups and Settings</span>
          `
          : null
      }</span></label>`
    )
  }
    ${error ? html`<div class="err">${error}</div>` : null}</fieldset>`;
}

/** @param {{ close: (v?: any) => void, users: any[], group?: any }} p */
function GroupDialog({ close, users, group }) {
  useDialogGuide('dialog-group');
  const [name, setName] = useState(group?.name || '');
  const [active, setActive] = useState(group ? group.active : true);
  const [ids, setIds] = useState(/** @type {string[]} */ (group?.memberIds || []));
  const save = useSubmit(async () => {
    const out = group
      ? await api.patch(`/groups/${group.id}`, {
        name: group.builtIn ? undefined : name,
        active: group.builtIn ? undefined : active,
        memberIds: ids,
      }, group.version)
      : await api.post('/groups', { name, memberIds: ids }, { idempotent: true });
    toast('Saved');
    close(out);
  });
  return html`
    <${Dialog} title=${group ? group.name : 'New group'} close=${close} onSubmit=${() =>
      save.run().catch(() => {})}
      footer=${html`<button class="btn primary" disabled=${save.busy}>Save</button>`}>
      <${Field} label="Name"
        error=${errAt(
          save.error,
          'name',
        )}><${Input} value=${name} onInput=${setName} required disabled=${group
          ?.builtIn} /></${Field}>
        ${group && !group.builtIn
          ? html`
            <div
              class="list-item"><span class="grow">Active<div class="small dim">An inactive group's shares give its members nothing.</div></span>
                  <${Switch} on=${active} onChange=${setActive} label="Active" /></div>
          `
          : null}
        <fieldset class="field" style=${{
          border: 0,
          padding: 0,
          margin: '14px 0',
        }}><legend class="small" style=${{ color: 'var(--fg-dim)' }}>Members</legend>
          ${users.filter((u) => u.active).map((u) =>
            html`<label class="list-item" style=${{ cursor: 'pointer' }}><input type="checkbox"
        checked=${ids.includes(u.id)} onChange=${() =>
              setIds(ids.includes(u.id) ? ids.filter((x) => x !== u.id) : [...ids, u.id])} />
        <${Avatar} sm name=${u.displayName} image=${u.avatar} id=${u.id} /><span class="grow">${u.displayName}</span></label>`
          )}
          ${errAt(save.error, 'memberIds')
            ? html`<div class="err">${errAt(save.error, 'memberIds')}</div>`
            : null}</fieldset>
        <${FormError} error=${save.error} shown=${['name', 'memberIds', 'active']} />
      </${Dialog}>
  `;
}
