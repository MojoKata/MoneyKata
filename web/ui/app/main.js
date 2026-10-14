// The browser app's entry point: the session decides between sign-in, the default admin's
// setup step, and the frame with its screens.
import { render } from 'preact';
import { useEffect } from 'preact/hooks';
import { lazy, LocationProvider, Route, Router, useLocation } from 'preact-iso';
import { html } from './html.js';
import { api, readLinked, whenSignedOut } from '../api/client.js';
import { applyTheme, helpOpen, theme } from '../store/prefs.js';
import { ended, loadSession, session } from '../store/session.js';
import { connect, disconnect } from './stream.js';
import { PUBLIC_PATHS, PublicScreens, Screens, SetupScreen } from './router.js';
import { Frame } from '../components/frame.js';
import { DialogHost } from '../components/dialog.js';
import { MenuHost } from '../components/menu.js';
import { Toasts } from '../components/toast.js';
import { installTooltips, TooltipHost } from '../components/tooltip.js';

// A linked household's window (S12.10) is a page of its own: everything it reads comes from
// that household's copy.
const LINKED = location.pathname.match(/^\/ui\/linked\/([^/]+)/);
if (LINKED) readLinked(LINKED[1]);
const LinkedWindow = lazy(() => import('../screens/linked.js'));

function signOutLocally(/** @type {string} */ why) {
  disconnect();
  session.value = null;
  ended.value = why || 'signed-out';
}

function App() {
  const { path } = useLocation();
  const s = session.value;

  useEffect(() => {
    if (s && !s.user.needsSetup) connect(signOutLocally);
  }, [s?.user?.id, s?.user?.needsSetup]);

  if (PUBLIC_PATHS.some((p) => path.startsWith(p))) return html`<${PublicScreens} />`;
  if (!s) return ended.value ? html`<${PublicScreens} />` : null;
  if (s.user.needsSetup) return html`<${SetupScreen} />`;
  if (LINKED) {
    return html`
      <${Router}>
        <${Route} default component=${LinkedWindow} />
        </${Router}>
    `;
  }
  return html`
    <${Frame} onSignOut=${async () => {
      try {
        await api.del('/session');
      } finally {
        signOutLocally('signed-out');
      }
    }}>
      <${Screens} />
      </${Frame}>
  `;
}

function Root() {
  return html`
    <${LocationProvider}>
      <${App} />
      <${DialogHost} />
      <${MenuHost} />
      <${TooltipHost} />
      <${Toasts} />
      </${LocationProvider}>
  `;
}

applyTheme();
matchMedia('(prefers-color-scheme: light)').addEventListener('change', () => {
  if (theme.value === 'system') applyTheme();
});
document.addEventListener('keydown', (e) => {
  if (e.key === 'F1') {
    e.preventDefault();
    helpOpen.value = !helpOpen.value;
  }
});
installTooltips();
whenSignedOut((code) => signOutLocally(code === 'account-disabled' ? 'disabled' : 'expired'));

const root = document.getElementById('app');
loadSession().then((info) => {
  if (info && theme.value !== info.user.theme) {
    // The profile's theme follows the user to a new browser; this browser remembers it after.
    theme.value = info.user.theme;
    applyTheme();
  }
  if (root) render(html`<${Root} />`, root);
});
