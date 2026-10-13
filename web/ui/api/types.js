// Generated from the API's OpenAPI document by `python -m moneykata.contract write`.
// Do not edit: web/check fails when this file differs from what the routes give.

/**
 * @typedef {Object} AccountChange
 * @property {(string | null)} [name]
 * @property {(string | null)} [institution]
 * @property {(string | null)} [mask]
 * @property {(string | null)} [notes]
 * @property {(Array<string> | null)} [keptBy]
 * @property {(string | null)} [lotMethod]
 * @property {((number | string) | null)} [openingBalance]
 * @property {(string | null)} [openingDate]
 * @property {(boolean | null)} [countInNetWorth]
 * @property {(boolean | null)} [active]
 */

/**
 * @typedef {Object} AccountDetail
 * @property {string} id
 * @property {string} name
 * @property {string} type
 * @property {string} typeLabel
 * @property {string} group
 * @property {(string | null)} institution
 * @property {(string | null)} mask
 * @property {boolean} active
 * @property {string} ownerId
 * @property {string} ownerName
 * @property {("owner" | "write" | "read")} level
 * @property {number} sharedWith
 * @property {(string | null)} ownerAvatar
 * @property {boolean} counted
 * @property {string} balance
 * @property {(string | null)} change
 * @property {(string | null)} lastUpdated
 * @property {boolean} needsAnchor
 * @property {boolean} mismatch
 * @property {boolean} countInNetWorth
 * @property {boolean} investing
 * @property {boolean} reconcilable
 * @property {number} version
 * @property {(string | null)} notes
 * @property {Array<string>} keptBy
 * @property {string} lotMethod
 * @property {(string | null)} openingBalance
 * @property {(string | null)} openingDate
 * @property {string} openingWorkedOut
 * @property {boolean} openingStandIn
 * @property {(string | null)} tax
 */

/**
 * @typedef {Object} AccountName
 * @property {string} id
 * @property {string} name
 * @property {boolean} yours
 */

/**
 * @typedef {Object} AccountRow
 * @property {string} id
 * @property {string} name
 * @property {string} type
 * @property {string} typeLabel
 * @property {string} group
 * @property {(string | null)} institution
 * @property {(string | null)} mask
 * @property {boolean} active
 * @property {string} ownerId
 * @property {string} ownerName
 * @property {("owner" | "write" | "read")} level
 * @property {number} sharedWith
 * @property {(string | null)} ownerAvatar
 * @property {boolean} counted
 * @property {string} balance
 * @property {(string | null)} change
 * @property {(string | null)} lastUpdated
 * @property {boolean} needsAnchor
 * @property {boolean} mismatch
 * @property {boolean} countInNetWorth
 * @property {boolean} investing
 * @property {boolean} reconcilable
 * @property {number} version
 */

/**
 * @typedef {Object} ActivityItem
 * @property {string} id
 * @property {string} at
 * @property {string} kind
 * @property {(string | null)} actorId
 * @property {(string | null)} actorName
 * @property {(string | null)} actorAvatar
 * @property {(string | null)} via
 * @property {(string | null)} subjectKind
 * @property {(string | null)} subjectId
 * @property {string} text
 */

/**
 * @typedef {Object} AlertList
 * @property {Array<AlertRow>} open
 * @property {Array<AlertRow>} resolved
 * @property {string} emails
 */

/**
 * @typedef {Object} AlertRow
 * @property {string} id
 * @property {string} kind
 * @property {string} title
 * @property {string} about
 * @property {(string | null)} link
 * @property {(string | null)} fix
 * @property {string} icon
 * @property {string} openedAt
 * @property {(string | null)} resolvedAt
 * @property {(string | null)} resolution
 * @property {boolean} forAdmins
 * @property {boolean} seen
 */

/**
 * @typedef {Object} Approval
 * @property {Array<string>} [groupIds]
 */

/**
 * @typedef {Object} Attention
 * @property {string} kind
 * @property {number} count
 * @property {string} text
 * @property {string} link
 */

/**
 * @typedef {Object} BackupOut
 * @property {string} name
 * @property {string} made
 * @property {number} bytes
 * @property {number} files
 * @property {string} masterKey
 */

