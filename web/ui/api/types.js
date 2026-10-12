// Generated from the API's OpenAPI document by `python -m moneykata.contract write`.
// Do not edit: web/check fails when this file differs from what the routes give.

/**
 * @typedef {Object} EmailChange
 * @property {string} email
 */

/**
 * @typedef {Object} GroupChange
 * @property {(string | null)} [name]
 * @property {(boolean | null)} [active]
 * @property {(Array<string> | null)} [memberIds]
 */

/**
 * @typedef {Object} GroupRow
 * @property {string} id
 * @property {string} name
 * @property {boolean} active
 * @property {(string | null)} builtIn
 * @property {Array<string>} memberIds
 * @property {string} createdAt
 * @property {number} version
 */

/**
 * @typedef {Object} HTTPValidationError
 * @property {Array<ValidationError>} [detail]
 */

/**
 * @typedef {Object} Household
 * @property {string} name
 * @property {Object<string, unknown>} avatar
 */

/**
 * @typedef {Object} InvitationInfo
 * @property {string} username
 * @property {string} displayName
 * @property {string} household
 */

/**
 * @typedef {Object} Login
 * @property {string} login
 */

/**
 * @typedef {Object} Me
 * @property {string} id
 * @property {string} username
 * @property {string} displayName
 * @property {(string | null)} email
 * @property {(string | null)} avatar
 * @property {boolean} admin
 * @property {boolean} needsSetup
 * @property {string} timeZone
 * @property {string} zone
 * @property {string} theme
 */

/**
 * @typedef {Object} NewGroup
 * @property {string} name
 * @property {Array<string>} [memberIds]
 */

/**
 * @typedef {Object} NewUser
 * @property {string} displayName
 * @property {string} username
 * @property {string} email
 * @property {Array<string>} [groupIds]
 */

/**
 * @typedef {Object} Password
 * @property {string} password
 */

/**
 * @typedef {Object} PasswordChange
 * @property {string} currentPassword
 * @property {string} newPassword
 */

/**
 * @typedef {Object} Person
 * @property {string} id
 * @property {string} displayName
 */

/**
 * @typedef {Object} Profile
 * @property {string} id
 * @property {string} username
 * @property {string} displayName
 * @property {(string | null)} email
 * @property {(string | null)} pendingEmail
 * @property {(string | null)} avatar
 * @property {string} timeZone
 * @property {string} zone
 * @property {string} theme
 * @property {(number | null)} birthYear
 * @property {(string | null)} spouseId
 * @property {string} alertEmails
 * @property {Array<Person>} people
 * @property {number} version
 */

/**
 * @typedef {Object} ProfileChange
 * @property {(string | null)} [displayName]
 * @property {(string | null)} [avatar]
 * @property {(string | null)} [timeZone]
 * @property {(string | null)} [theme]
 * @property {(number | null)} [birthYear]
 * @property {(string | null)} [spouseId]
 * @property {(string | null)} [alertEmails]
 */

/**
 * @typedef {Object} SessionInfo
 * @property {Me} user
 * @property {Household} household
 * @property {string} version
 * @property {boolean} dev
 * @property {string} serverName
 */

/**
 * @typedef {Object} SettingsView
 * @property {Object<string, unknown>} values
 * @property {Object<string, Array<string>>} sections
 * @property {string} serverZone
 * @property {Object<string, number>} versions
 */

/**
 * @typedef {Object} Setup
 * @property {string} password
 * @property {string} email
 * @property {(string | null)} [displayName]
 */

/**
 * @typedef {Object} SignIn
 * @property {string} login
 * @property {string} password
 */

/**
 * @typedef {Object} Token
 * @property {string} token
 */

/**
 * @typedef {Object} TokenPassword
 * @property {string} token
 * @property {string} password
 */

/**
 * @typedef {Object} UserChange
 * @property {(string | null)} [displayName]
 * @property {(string | null)} [email]
 * @property {(boolean | null)} [active]
 * @property {(Array<string> | null)} [groupIds]
 */

/**
 * @typedef {Object} UserRow
 * @property {string} id
 * @property {string} username
 * @property {string} displayName
 * @property {(string | null)} email
 * @property {(string | null)} avatar
 * @property {boolean} active
 * @property {boolean} admin
 * @property {boolean} invited
 * @property {Array<string>} groupIds
 * @property {(string | null)} lastSignInAt
 * @property {(string | null)} reactivationAskedAt
 * @property {string} createdAt
 * @property {number} version
 */

/**
 * @typedef {Object} ValidationError
 * @property {Array<(string | number)>} loc
 * @property {string} msg
 * @property {string} type
 * @property {unknown} [input]
 * @property {Object<string, unknown>} [ctx]
 */

/**
 * @typedef {Object} Zones
 * @property {string} server
 * @property {Array<string>} zones
 */

export {};
