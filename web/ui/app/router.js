// The app's screens and their addresses. Each screen is a module loaded by import() on its
// first visit, so the first screen stays small (requirements S17.3.4).
import { lazy, Route, Router } from 'preact-iso';
import { html } from './html.js';

const screen = (/** @type {string} */ name) => lazy(() => import(`../screens/${name}.js`));

const Dashboard = screen('dashboard');
const Accounts = screen('accounts');
const Account = screen('account');
const Transactions = screen('transactions');
const Portfolios = screen('portfolios');
const Portfolio = screen('portfolio');
const Activity = screen('activity');
const Budgets = screen('budgets');
const Receipts = screen('receipts');
const Projections = screen('projections');
const Alerts = screen('alerts');
const Users = screen('users');
const Settings = screen('settings');
const Profile = screen('profile');
const NotFound = screen('notfound');

export function Screens() {
  return html`
    <${Router}>
      <${Route} path="/ui/" component=${Dashboard} />
      <${Route} path="/ui/accounts" component=${Accounts} />
      <${Route} path="/ui/accounts/:id" component=${Account} />
      <${Route} path="/ui/accounts/:id/:tab" component=${Account} />
      <${Route} path="/ui/transactions" component=${Transactions} />
      <${Route} path="/ui/portfolios" component=${Portfolios} />
      <${Route} path="/ui/portfolios/:id" component=${Portfolio} />
      <${Route} path="/ui/portfolios/:id/:tab" component=${Portfolio} />
      <${Route} path="/ui/budgets" component=${Budgets} />
      <${Route} path="/ui/budgets/:id/:tab" component=${Budgets} />
      <${Route} path="/ui/projections" component=${Projections} />
      <${Route} path="/ui/projections/:id" component=${Projections} />
      <${Route} path="/ui/receipts" component=${Receipts} />
      <${Route} path="/ui/activity" component=${Activity} />
      <${Route} path="/ui/alerts" component=${Alerts} />
      <${Route} path="/ui/users" component=${Users} />
      <${Route} path="/ui/settings" component=${Settings} />
      <${Route} path="/ui/settings/:section" component=${Settings} />
      <${Route} path="/ui/profile" component=${Profile} />
      <${Route} default component=${NotFound} />
      </${Router}>
  `;
}

const SignIn = screen('signin');
const Welcome = screen('welcome');
const Reset = screen('reset');
const ConfirmEmail = screen('confirm-email');
const SignupConfirm = screen('signup-confirm');

/** What can be opened without a session: sign-in, and the links emails carry. */
export function PublicScreens() {
  return html`
    <${Router}>
      <${Route} path="/ui/welcome" component=${Welcome} />
      <${Route} path="/ui/reset" component=${Reset} />
      <${Route} path="/ui/confirm-email" component=${ConfirmEmail} />
      <${Route} path="/ui/signup/confirm" component=${SignupConfirm} />
      <${Route} default component=${SignIn} />
      </${Router}>
  `;
}

// The default admin's setup step, at whatever address it was reached. It is in a Router too,
// which is what waits for a lazy screen's module.
const Setup = screen('setup');

export function SetupScreen() {
  return html`
    <${Router}>
      <${Route} default component=${Setup} />
      </${Router}>
  `;
}

export const PUBLIC_PATHS = ['/ui/welcome', '/ui/reset', '/ui/confirm-email', '/ui/signup/confirm'];
