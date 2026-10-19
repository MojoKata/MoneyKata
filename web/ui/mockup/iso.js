// The router for the generated mockup (requirements S12.9). A page opened from a file has no
// origin to push addresses to, so the address lives after the '#': '#/ui/accounts'. Everything
// else is the router the app uses.
import { h } from 'preact';
import { useLayoutEffect, useMemo, useState } from 'preact/hooks';
import { LocationProvider as Real } from '@mk/preact-iso';

export * from '@mk/preact-iso';

const current = () => location.hash.slice(1) || '/ui/';

/** @param {{ children?: any }} props */
export function LocationProvider(props) {
  const [nav, setNav] = useState({ url: current(), push: false });

  useLayoutEffect(() => {
    const changed = () => setNav({ url: current(), push: true });
    const click = (/** @type {MouseEvent} */ e) => {
      if (e.ctrlKey || e.metaKey || e.altKey || e.shiftKey || e.button !== 0) return;
      const link = /** @type {HTMLAnchorElement | undefined} */ (e.composedPath().find((el) =>
        /** @type {Element} */ (el).nodeName === 'A'
      ));
      const href = link?.getAttribute('href');
      if (!href || !href.startsWith('/') || link?.target || link?.download) {
        return;
      }
      e.preventDefault();
      location.hash = href;
    };
    addEventListener('hashchange', changed);
    addEventListener('click', click);
    return () => {
      removeEventListener('hashchange', changed);
      removeEventListener('click', click);
    };
  }, []);

  const value = useMemo(() => {
    const u = new URL(nav.url, 'https://moolakata.invalid');
    return {
      url: nav.url,
      path: u.pathname.replace(/\/+$/g, '') || '/',
      query: Object.fromEntries(u.searchParams),
      route: (/** @type {string} */ url, /** @type {boolean} */ replace) => {
        if (replace) location.replace('#' + url);
        else location.hash = url;
      },
      back: () => history.back(),
      forward: () => history.forward(),
      wasPush: nav.push,
    };
  }, [nav]);

  // @ts-ignore: the context is the real router's, so its Router and hooks read this one
  return h(Real.ctx.Provider, { value }, props.children);
}
