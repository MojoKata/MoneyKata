// The Brokerage account type (requirements §4.1): its fields, icon and help part.
/** @type {import('./index.js').AccountType} */
export default {
  type: 'brokerage',
  label: 'Brokerage',
  group: 'investing',
  icon: 'candles',
  hint: 'Stocks, ETFs, funds',
  investing: true,
  reconcilable: true,
  contributions: false,
};
