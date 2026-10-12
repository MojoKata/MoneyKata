// The Traditional IRA account type (requirements §4.1): its fields, icon and help part.
/** @type {import('./index.js').AccountType} */
export default {
  type: 'ira',
  label: 'Traditional IRA',
  group: 'retirement',
  icon: 'retire',
  hint: 'Tax-deferred',
  investing: true,
  reconcilable: false,
  contributions: true,
};