/**
 * @typedef {Object} Backups
 * @property {string} directory
 * @property {string} time
 * @property {number} copies
 * @property {Array<BackupOut>} backups
 * @property {(string | null)} lastRun
 * @property {(string | null)} lastError
 * @property {(string | null)} nextRun
 * @property {boolean} running
 */

/**
 * @typedef {Object} Body_upload_ui_api_accounts__account_id__imports_post
 * @property {string} file
 */

/**
 * @typedef {Object} Categorise
 * @property {Array<string>} ids
 * @property {(string | null)} categoryId
 */

/**
 * @typedef {Object} CategoryOut
 * @property {string} id
 * @property {string} name
 * @property {string} kind
 * @property {(string | null)} parentId
 * @property {(string | null)} taxTag
 * @property {string} path
 */

/**
 * @typedef {Object} Change
 * @property {(string | null)} day
 * @property {(string | null)} month
 * @property {(string | null)} year
 */

/**
 * @typedef {Object} CheckOut
 * @property {string} name
 * @property {boolean} ok
 * @property {string} detail
 */

/**
 * @typedef {Object} CheckRow
 * @property {string} date
 * @property {string} reported
 * @property {string} computed
 * @property {string} difference
 * @property {string} source
 * @property {boolean} ok
 * @property {(string | null)} windowFrom
 * @property {(Suspects | null)} suspects
 */

/**
 * @typedef {Object} Close
 * @property {string} date
 * @property {string} close
 * @property {string} source
 */

/**
 * @typedef {Object} Confirmation
 * @property {string} at
 * @property {string} fingerprint
 * @property {boolean} matched
 */

/**
 * @typedef {Object} Counted
 * @property {boolean} counted
 */

/**
 * @typedef {Object} Dashboard
 * @property {string} netWorth
 * @property {Change} change
 * @property {string} investments
 * @property {(string | null)} investmentsDay
 * @property {string} cash
 * @property {number} cashAccounts
 * @property {(string | null)} lastUpdated
 * @property {Array<GroupTotal>} groups
 * @property {Array<Attention>} attention
 */

/**
 * @typedef {Object} Done
 * @property {number} changed
 */

/**
 * @typedef {Object} EmailChange
 * @property {string} email
 */

/**
 * @typedef {Object} EmailPassword
 * @property {(string | null)} password
 */

/**
 * @typedef {Object} EmailView
 * @property {(moneykata__ui__settings__SecretSet | null)} password
 * @property {number} waiting
 * @property {number} setAside
 * @property {(string | null)} lastRun
 * @property {(string | null)} lastError
 */

/**
 * @typedef {Object} GroupChange
 * @property {(string | null)} [name]
 * @property {(boolean | null)} [active]
 * @property {(Array<string> | null)} [memberIds]
 */

/**
 * @typedef {Object} GroupGrant
 * @property {string} id
 * @property {string} name
 * @property {string} level
 * @property {number} members
 */

/**
 * @typedef {Object} GroupPoint
 * @property {string} date
 * @property {string} total
 * @property {Object<string, string>} groups
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
 * @typedef {Object} GroupTotal
 * @property {string} group
 * @property {string} total
 * @property {Array<string>} accounts
 * @property {boolean} inNetWorth
 */

/**
 * @typedef {Object} HTTPValidationError
 * @property {Array<ValidationError>} [detail]
 */

/**
 * @typedef {Object} HoldingRow
 * @property {string} instrumentId
 * @property {string} symbol
 * @property {(string | null)} name
 * @property {string} instrumentClass
 * @property {string} quantity
 * @property {(string | null)} costBasis
 * @property {(string | null)} price
 * @property {(string | null)} priceAsOf
 * @property {(string | null)} priceSource
 * @property {(string | null)} value
 * @property {(string | null)} gain
 * @property {Array<LotRow>} lots
 */

