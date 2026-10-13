// The guides' Markdown (requirements S12.7.4): headings, paragraphs, lists, tables, code, quotes
// (shown as notes), images, links, bold and italic. Everything is built as elements from text,
// so raw HTML in a guide is shown as text, never parsed.
import { h } from 'preact';
import { slug } from '../app/format.js';

/**
 * Inline spans: `code`, **bold**, *italic* or _italic_, [links](url) and ![images](src).
 * @param {string} text
 * @param {(src: string) => string} resolve
 * @returns {any[]}
 */
function inline(text, resolve) {
  const out = [];
  const re =
    /(`[^`]+`)|(!\[[^\]]*\]\([^)]+\))|(\[[^\]]+\]\([^)]+\))|(\*\*[^*]+\*\*)|(\*[^*]+\*)|(\b_[^_]+_\b)/;
  let rest = text;
  while (rest) {
    const m = rest.match(re);
    if (!m || m.index === undefined) {
      out.push(rest);
      break;
    }
    if (m.index) out.push(rest.slice(0, m.index));
    const t = m[0];
    if (t.startsWith('`')) out.push(h('code', null, t.slice(1, -1)));
    else if (t.startsWith('![')) {
      const [, alt, src] = /** @type {RegExpMatchArray} */ (t.match(/!\[([^\]]*)\]\(([^)]+)\)/));
      out.push(h('img', { src: resolve(src), alt, loading: 'lazy' }));
    } else if (t.startsWith('[')) {
      const [, label, href] = /** @type {RegExpMatchArray} */ (t.match(/\[([^\]]+)\]\(([^)]+)\)/));
      const external = /^https?:/.test(href);
      out.push(h('a', {
        href,
        target: external ? '_blank' : undefined,
        rel: external ? 'noopener noreferrer' : undefined,
      }, inline(label, resolve)));
    } else if (t.startsWith('**')) out.push(h('b', null, inline(t.slice(2, -2), resolve)));
    else out.push(h('i', null, inline(t.slice(1, -1), resolve)));
    rest = rest.slice(m.index + t.length);
  }
  return out;
}

/**
 * A heading's anchor: an id it lists ("## Lot method {#lots}") or its text's slug (S12.7.3).
 * @param {string} text
 */
export function anchorOf(text) {
  const m = text.match(/\{#([a-z0-9-]+)\}\s*$/);
  return m ? { text: text.slice(0, m.index).trim(), id: m[1] } : { text, id: slug(text) };
}

/**
 * @param {string} md
 * @param {(src: string) => string} resolve  where an image's path points
 */
export function render(md, resolve = (s) => s) {
  const lines = md.replace(/\r/g, '').split('\n');
  const out = [];
  let i = 0;
  let key = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      i++;
      continue;
    }
    if (line.startsWith('```')) {
      const code = [];
      i++;
      while (i < lines.length && !lines[i].startsWith('```')) code.push(lines[i++]);
      i++;
      out.push(h('pre', { key: key++ }, h('code', null, code.join('\n'))));
      continue;
    }
    const head = line.match(/^(#{1,3})\s+(.*)$/);
    if (head) {
      const level = head[1].length;
      const { text, id } = anchorOf(head[2]);
      out.push(h('h' + level, {
        key: key++,
        id: level === 2 ? 'h-' + id : undefined,
        'data-anchor': level === 2 ? id : undefined,
      }, inline(text, resolve)));
      i++;
      continue;
    }
    if (line.startsWith('>')) {
      const quote = [];
      while (i < lines.length && lines[i].startsWith('>')) {
        quote.push(lines[i++].replace(/^>\s?/, ''));
      }
      out.push(h('blockquote', { key: key++ }, inline(quote.join(' '), resolve)));
      continue;
    }
    if (/^\s*([-*]|\d+\.)\s+/.test(line)) {
      const ordered = /^\s*\d+\./.test(line);
      const items = [];
      while (i < lines.length && /^\s*([-*]|\d+\.)\s+/.test(lines[i])) {
        let item = lines[i++].replace(/^\s*([-*]|\d+\.)\s+/, '');
        while (
          i < lines.length && /^\s{2,}\S/.test(lines[i]) && !/^\s*([-*]|\d+\.)\s/.test(lines[i])
        ) {
          item += ' ' + lines[i++].trim();
        }
        items.push(h('li', null, inline(item, resolve)));
      }
      out.push(h(ordered ? 'ol' : 'ul', { key: key++ }, items));
      continue;
    }
    if (line.startsWith('|')) {
      const rows = [];
      while (i < lines.length && lines[i].startsWith('|')) rows.push(lines[i++]);
      const cells = (/** @type {string} */ r) => r.slice(1, -1).split('|').map((c) => c.trim());
      const [first, sep, ...body] = rows;
      const hasHead = sep && /^\|[\s:|-]+\|$/.test(sep);
      out.push(h('table', { key: key++ }, [
        hasHead
          ? h(
            'thead',
            null,
            h('tr', null, cells(first).map((c) => h('th', null, inline(c, resolve)))),
          )
          : null,
        h(
          'tbody',
          null,
          (hasHead ? body : rows).map((r) =>
            h('tr', null, cells(r).map((c) => h('td', null, inline(c, resolve))))
          ),
        ),
      ]));
      continue;
    }
    const para = [line];
    i++;
    while (
      i < lines.length && lines[i].trim() && !/^(#|>|```|\||\s*([-*]|\d+\.)\s)/.test(lines[i])
    ) {
      para.push(lines[i++]);
    }
    out.push(h('p', { key: key++ }, inline(para.join(' '), resolve)));
  }
  return out;
}

/**
 * Put the parts a guide names into it: a line "{{part NAME}}" becomes guides/NAME.md, and
 * "{{account-type SECTION}}" the section of guides/account-TYPE.md that starts "@@ SECTION".
 * @param {string} md
 * @param {(name: string) => Promise<string>} load
 * @param {Record<string, string>} vars
 */
export async function assemble(md, load, vars = {}) {
  const lines = md.split('\n');
  const out = [];
  for (const line of lines) {
    const part = line.match(/^\{\{part ([a-z0-9-]+)\}\}$/);
    const typed = line.match(/^\{\{account-type ([a-z0-9-]+)\}\}$/);
    if (part) out.push(await load(part[1]).catch(() => ''));
    else if (typed) {
      if (!vars.type) continue;
      const text = await load('account-' + vars.type).catch(() => '');
      const sections = text.split(/^@@ /m);
      const found = sections.find((s) => s.startsWith(typed[1] + '\n'));
      if (found) out.push(found.slice(typed[1].length + 1));
    } else out.push(line);
  }
  return out.join('\n');
}
