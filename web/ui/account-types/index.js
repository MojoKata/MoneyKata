// Every account type this release has, in the New account dialog's order (requirements §4.1).
// One module per type holds its label, group, icon and which tabs and fields it has; its help
// part is guides/account-<type>.md.
import t0 from './checking.js';
import t1 from './savings.js';
import t2 from './money-market.js';
import t3 from './cd.js';
import t4 from './credit-card.js';
import t5 from './brokerage.js';
import t6 from './ira.js';
import t7 from './roth-ira.js';
import t8 from './401k.js';
import t9 from './403b.js';
import t10 from './457b.js';
import t11 from './hsa.js';

/**
 * @typedef {Object} AccountType
 * @property {string} type
 * @property {string} label
 * @property {string} group
 * @property {string} icon
 * @property {string} hint
 * @property {boolean} investing  has Holdings, a lot method and trades
 * @property {boolean} reconcilable  has a Reconcile tab
 * @property {boolean} contributions  records contribution years and sources
 */

/** @type {AccountType[]} */
export const TYPES = [t0, t1, t2, t3, t4, t5, t6, t7, t8, t9, t10, t11];

/** @type {Record<string, AccountType>} */
export const BY_TYPE = Object.fromEntries(TYPES.map((t) => [t.type, t]));