/**
 * @typedef {Object} HoldingTotal
 * @property {string} instrumentId
 * @property {string} symbol
 * @property {(string | null)} name
 * @property {string} instrumentClass
 * @property {string} quantity
 * @property {(string | null)} price
 * @property {(string | null)} priceAsOf
 * @property {(string | null)} priceSource
 * @property {boolean} stale
 * @property {(string | null)} value
 * @property {(string | null)} costBasis
 * @property {(string | null)} gain
 * @property {(string | null)} weight
 * @property {Array<string>} accounts
 */

/**
 * @typedef {Object} Holdings
 * @property {string} cash
 * @property {string} total
 * @property {Array<HoldingRow>} holdings
 * @property {Array<Object<string, unknown>>} problems
 */

/**
 * @typedef {Object} Household
 * @property {string} name
 * @property {Object<string, unknown>} avatar
 */

/**
 * @typedef {Object} ImportRow
 * @property {string} id
 * @property {string} format
 * @property {string} fileName
 * @property {(string | null)} coveredFrom
 * @property {(string | null)} coveredTo
 * @property {number} added
 * @property {number} matched
 * @property {number} changed
 * @property {string} userName
 * @property {string} createdAt
 */

/**
 * @typedef {Object} InstrumentOut
 * @property {string} id
 * @property {string} symbol
 * @property {(string | null)} name
 * @property {string} instrumentClass
 */

/**
 * @typedef {Object} InvitationInfo
 * @property {string} username
 * @property {string} displayName
 * @property {string} household
 */

/**
 * @typedef {Object} JobOut
 * @property {string} id
 * @property {string} kind
 * @property {string} state
 * @property {number} progress
 * @property {(Object<string, unknown> | null)} result
 * @property {(Object<string, unknown> | null)} error
 */

/**
 * @typedef {Object} KeyStorage
 * @property {string} keyFile
 * @property {string} fingerprint
 * @property {string} created
 * @property {number} ageDays
 * @property {number} reminderMonths
 * @property {boolean} reminderDue
 * @property {string} dataKeyCreated
 * @property {Array<PreviousKeyOut>} previous
 * @property {Array<Confirmation>} confirmations
 * @property {number} databaseBytes
 * @property {number} secrets
 * @property {number} receipts
 * @property {boolean} reencrypting
 */

/**
 * @typedef {Object} KeyTest
 * @property {boolean} ok
 * @property {Array<CheckOut>} checks
 */

/**
 * @typedef {Object} Login
 * @property {string} login
 */

/**
 * @typedef {Object} LotRow
 * @property {(string | null)} lotId
 * @property {string} acquiredOn
 * @property {string} quantity
 * @property {(string | null)} basis
 * @property {boolean} basisMissing
 * @property {boolean} standIn
 * @property {boolean} longTerm
 */

/**
 * @typedef {Object} MappingIn
 * @property {Object<string, unknown>} mapping
 * @property {boolean} [save]
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
 * @typedef {Object} NetWorthSeries
 * @property {Array<GroupPoint>} points
 * @property {Array<string>} groups
 */

/**
 * @typedef {Object} NewAccount
 * @property {string} name
 * @property {string} type
 * @property {(string | null)} [institution]
 * @property {(string | null)} [mask]
 * @property {(string | null)} [notes]
 * @property {Array<string>} [keptBy]
 * @property {string} [lotMethod]
 * @property {((number | string) | null)} [openingBalance]
 * @property {(string | null)} [openingDate]
 * @property {boolean} [countInNetWorth]
 */

/**
 * @typedef {Object} NewAdjustment
 * @property {string} date
 * @property {(number | string)} amount
 * @property {string} note
 */

/**
 * @typedef {Object} NewAnchor
 * @property {string} date
 * @property {(number | string)} balance
 * @property {(string | null)} [note]
 */

/**
 * @typedef {Object} NewCategory
 * @property {string} name
 * @property {string} kind
 * @property {(string | null)} [parentId]
 * @property {(string | null)} [taxTag]
 */

/**
 * @typedef {Object} NewGroup
 * @property {string} name
 * @property {Array<string>} [memberIds]
 */

/**
 * @typedef {Object} NewPortfolio
 * @property {string} name
 * @property {Array<string>} [accountIds]
 * @property {string} [benchmark]
 * @property {(string | null)} [notes]
 */

/**
 * @typedef {Object} NewReconciliation
 * @property {string} statementDate
 * @property {(number | string)} statementBalance
 */

/**
 * @typedef {Object} NewSource
 * @property {string} name
 */

/**
 * @typedef {Object} NewUser
 * @property {string} displayName
 * @property {string} username
 * @property {string} email
 * @property {Array<string>} [groupIds]
 */

/**
 * @typedef {Object} Newer
 * @property {number} count
 */

/**
 * @typedef {Object} Page_ActivityItem_
 * @property {Array<ActivityItem>} items
 * @property {(string | null)} next
 */

/**
 * @typedef {Object} Page_TxnOut_
 * @property {Array<TxnOut>} items
 * @property {(string | null)} next
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
 * @typedef {Object} PeriodRow
 * @property {string} start
 * @property {string} end
 * @property {Array<string>} importIds
 */

/**
 * @typedef {Object} Person
 * @property {string} id
 * @property {string} displayName
 */

/**
 * @typedef {Object} PickIn
 * @property {string} lotId
 * @property {(number | string)} quantity
 */

/**
 * @typedef {Object} Point
 * @property {string} date
 * @property {string} value
 */

/**
 * @typedef {Object} PortfolioChange
 * @property {(string | null)} [name]
 * @property {(Array<string> | null)} [accountIds]
 * @property {(string | null)} [benchmark]
 * @property {(string | null)} [notes]
 */

/**
 * @typedef {Object} PortfolioHoldings
 * @property {Array<HoldingTotal>} holdings
 * @property {string} cash
 * @property {string} total
 */

/**
 * @typedef {Object} PortfolioRow
 * @property {string} id
 * @property {string} name
 * @property {boolean} implicit
 * @property {string} ownerId
 * @property {string} ownerName
 * @property {(string | null)} ownerAvatar
 * @property {string} level
 * @property {string} benchmark
 * @property {Array<string>} accountIds
 * @property {string} value
 * @property {number} sharedWith
 * @property {(string | null)} notes
 * @property {number} version
 */

/**
 * @typedef {Object} PortfolioSeries
 * @property {Array<SeriesPoint>} points
 * @property {string} benchmark
 * @property {(string | null)} twr
 * @property {(string | null)} irr
 * @property {string} contributed
 * @property {string} growth
 * @property {string} start
 * @property {string} end
 */

/**
 * @typedef {Object} PreviousKeyOut
 * @property {string} fingerprint
 * @property {string} path
 * @property {(string | null)} removableAfter
 */

/**
 * @typedef {Object} PriceStatus
 * @property {(string | null)} lastRefresh
 * @property {boolean} stale
 * @property {number} sources
 * @property {boolean} running
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
 * @property {TwoStep} twoStep
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
 * @typedef {Object} ReconcileView
 * @property {Array<PeriodRow>} periods
 * @property {Array<Array<string>>} gaps
 * @property {Array<Array<string>>} overlaps
 * @property {Array<CheckRow>} checks
 * @property {boolean} needsAnchor
 * @property {boolean} openingStandIn
 * @property {Array<ReconciliationRow>} reconciliations
 */

/**
 * @typedef {Object} ReconciliationChange
 * @property {boolean} finish
 */

/**
 * @typedef {Object} ReconciliationRow
 * @property {string} id
 * @property {string} statementDate
 * @property {string} statementBalance
 * @property {string} cleared
 * @property {string} difference
 * @property {(string | null)} finishedAt
 * @property {number} version
 */

/**
 * Shown once: only their hashes are kept.
 * @typedef {Object} RecoveryCodes
 * @property {Array<string>} codes
 */

/**
 * @typedef {Object} ReturnRow
 * @property {string} id
 * @property {string} name
 * @property {Object<string, (string | null)>} periods
 */

/**
 * @typedef {Object} Saved
 * @property {ShareView} view
 * @property {number} alsoShared
 */

/**
 * @typedef {Object} Series
 * @property {Array<Point>} points
 * @property {string} asOf
 */

/**
 * @typedef {Object} SeriesPoint
 * @property {string} date
 * @property {string} value
 * @property {string} contributions
 * @property {(string | null)} benchmark
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
 * @typedef {Object} ShareSave
 * @property {Object<string, string>} [users]
 * @property {Object<string, string>} [groups]
 * @property {boolean} [shareAccountsToo]
 */

/**
 * @typedef {Object} ShareView
 * @property {string} kind
 * @property {string} itemId
 * @property {string} itemName
 * @property {Array<UserGrant>} users
 * @property {Array<GroupGrant>} groups
 * @property {Object<string, Array<string>>} hidden
 * @property {Array<AccountName>} accounts
 */

/**
 * @typedef {Object} SignIn
 * @property {string} login
 * @property {string} password
 */

/**
 * @typedef {Object} SignupConfirmed
 * @property {string} displayName
 * @property {string} household
 */

/**
 * @typedef {Object} SignupForm
 * @property {string} displayName
 * @property {string} username
 * @property {string} email
 * @property {string} password
 */

/**
 * Whether the sign-in screen offers Sign up, and to which email domains.
 * @typedef {Object} SignupOpen
 * @property {boolean} open
 * @property {Array<string>} domains
 */

/**
 * @typedef {Object} SignupRow
 * @property {string} id
 * @property {string} displayName
 * @property {string} username
 * @property {string} email
 * @property {(string | null)} confirmedAt
 */

/**
 * @typedef {Object} SourceChange
 * @property {(boolean | null)} [enabled]
 * @property {(Object<string, number> | null)} [preference]
 * @property {(string | null)} [apiKey]
 */

/**
 * @typedef {Object} SourceKind
 * @property {string} name
 * @property {string} label
 * @property {Array<string>} classes
 * @property {boolean} needsKey
 * @property {(string | null)} keyUrl
 * @property {string} terms
 * @property {(string | null)} termsChecked
 * @property {(string | null)} attribution
 * @property {boolean} fetches
 */

/**
 * @typedef {Object} SourceRow
 * @property {string} name
 * @property {string} label
 * @property {Array<string>} classes
 * @property {boolean} needsKey
 * @property {(string | null)} keyUrl
 * @property {string} terms
 * @property {(string | null)} termsChecked
 * @property {(string | null)} attribution
 * @property {boolean} fetches
 * @property {string} id
 * @property {boolean} enabled
 * @property {Object<string, number>} preference
 * @property {(moneykata__ui__prices__SecretSet | null)} key
 * @property {(string | null)} lastRunAt
 * @property {(string | null)} lastOkAt
 * @property {(string | null)} lastError
 * @property {number} version
 */

/**
 * @typedef {Object} SourcesView
 * @property {Array<SourceKind>} available
 * @property {Array<SourceRow>} sources
 * @property {string} refreshTime
 * @property {string} refreshZone
 */

/**
 * @typedef {Object} SplitIn
 * @property {(string | null)} [categoryId]
 * @property {(number | string)} amount
 * @property {(string | null)} [memo]
 */

/**
 * @typedef {Object} SplitOut
 * @property {(string | null)} [categoryId]
 * @property {string} amount
 * @property {(string | null)} [memo]
 * @property {string} id
 */

/**
 * @typedef {Object} Suspects
 * @property {Array<Array<string>>} duplicates
 * @property {Array<string>} changed
 * @property {Array<Array<string>>} gaps
 * @property {(string | null)} firstParting
 */

/**
 * @typedef {Object} TestEmail
 * @property {string} to
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
 * @typedef {Object} TransferLink
 * @property {(string | null)} otherId
 */

/**
 * @typedef {Object} TwoStep
 * @property {boolean} on
 * @property {(string | null)} since
 * @property {number} recoveryCodesLeft
 */

/**
 * @typedef {Object} TwoStepCode
 * @property {string} token
 * @property {string} code
 */

/**
 * @typedef {Object} TwoStepConfirm
 * @property {string} code
 */

/**
 * The password was right and two-step sign-in is on: the code comes next (S10.1.6).
 * @typedef {Object} TwoStepNeeded
 * @property {string} twoStepToken
 */

/**
 * What an authenticator app needs: the QR code, or the key typed by hand.
 * @typedef {Object} TwoStepSetup
 * @property {string} secret
 * @property {string} uri
 * @property {string} qrImage
 */

/**
 * @typedef {Object} TxnChange
 * @property {(string | null)} [date]
 * @property {(string | null)} [kind]
 * @property {((number | string) | null)} [amount]
 * @property {(string | null)} [payee]
 * @property {(string | null)} [memo]
 * @property {(string | null)} [categoryId]
 * @property {((number | string) | null)} [quantity]
 * @property {((number | string) | null)} [price]
 * @property {((number | string) | null)} [fees]
 * @property {(string | null)} [dividendType]
 * @property {(number | null)} [contributionYear]
 * @property {(string | null)} [contributionSource]
 * @property {((number | string) | null)} [costBasis]
 * @property {(boolean | null)} [cleared]
 * @property {(Array<SplitIn> | null)} [splits]
 * @property {(Array<string> | null)} [tags]
 */

/**
 * @typedef {Object} TxnIn
 * @property {string} accountId
 * @property {string} date
 * @property {string} [kind]
 * @property {(number | string)} amount
 * @property {(string | null)} [payee]
 * @property {(string | null)} [memo]
 * @property {(string | null)} [categoryId]
 * @property {(string | null)} [instrumentId]
 * @property {(string | null)} [symbol]
 * @property {((number | string) | null)} [quantity]
 * @property {((number | string) | null)} [price]
 * @property {((number | string) | null)} [fees]
 * @property {(string | null)} [dividendType]
 * @property {((number | string) | null)} [splitRatio]
 * @property {(number | null)} [contributionYear]
 * @property {(string | null)} [contributionSource]
 * @property {((number | string) | null)} [costBasis]
 * @property {Array<SplitIn>} [splits]
 * @property {Array<string>} [tags]
 * @property {Array<PickIn>} [picks]
 */

/**
 * @typedef {Object} TxnOut
 * @property {string} id
 * @property {string} accountId
 * @property {string} accountName
 * @property {string} date
 * @property {string} kind
 * @property {string} amount
 * @property {(string | null)} payee
 * @property {(string | null)} payeeRaw
 * @property {(string | null)} memo
 * @property {(string | null)} categoryId
 * @property {(string | null)} instrumentId
 * @property {(string | null)} symbol
 * @property {(string | null)} quantity
 * @property {(string | null)} price
 * @property {(string | null)} fees
 * @property {(string | null)} dividendType
 * @property {(number | null)} contributionYear
 * @property {(string | null)} contributionSource
 * @property {(string | null)} transferId
 * @property {(string | null)} transferAccountName
 * @property {boolean} imported
 * @property {boolean} cleared
 * @property {boolean} reconciled
 * @property {(string | null)} amountWas
 * @property {Array<SplitOut>} splits
 * @property {Array<string>} tags
 * @property {string} level
 * @property {number} version
 */

/**
 * @typedef {Object} TypedPrice
 * @property {string} date
 * @property {(number | string)} price
 */

/**
 * @typedef {Object} UserChange
 * @property {(string | null)} [displayName]
 * @property {(string | null)} [email]
 * @property {(boolean | null)} [active]
 * @property {(Array<string> | null)} [groupIds]
 */

/**
 * @typedef {Object} UserGrant
 * @property {string} id
 * @property {string} displayName
 * @property {(string | null)} avatar
 * @property {string} level
 * @property {Array<Via>} via
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
 * @property {boolean} twoStep
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
 * @typedef {Object} Via
 * @property {string} groupId
 * @property {string} groupName
 * @property {string} level
 */

/**
 * @typedef {Object} Zones
 * @property {string} server
 * @property {Array<string>} zones
 */

/**
 * @typedef {Object} moneykata__ui__prices__SecretSet
 * @property {string} setAt
 * @property {(string | null)} setBy
 */

/**
 * A stored secret as the UI shows it: set, when and by whom.
 * @typedef {Object} moneykata__ui__settings__SecretSet
 * @property {string} setAt
 * @property {(string | null)} setBy
 */

export {};
