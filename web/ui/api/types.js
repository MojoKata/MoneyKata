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
 * @property {(import('../app/dec.js').Dec | null)} [openingBalance]
 * @property {(string | null)} [openingDate]
 * @property {(boolean | null)} [countInNetWorth]
 * @property {(boolean | null)} [active]
 * @property {(string | null)} [statementInterval]
 * @property {boolean} [dismissIntervalProposal]
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
 * @property {import('../app/dec.js').Dec} balance
 * @property {(import('../app/dec.js').Dec | null)} change
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
 * @property {(import('../app/dec.js').Dec | null)} openingBalance
 * @property {(string | null)} openingDate
 * @property {import('../app/dec.js').Dec} openingWorkedOut
 * @property {boolean} openingStandIn
 * @property {(string | null)} tax
 * @property {(string | null)} statementInterval
 * @property {string} statementIntervalDefault
 * @property {(string | null)} statementIntervalProposal
 */

/**
 * @typedef {Object} AccountName
 * @property {string} id
 * @property {string} name
 * @property {boolean} yours
 */

/**
 * @typedef {Object} AccountRef
 * @property {string} id
 * @property {string} name
 * @property {string} type
 * @property {string} ownerName
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
 * @property {import('../app/dec.js').Dec} balance
 * @property {(import('../app/dec.js').Dec | null)} change
 * @property {(string | null)} lastUpdated
 * @property {boolean} needsAnchor
 * @property {boolean} mismatch
 * @property {boolean} countInNetWorth
 * @property {boolean} investing
 * @property {boolean} reconcilable
 * @property {number} version
 */

/**
 * @typedef {Object} Activated
 * @property {(string | null)} replaced
 */

/**
 * @typedef {Object} ActivityIn
 * @property {string} date
 * @property {string} description
 * @property {import('../app/dec.js').Dec} amount
 * @property {string} kind
 * @property {boolean} [include]
 * @property {(string | null)} [symbol]
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
 * @typedef {Object} Amount
 * @property {string} label
 * @property {import('../app/dec.js').Dec} amount
 */

/**
 * @typedef {Object} Approval
 * @property {Array<string>} [groupIds]
 */

/**
 * @typedef {Object} Asked
 * @property {boolean} asked
 */

/**
 * @typedef {Object} AssumptionsView
 * @property {Object<string, unknown>} figures
 * @property {Array<Array<unknown>>} classes
 * @property {Array<Array<unknown>>} bitcoinModels
 * @property {number} [version]
 */

/**
 * @typedef {Object} Attach
 * @property {string} transactionId
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
 * @typedef {Object} BeneficiaryOut
 * @property {string} kind
 * @property {string} id
 * @property {string} name
 * @property {(number | null)} birthYear
 * @property {boolean} [deleted]
 */

/**
 * @typedef {Object} BeneficiaryRef
 * @property {string} kind
 * @property {string} id
 */

/**
 * @typedef {Object} BitcoinPassword
 * @property {(string | null)} password
 */

/**
 * @typedef {Object} BitcoinTest
 * @property {string} answer
 */

/**
 * @typedef {Object} BitcoinView
 * @property {(moneykata__ui__settings__SecretSet | null)} password
 * @property {number} wallets
 * @property {(string | null)} lastRun
 * @property {(string | null)} lastError
 */

/**
 * @typedef {Object} Body_keep_upload_ui_api_accounts__account_id__statements_keep_post
 * @property {string} file
 */

/**
 * @typedef {Object} Body_upload_ui_api_accounts__account_id__imports_post
 * @property {string} file
 */

/**
 * @typedef {Object} Body_upload_ui_api_receipts_post
 * @property {string} file
 */

/**
 * @typedef {Object} BookDetail
 * @property {string} id
 * @property {number} year
 * @property {Array<Filer>} filers
 * @property {string} level
 * @property {string} label
 * @property {number} version
 * @property {Array<DependentOut>} dependents
 * @property {Array<Form8615Out>} form8615
 * @property {Array<string>} claimedElsewhere
 * @property {Array<AccountRef>} accounts
 * @property {Array<AccountRef>} leftOut
 * @property {Array<AccountRef>} addable
 * @property {Array<FilingOut>} filings
 * @property {Array<ExpectedOut>} expected
 * @property {Array<DocumentOut>} received
 * @property {Array<LastYear>} lastYear
 * @property {string} federalDue
 * @property {boolean} canWrite
 */

/**
 * @typedef {Object} BookRow
 * @property {string} id
 * @property {number} year
 * @property {Array<Filer>} filers
 * @property {string} level
 * @property {string} label
 * @property {number} version
 */

/**
 * @typedef {Object} BoxTotal
 * @property {string} box
 * @property {import('../app/dec.js').Dec} proceeds
 * @property {import('../app/dec.js').Dec} basis
 * @property {import('../app/dec.js').Dec} adjustment
 * @property {import('../app/dec.js').Dec} gain
 */

/**
 * @typedef {Object} BrokerageIn
 * @property {string} periodStart
 * @property {string} periodEnd
 * @property {(import('../app/dec.js').Dec | null)} [endingValue]
 * @property {Array<PositionIn>} [positions]
 * @property {Array<ActivityIn>} [rows]
 */

/**
 * @typedef {Object} BudgetChange
 * @property {(string | null)} [name]
 * @property {(Array<string> | null)} [accountIds]
 */

/**
 * @typedef {Object} BudgetRow
 * @property {string} id
 * @property {string} name
 * @property {string} ownerId
 * @property {string} ownerName
 * @property {string} level
 * @property {Array<string>} accountIds
 * @property {number} sharedWith
 * @property {number} version
 */

/**
 * @typedef {Object} Candidate
 * @property {string} transactionId
 * @property {string} accountName
 * @property {string} date
 * @property {import('../app/dec.js').Dec} amount
 * @property {(string | null)} payee
 */

/**
 * @typedef {Object} CandidateOut
 * @property {string} personId
 * @property {string} name
 * @property {(string | null)} relation
 * @property {(number | null)} age
 * @property {string} suggest
 * @property {string} suggestIfStudent
 */

/**
 * @typedef {Object} Carried
 * @property {(import('../app/dec.js').Dec | null)} [agi]
 * @property {(import('../app/dec.js').Dec | null)} [totalTax]
 * @property {(import('../app/dec.js').Dec | null)} [overpaymentApplied]
 * @property {(import('../app/dec.js').Dec | null)} [capitalLossShort]
 * @property {(import('../app/dec.js').Dec | null)} [capitalLossLong]
 * @property {(import('../app/dec.js').Dec | null)} [basis8606]
 * @property {(import('../app/dec.js').Dec | null)} [charitableCarryover]
 */

/**
 * @typedef {Object} CarriedView
 * @property {(import('../app/dec.js').Dec | null)} [agi]
 * @property {(import('../app/dec.js').Dec | null)} [totalTax]
 * @property {(import('../app/dec.js').Dec | null)} [overpaymentApplied]
 * @property {(import('../app/dec.js').Dec | null)} [capitalLossShort]
 * @property {(import('../app/dec.js').Dec | null)} [capitalLossLong]
 * @property {(import('../app/dec.js').Dec | null)} [basis8606]
 * @property {(import('../app/dec.js').Dec | null)} [charitableCarryover]
 */

/**
 * @typedef {Object} CashFlow
 * @property {string} month
 * @property {Array<Flow>} sources
 * @property {Array<Flow>} uses
 * @property {import('../app/dec.js').Dec} income
 * @property {import('../app/dec.js').Dec} spending
 */

/**
 * @typedef {Object} Categorise
 * @property {Array<string>} ids
 * @property {(string | null)} categoryId
 */

/**
 * @typedef {Object} CategoryChange
 * @property {(number | null)} [keepReceiptsYears]
 */

/**
 * @typedef {Object} CategoryOut
 * @property {string} id
 * @property {string} name
 * @property {string} kind
 * @property {(string | null)} parentId
 * @property {(string | null)} taxTag
 * @property {string} path
 * @property {(number | null)} keepReceiptsYears
 * @property {number} version
 */

/**
 * @typedef {Object} CategorySize
 * @property {number} files
 * @property {number} bytes
 * @property {string} category
 */

/**
 * @typedef {Object} Change
 * @property {(import('../app/dec.js').Dec | null)} day
 * @property {(import('../app/dec.js').Dec | null)} month
 * @property {(import('../app/dec.js').Dec | null)} year
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
 * @property {import('../app/dec.js').Dec} reported
 * @property {import('../app/dec.js').Dec} computed
 * @property {import('../app/dec.js').Dec} difference
 * @property {string} source
 * @property {boolean} ok
 * @property {(string | null)} windowFrom
 * @property {(Suspects | null)} suspects
 */

/**
 * @typedef {Object} Close
 * @property {string} date
 * @property {import('../app/dec.js').Dec} close
 * @property {string} source
 */

/**
 * @typedef {Object} ClosedRow
 * @property {(string | null)} saleId
 * @property {string} accountId
 * @property {string} accountName
 * @property {string} instrumentId
 * @property {string} symbol
 * @property {string} instrumentClass
 * @property {string} side
 * @property {import('../app/dec.js').Dec} quantity
 * @property {string} opened
 * @property {string} closed
 * @property {string} how
 * @property {import('../app/dec.js').Dec} proceeds
 * @property {(import('../app/dec.js').Dec | null)} cost
 * @property {(import('../app/dec.js').Dec | null)} realized
 * @property {import('../app/dec.js').Dec} washDisallowed
 * @property {string} term
 */

/**
 * @typedef {Object} Colour
 * @property {string} colour
 */

/**
 * @typedef {Object} Confirmation
 * @property {string} at
 * @property {string} fingerprint
 * @property {boolean} matched
 */

/**
 * @typedef {Object} ContributionIn
 * @property {string} date
 * @property {import('../app/dec.js').Dec} amount
 * @property {string} [contributor]
 * @property {boolean} [fiveYear]
 * @property {(string | null)} [fromAccountId]
 */

/**
 * @typedef {Object} ContributionsView
 * @property {Array<moneykata__ui__education__ContributionOut>} rows
 * @property {Array<GiftYearOut>} years
 * @property {boolean} canWrite
 */

/**
 * The link's copy (S11.7): its access key, size, and whether it is unlocked.
 * @typedef {Object} CopyOut
 * @property {(string | null)} keyMadeAt
 * @property {(string | null)} keyMadeBy
 * @property {number} sizeBytes
 * @property {number} receipts
 * @property {number} items
 * @property {number} waiting
 * @property {boolean} unlocked
 * @property {(string | null)} unlockedBy
 * @property {(string | null)} unlockedAt
 * @property {(number | null)} locksInSeconds
 */

/**
 * @typedef {Object} CopyState
 * @property {moneykata__ui__linked__Household} household
 * @property {boolean} hasKey
 * @property {number} waiting
 * @property {(string | null)} pulledAt
 * @property {(string | null)} unlockedBy
 * @property {(string | null)} unlockedAt
 * @property {(number | null)} locksInSeconds
 */

/**
 * @typedef {Object} CountIn
 * @property {(boolean | null)} counted
 */

/**
 * @typedef {Object} Counted
 * @property {boolean} counted
 */

/**
 * @typedef {Object} Dashboard
 * @property {import('../app/dec.js').Dec} netWorth
 * @property {Change} change
 * @property {import('../app/dec.js').Dec} investments
 * @property {(import('../app/dec.js').Dec | null)} investmentsDay
 * @property {import('../app/dec.js').Dec} cash
 * @property {number} cashAccounts
 * @property {(string | null)} lastUpdated
 * @property {Array<GroupTotal>} groups
 * @property {Array<Attention>} attention
 */

/**
 * @typedef {Object} Deleted_BookDetail_
 * @property {Gone} deleted
 * @property {(BookDetail | null)} [parent]
 */

/**
 * @typedef {Object} Deleted_ItemDetail_
 * @property {Gone} deleted
 * @property {(ItemDetail | null)} [parent]
 */

/**
 * @typedef {Object} Deleted_NoneType_
 * @property {Gone} deleted
 * @property {null} [parent]
 */

/**
 * @typedef {Object} Deleted_Profile_
 * @property {Gone} deleted
 * @property {(Profile | null)} [parent]
 */

/**
 * @typedef {Object} Deleted_ReceiptDetail_
 * @property {Gone} deleted
 * @property {(ReceiptDetail | null)} [parent]
 */

/**
 * @typedef {Object} Deleted_UserRow_
 * @property {Gone} deleted
 * @property {(UserRow | null)} [parent]
 */

/**
 * @typedef {Object} Deleted_WithdrawalsView_
 * @property {Gone} deleted
 * @property {(WithdrawalsView | null)} [parent]
 */

/**
 * @typedef {Object} DependentAge
 * @property {string} name
 * @property {(string | null)} relation
 * @property {(number | null)} age
 * @property {boolean} under17
 * @property {boolean} under13
 * @property {Array<string>} agesOut
 */

/**
 * @typedef {Object} DependentIn
 * @property {string} personId
 * @property {string} [claimedAs]
 * @property {number} [months]
 * @property {boolean} [student]
 * @property {Array<string>} [accountIds]
 */

/**
 * @typedef {Object} DependentOut
 * @property {string} id
 * @property {string} personId
 * @property {string} name
 * @property {(string | null)} relation
 * @property {string} claimedAs
 * @property {number} months
 * @property {boolean} student
 * @property {(number | null)} age
 * @property {boolean} under17
 * @property {boolean} under13
 * @property {Array<string>} agesOut
 * @property {boolean} claimedElsewhere
 * @property {Array<string>} accountIds
 * @property {number} version
 */

/**
 * @typedef {Object} DocumentOut
 * @property {string} id
 * @property {string} direction
 * @property {string} form
 * @property {(string | null)} issuer
 * @property {(string | null)} accountId
 * @property {(string | null)} accountName
 * @property {(string | null)} filingId
 * @property {(string | null)} receiptId
 * @property {(string | null)} fileName
 * @property {(string | null)} notes
 * @property {number} version
 */

/**
 * @typedef {Object} DonationChange
 * @property {(boolean | null)} [acknowledged]
 * @property {(boolean | null)} [granted]
 * @property {(string | null)} [notes]
 * @property {(string | null)} [organisationId]
 */

/**
 * @typedef {Object} DonationIn
 * @property {string} date
 * @property {string} kind
 * @property {(string | null)} [organisationId]
 * @property {(import('../app/dec.js').Dec | null)} [amount]
 * @property {(string | null)} [description]
 * @property {(string | null)} [transactionId]
 * @property {(string | null)} [fromAccountId]
 * @property {(string | null)} [dafAccountId]
 * @property {(string | null)} [lotId]
 * @property {(import('../app/dec.js').Dec | null)} [quantity]
 * @property {boolean} [acknowledged]
 * @property {(boolean | null)} [granted]
 * @property {(string | null)} [notes]
 */

/**
 * @typedef {Object} DonationOut
 * @property {(string | null)} id
 * @property {string} date
 * @property {string} kind
 * @property {string} kindLabel
 * @property {string} name
 * @property {(string | null)} organisationId
 * @property {import('../app/dec.js').Dec} amount
 * @property {boolean} deductible
 * @property {boolean} counted
 * @property {boolean} needsAck
 * @property {boolean} acknowledged
 * @property {(string | null)} transactionId
 * @property {(string | null)} description
 * @property {(string | null)} symbol
 * @property {(import('../app/dec.js').Dec | null)} quantity
 * @property {(import('../app/dec.js').Dec | null)} basis
 * @property {(boolean | null)} longTerm
 * @property {(boolean | null)} granted
 * @property {(string | null)} notes
 * @property {boolean} canWrite
 * @property {(number | null)} version
 */

/**
 * @typedef {Object} DonationRow
 * @property {string} date
 * @property {string} name
 * @property {string} kindLabel
 * @property {import('../app/dec.js').Dec} amount
 * @property {boolean} deductible
 * @property {boolean} needsAck
 * @property {boolean} acknowledged
 */

/**
 * @typedef {Object} Done
 * @property {number} changed
 */

/**
 * @typedef {Object} EducationOut
 * @property {string} account
 * @property {string} beneficiary
 * @property {Array<Amount>} contributions
 * @property {(import('../app/dec.js').Dec | null)} stateDeduction
 * @property {import('../app/dec.js').Dec} distributions
 * @property {import('../app/dec.js').Dec} expenses
 * @property {import('../app/dec.js').Dec} notCovered
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
 * What the loan is secured by, and the borrower's stake in it (S1.9.5).
 * @typedef {Object} Equity
 * @property {string} itemId
 * @property {string} itemName
 * @property {string} accountId
 * @property {import('../app/dec.js').Dec} value
 * @property {import('../app/dec.js').Dec} owed
 * @property {import('../app/dec.js').Dec} equity
 * @property {import('../app/dec.js').Dec} ltv
 * @property {(string | null)} pmiRequest
 * @property {(string | null)} pmiEnds
 */

/**
 * @typedef {Object} ExpectedOut
 * @property {string} form
 * @property {(string | null)} issuer
 * @property {(string | null)} accountId
 * @property {string} why
 * @property {(DocumentOut | null)} document
 */

/**
 * @typedef {Object} ExpenseIn
 * @property {string} date
 * @property {(number | null)} [year]
 * @property {string} kind
 * @property {(string | null)} [description]
 * @property {import('../app/dec.js').Dec} amount
 */

/**
 * @typedef {Object} ExpenseOut
 * @property {string} id
 * @property {string} date
 * @property {number} year
 * @property {string} kind
 * @property {string} kindLabel
 * @property {(string | null)} description
 * @property {import('../app/dec.js').Dec} amount
 * @property {Array<ReceiptRow>} documents
 * @property {number} version
 */

/**
 * @typedef {Object} Expiring
 * @property {string} symbol
 * @property {number} days
 * @property {(boolean | null)} inTheMoney
 */

/**
 * @typedef {Object} Filer
 * @property {string} id
 * @property {string} name
 * @property {boolean} accepted
 */

/**
 * @typedef {Object} FilingIn
 * @property {string} [jurisdiction]
 * @property {(string | null)} [place]
 * @property {string} [form]
 * @property {(string | null)} [amendsId]
 * @property {(string | null)} [filingStatus]
 * @property {(string | null)} [preparedBy]
 * @property {(string | null)} [sentBy]
 * @property {string} [progress]
 * @property {(string | null)} [dueDate]
 * @property {(string | null)} [extensionFiledOn]
 * @property {(string | null)} [extendedDue]
 * @property {(string | null)} [filedOn]
 * @property {(string | null)} [confirmation]
 * @property {(string | null)} [resultKind]
 * @property {(import('../app/dec.js').Dec | null)} [resultAmount]
 * @property {(string | null)} [resultTransactionId]
 * @property {Array<Payment>} [payments]
 * @property {Carried} [carried]
 */

/**
 * @typedef {Object} FilingOut
 * @property {string} id
 * @property {string} jurisdiction
 * @property {(string | null)} place
 * @property {string} form
 * @property {string} label
 * @property {(string | null)} amendsId
 * @property {(string | null)} filingStatus
 * @property {(string | null)} preparedBy
 * @property {(string | null)} sentBy
 * @property {string} progress
 * @property {(string | null)} dueDate
 * @property {(string | null)} extensionFiledOn
 * @property {(string | null)} extendedDue
 * @property {(string | null)} filedOn
 * @property {(string | null)} confirmation
 * @property {(string | null)} resultKind
 * @property {(import('../app/dec.js').Dec | null)} resultAmount
 * @property {(string | null)} resultTransactionId
 * @property {(string | null)} resultPaid
 * @property {boolean} overdue
 * @property {Array<PaymentView>} payments
 * @property {CarriedView} carried
 * @property {Array<DocumentOut>} documents
 * @property {number} version
 */

/**
 * @typedef {Object} Flag
 * @property {PersonRef} person
 * @property {import('../app/dec.js').Dec} given
 * @property {import('../app/dec.js').Dec} exclusion
 */

/**
 * @typedef {Object} Flow
 * @property {string} name
 * @property {import('../app/dec.js').Dec} amount
 */

/**
 * @typedef {Object} FollowIn
 * @property {boolean} following
 */

/**
 * @typedef {Object} Following
 * @property {string} planId
 * @property {string} name
 * @property {string} since
 * @property {import('../app/dec.js').Dec} expected
 * @property {import('../app/dec.js').Dec} actual
 * @property {import('../app/dec.js').Dec} ahead
 */

/**
 * @typedef {Object} Form8615Out
 * @property {string} name
 * @property {import('../app/dec.js').Dec} unearned
 * @property {import('../app/dec.js').Dec} threshold
 * @property {Array<string>} accounts
 */

/**
 * @typedef {Object} Forms
 * @property {Array<string>} received
 * @property {Array<string>} filed
 * @property {Array<string>} statuses
 */

/**
 * @typedef {Object} FundOut
 * @property {string} accountId
 * @property {string} name
 * @property {(string | null)} institution
 * @property {import('../app/dec.js').Dec} balance
 * @property {import('../app/dec.js').Dec} contributed
 * @property {import('../app/dec.js').Dec} granted
 */

/**
 * @typedef {Object} GainGroup
 * @property {string} key
 * @property {string} label
 * @property {import('../app/dec.js').Dec} shortTerm
 * @property {import('../app/dec.js').Dec} longTerm
 * @property {import('../app/dec.js').Dec} total
 */

/**
 * @typedef {Object} GainsView
 * @property {string} by
 * @property {(number | null)} year
 * @property {Array<GainGroup>} realized
 * @property {Array<GainGroup>} unrealized
 */

/**
 * @typedef {Object} GiftIn
 * @property {Array<string>} people
 * @property {(string | null)} [occasion]
 * @property {(number | null)} [occasionYear]
 * @property {string} description
 * @property {string} [status]
 * @property {(import('../app/dec.js').Dec | null)} [cost]
 * @property {(string | null)} [transactionId]
 * @property {(string | null)} [store]
 * @property {(string | null)} [link]
 * @property {(string | null)} [notes]
 * @property {boolean} [cash]
 * @property {boolean} [thankYou]
 */

/**
 * @typedef {Object} GiftOut
 * @property {string} id
 * @property {Array<PersonRef>} people
 * @property {(string | null)} occasion
 * @property {string} occasionLabel
 * @property {(number | null)} occasionYear
 * @property {string} description
 * @property {string} status
 * @property {(import('../app/dec.js').Dec | null)} cost
 * @property {(Paid | null)} paid
 * @property {(string | null)} store
 * @property {(string | null)} link
 * @property {(string | null)} notes
 * @property {boolean} cash
 * @property {boolean} thankYou
 * @property {Array<ReceiptRow>} documents
 * @property {boolean} canWrite
 * @property {number} version
 */

/**
 * @typedef {Object} GiftTaxOut
 * @property {string} giver
 * @property {string} person
 * @property {import('../app/dec.js').Dec} given
 * @property {import('../app/dec.js').Dec} exclusion
 */

/**
 * @typedef {Object} GiftYearOut
 * @property {string} contributor
 * @property {string} name
 * @property {number} year
 * @property {import('../app/dec.js').Dec} counted
 * @property {import('../app/dec.js').Dec} exclusion
 * @property {boolean} over
 * @property {(number | null)} fromElection
 */

/**
 * @typedef {Object} GivingOut
 * @property {Array<DonationRow>} deductible
 * @property {Array<DonationRow>} apart
 * @property {import('../app/dec.js').Dec} deductibleTotal
 * @property {number} missingAcks
 * @property {Array<string>} notes
 */

/**
 * @typedef {Object} GivingView
 * @property {number} year
 * @property {(moneykata__ui__giving__PlanOut | null)} plan
 * @property {import('../app/dec.js').Dec} income
 * @property {import('../app/dec.js').Dec} target
 * @property {import('../app/dec.js').Dec} given
 * @property {import('../app/dec.js').Dec} pace
 * @property {import('../app/dec.js').Dec} pledged
 * @property {import('../app/dec.js').Dec} projected
 * @property {Array<import('../app/dec.js').Dec>} byMonth
 * @property {Array<Share>} byOrganisation
 * @property {Array<Share>} byCause
 * @property {Array<Share>} byKind
 * @property {Array<YearPct>} history
 * @property {Array<FundOut>} funds
 * @property {number} missingAcks
 * @property {Array<string>} notes
 */

/**
 * @typedef {Object} GoalView
 * @property {(BeneficiaryOut | null)} beneficiary
 * @property {(ProjectionDetail | null)} projection
 * @property {number} others
 */

/**
 * What a DELETE took away (S13.8.1): its id (for a pair, its two keys joined by a slash),
 * when, and the version it had.
 * @typedef {Object} Gone
 * @property {string} id
 * @property {(string | null)} [deletedAt]
 * @property {(number | null)} [version]
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
 * @property {import('../app/dec.js').Dec} total
 * @property {Object<string, import('../app/dec.js').Dec>} groups
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
 * @property {import('../app/dec.js').Dec} total
 * @property {Array<string>} accounts
 * @property {boolean} inNetWorth
 */

/**
 * @typedef {Object} HTTPValidationError
 * @property {Array<ValidationError>} [detail]
 */

/**
 * @typedef {Object} HoldingCheckRow
 * @property {string} label
 * @property {(string | null)} instrumentId
 * @property {(string | null)} symbol
 * @property {(import('../app/dec.js').Dec | null)} statement
 * @property {(import('../app/dec.js').Dec | null)} held
 * @property {(import('../app/dec.js').Dec | null)} difference
 * @property {(import('../app/dec.js').Dec | null)} statementBasis
 * @property {(import('../app/dec.js').Dec | null)} heldBasis
 * @property {boolean} cash
 * @property {boolean} ok
 */

/**
 * @typedef {Object} HoldingRow
 * @property {string} instrumentId
 * @property {string} symbol
 * @property {(string | null)} name
 * @property {string} instrumentClass
 * @property {import('../app/dec.js').Dec} quantity
 * @property {(import('../app/dec.js').Dec | null)} costBasis
 * @property {(import('../app/dec.js').Dec | null)} price
 * @property {(string | null)} priceAsOf
 * @property {(string | null)} priceSource
 * @property {(import('../app/dec.js').Dec | null)} value
 * @property {(import('../app/dec.js').Dec | null)} gain
 * @property {Array<LotRow>} lots
 */

/**
 * @typedef {Object} HoldingTotal
 * @property {string} instrumentId
 * @property {string} symbol
 * @property {(string | null)} name
 * @property {string} instrumentClass
 * @property {import('../app/dec.js').Dec} quantity
 * @property {(import('../app/dec.js').Dec | null)} price
 * @property {(string | null)} priceAsOf
 * @property {(string | null)} priceSource
 * @property {boolean} stale
 * @property {(import('../app/dec.js').Dec | null)} value
 * @property {(import('../app/dec.js').Dec | null)} costBasis
 * @property {(import('../app/dec.js').Dec | null)} gain
 * @property {(import('../app/dec.js').Dec | null)} weight
 * @property {Array<string>} accounts
 */

/**
 * @typedef {Object} Holdings
 * @property {import('../app/dec.js').Dec} cash
 * @property {import('../app/dec.js').Dec} total
 * @property {Array<HoldingRow>} holdings
 * @property {Array<Object<string, unknown>>} problems
 */

/**
 * @typedef {Object} HolidayOut
 * @property {string} key
 * @property {string} label
 * @property {(string | null)} date
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
 * @typedef {Object} ImprovementIn
 * @property {string} date
 * @property {string} description
 * @property {import('../app/dec.js').Dec} amount
 */

/**
 * @typedef {Object} ImprovementOut
 * @property {string} id
 * @property {string} date
 * @property {string} description
 * @property {import('../app/dec.js').Dec} amount
 * @property {number} version
 */

/**
 * @typedef {Object} IncomeOut
 * @property {Array<Amount>} interest
 * @property {import('../app/dec.js').Dec} interestTotal
 * @property {import('../app/dec.js').Dec} ordinary
 * @property {import('../app/dec.js').Dec} qualified
 * @property {import('../app/dec.js').Dec} capitalGainDistributions
 * @property {import('../app/dec.js').Dec} returnOfCapital
 * @property {Array<Amount>} dividendsByPayer
 */

/**
 * A share from the linked server, as an admin here sees it (S11.3): its kind, owner, date
 * and who it names, never its name or figures.
 * @typedef {Object} Incoming
 * @property {string} kind
 * @property {string} ownerName
 * @property {string} sharedAt
 * @property {Array<string>} names
 * @property {boolean} includeReceipts
 */

/**
 * @typedef {Object} InstrumentOut
 * @property {string} id
 * @property {string} symbol
 * @property {(string | null)} name
 * @property {string} instrumentClass
 */

/**
 * @typedef {Object} InvestedOut
 * @property {string} assetClass
 * @property {import('../app/dec.js').Dec} rate
 * @property {import('../app/dec.js').Dec} contributed
 * @property {import('../app/dec.js').Dec} value
 * @property {import('../app/dec.js').Dec} gain
 */

/**
 * @typedef {Object} Invitation
 * @property {string} code
 * @property {moneykata__ui__links__LinkOut} link
 */

/**
 * @typedef {Object} InvitationInfo
 * @property {string} username
 * @property {string} displayName
 * @property {string} household
 */

/**
 * @typedef {Object} IssueOut
 * @property {string} kind
 * @property {string} text
 * @property {(string | null)} link
 */

/**
 * @typedef {Object} ItemDetail
 * @property {string} id
 * @property {string} accountId
 * @property {string} name
 * @property {(string | null)} category
 * @property {string} acquiredOn
 * @property {string} acquiredHow
 * @property {import('../app/dec.js').Dec} quantity
 * @property {string} valuation
 * @property {(string | null)} metal
 * @property {(import('../app/dec.js').Dec | null)} fineOunces
 * @property {import('../app/dec.js').Dec} basis
 * @property {import('../app/dec.js').Dec} value
 * @property {import('../app/dec.js').Dec} gain
 * @property {import('../app/dec.js').Dec} years
 * @property {(ValuationOut | null)} latest
 * @property {boolean} stale
 * @property {(Sale | null)} sale
 * @property {Array<SecuredLoan>} loans
 * @property {(import('../app/dec.js').Dec | null)} equity
 * @property {number} version
 * @property {(string | null)} description
 * @property {import('../app/dec.js').Dec} costBasis
 * @property {(string | null)} location
 * @property {(string | null)} serial
 * @property {(string | null)} condition
 * @property {(import('../app/dec.js').Dec | null)} insuredValue
 * @property {(string | null)} policy
 * @property {(string | null)} notes
 * @property {(import('../app/dec.js').Dec | null)} unitWeight
 * @property {(string | null)} weightUnit
 * @property {(import('../app/dec.js').Dec | null)} purity
 * @property {import('../app/dec.js').Dec} sellPremium
 * @property {(import('../app/dec.js').Dec | null)} depreciationRate
 * @property {(string | null)} address
 * @property {(import('../app/dec.js').Dec | null)} closingCosts
 * @property {boolean} primaryResidence
 * @property {boolean} personalUse
 * @property {(import('../app/dec.js').Dec | null)} spot
 * @property {(string | null)} spotAsOf
 * @property {Array<ValuationOut>} valuations
 * @property {Array<ImprovementOut>} improvements
 * @property {Array<ReceiptRow>} documents
 * @property {Array<Array<unknown>>} history
 * @property {boolean} canWrite
 */

/**
 * @typedef {Object} ItemIn
 * @property {string} name
 * @property {(string | null)} [category]
 * @property {(string | null)} [description]
 * @property {string} acquiredOn
 * @property {string} [acquiredHow]
 * @property {import('../app/dec.js').Dec} costBasis
 * @property {import('../app/dec.js').Dec} [quantity]
 * @property {(string | null)} [location]
 * @property {(string | null)} [serial]
 * @property {(string | null)} [condition]
 * @property {(import('../app/dec.js').Dec | null)} [insuredValue]
 * @property {(string | null)} [policy]
 * @property {(string | null)} [notes]
 * @property {string} [valuation]
 * @property {(string | null)} [metal]
 * @property {(import('../app/dec.js').Dec | null)} [unitWeight]
 * @property {(string | null)} [weightUnit]
 * @property {(string | null)} [purity]
 * @property {import('../app/dec.js').Dec} [sellPremium]
 * @property {(import('../app/dec.js').Dec | null)} [depreciationRate]
 * @property {(string | null)} [address]
 * @property {(import('../app/dec.js').Dec | null)} [closingCosts]
 * @property {boolean} [primaryResidence]
 * @property {boolean} [personalUse]
 */

/**
 * @typedef {Object} ItemRow
 * @property {string} id
 * @property {string} accountId
 * @property {string} name
 * @property {(string | null)} category
 * @property {string} acquiredOn
 * @property {string} acquiredHow
 * @property {import('../app/dec.js').Dec} quantity
 * @property {string} valuation
 * @property {(string | null)} metal
 * @property {(import('../app/dec.js').Dec | null)} fineOunces
 * @property {import('../app/dec.js').Dec} basis
 * @property {import('../app/dec.js').Dec} value
 * @property {import('../app/dec.js').Dec} gain
 * @property {import('../app/dec.js').Dec} years
 * @property {(ValuationOut | null)} latest
 * @property {boolean} stale
 * @property {(Sale | null)} sale
 * @property {Array<SecuredLoan>} loans
 * @property {(import('../app/dec.js').Dec | null)} equity
 * @property {number} version
 */

/**
 * @typedef {Object} ItemsView
 * @property {Array<ItemRow>} items
 * @property {Array<MetalOut>} metals
 * @property {import('../app/dec.js').Dec} value
 * @property {import('../app/dec.js').Dec} basis
 * @property {import('../app/dec.js').Dec} gain
 * @property {boolean} canWrite
 */

/**
 * @typedef {Object} JobOut
 * @property {string} id
 * @property {string} kind
 * @property {string} state
 * @property {import('../app/dec.js').Dec} progress
 * @property {(Object<string, unknown> | null)} result
 * @property {(Object<string, unknown> | null)} error
 */

/**
 * @typedef {Object} JoinIn
 * @property {string} code
 */

/**
 * @typedef {Object} KeepIn
 * @property {(string | null)} [periodStart]
 * @property {(string | null)} [periodEnd]
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
 * @typedef {Object} LastYear
 * @property {string} filing
 * @property {CarriedView} figures
 */

/**
 * @typedef {Object} LinkedFile
 * @property {string} id
 * @property {string} itemId
 * @property {string} contentType
 * @property {number} length
 * @property {(string | null)} thumbnail
 * @property {Object<string, unknown>} meta
 */

/**
 * @typedef {Object} LinkedPeople
 * @property {string} linkId
 * @property {string} serverName
 * @property {(string | null)} householdName
 * @property {boolean} includeReceipts
 * @property {Array<UserGrant>} users
 */

/**
 * @typedef {Object} LinkedRow
 * @property {string} id
 * @property {string} kind
 * @property {string} name
 * @property {string} ownerName
 * @property {string} asOf
 * @property {(Object<string, unknown> | null)} row
 */

/**
 * @typedef {Object} LinksView
 * @property {string} fingerprint
 * @property {(string | null)} address
 * @property {Array<moneykata__ui__links__LinkOut>} links
 */

/**
 * @typedef {Object} LoanOut
 * @property {string} account
 * @property {string} form
 * @property {import('../app/dec.js').Dec} interest
 * @property {import('../app/dec.js').Dec} pmi
 * @property {import('../app/dec.js').Dec} propertyTax
 * @property {(string | null)} securedBy
 */

/**
 * @typedef {Object} LoanView
 * @property {(TermsOut | null)} terms
 * @property {import('../app/dec.js').Dec} balance
 * @property {import('../app/dec.js').Dec} rate
 * @property {import('../app/dec.js').Dec} payment
 * @property {import('../app/dec.js').Dec} total
 * @property {(string | null)} nextDate
 * @property {(string | null)} payoffDate
 * @property {(string | null)} originalPayoff
 * @property {import('../app/dec.js').Dec} interestPaid
 * @property {import('../app/dec.js').Dec} interestAhead
 * @property {import('../app/dec.js').Dec} principalThisYear
 * @property {import('../app/dec.js').Dec} overpaid
 * @property {Array<moneykata__ui__loans__RowOut>} rows
 * @property {(ServicerCheck | null)} servicer
 * @property {(Equity | null)} [equity]
 * @property {(Following | null)} [following]
 * @property {boolean} canWrite
 * @property {number} [version]
 */

/**
 * @typedef {Object} Login
 * @property {string} login
 */

/**
 * @typedef {Object} LotOut
 * @property {string} acquiredOn
 * @property {import('../app/dec.js').Dec} quantity
 * @property {(import('../app/dec.js').Dec | null)} basis
 * @property {number} days
 * @property {boolean} longTerm
 */

/**
 * @typedef {Object} LotRow
 * @property {(string | null)} lotId
 * @property {string} acquiredOn
 * @property {import('../app/dec.js').Dec} quantity
 * @property {(import('../app/dec.js').Dec | null)} basis
 * @property {boolean} basisMissing
 * @property {boolean} standIn
 * @property {boolean} longTerm
 */

/**
 * @typedef {Object} Lump
 * @property {string} date
 * @property {import('../app/dec.js').Dec} amount
 */

/**
 * @typedef {Object} LumpView
 * @property {string} date
 * @property {import('../app/dec.js').Dec} amount
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
 * @typedef {Object} MetalOut
 * @property {string} metal
 * @property {import('../app/dec.js').Dec} ounces
 * @property {import('../app/dec.js').Dec} cost
 * @property {(import('../app/dec.js').Dec | null)} averageCost
 * @property {(import('../app/dec.js').Dec | null)} spot
 * @property {(string | null)} spotAsOf
 * @property {import('../app/dec.js').Dec} value
 * @property {import('../app/dec.js').Dec} gain
 */

/**
 * @typedef {Object} ModelRow
 * @property {string} model
 * @property {Array<Array<unknown>>} path
 * @property {Object<string, number>} at
 * @property {string} record
 */

/**
 * @typedef {Object} ModelsView
 * @property {(import('../app/dec.js').Dec | null)} price
 * @property {Array<ModelRow>} rows
 * @property {number} figuresYear
 */

/**
 * @typedef {Object} MonthRow
 * @property {string} categoryId
 * @property {string} label
 * @property {string} kind
 * @property {string} cadence
 * @property {boolean} rollover
 * @property {import('../app/dec.js').Dec} planned
 * @property {import('../app/dec.js').Dec} carried
 * @property {import('../app/dec.js').Dec} actual
 * @property {import('../app/dec.js').Dec} remaining
 * @property {string} state
 */

/**
 * @typedef {Object} MonthView
 * @property {string} month
 * @property {Array<MonthRow>} rows
 * @property {Array<Unplanned>} unplanned
 * @property {import('../app/dec.js').Dec} income
 * @property {import('../app/dec.js').Dec} expectedIncome
 * @property {import('../app/dec.js').Dec} spent
 * @property {import('../app/dec.js').Dec} plannedSpending
 * @property {number} uncategorised
 * @property {number} daysLeft
 * @property {boolean} canWrite
 * @property {number} version
 */

/**
 * @typedef {Object} Named
 * @property {string} id
 * @property {string} name
 * @property {boolean} deleted
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
 * @property {(import('../app/dec.js').Dec | null)} [openingBalance]
 * @property {(string | null)} [openingDate]
 * @property {(boolean | null)} [countInNetWorth]
 */

/**
 * @typedef {Object} NewAdjustment
 * @property {string} date
 * @property {import('../app/dec.js').Dec} amount
 * @property {string} note
 */

/**
 * @typedef {Object} NewAnchor
 * @property {string} date
 * @property {import('../app/dec.js').Dec} balance
 * @property {(string | null)} [note]
 */

/**
 * @typedef {Object} NewBook
 * @property {number} year
 * @property {Array<string>} filers
 * @property {boolean} [fromLastYear]
 */

/**
 * @typedef {Object} NewBookOut
 * @property {string} id
 * @property {number} year
 * @property {Array<Filer>} filers
 * @property {string} level
 * @property {string} label
 * @property {number} version
 * @property {Array<string>} dependentsLeftOut
 */

/**
 * @typedef {Object} NewBudget
 * @property {string} name
 * @property {Array<string>} [accountIds]
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
 * @typedef {Object} NewProjection
 * @property {string} name
 * @property {string} goal
 * @property {Object<string, unknown>} builtOn
 * @property {Object<string, unknown>} [inputs]
 */

/**
 * @typedef {Object} NewReconciliation
 * @property {string} statementDate
 * @property {import('../app/dec.js').Dec} statementBalance
 */

/**
 * @typedef {Object} NewSource
 * @property {string} name
 */

/**
 * @typedef {Object} NewToken
 * @property {string} name
 * @property {string} [scope]
 * @property {Array<TokenItem>} [items]
 * @property {number} [days]
 */

/**
 * @typedef {Object} NewUser
 * @property {string} displayName
 * @property {string} username
 * @property {string} email
 * @property {(string | null)} [sex]
 * @property {Array<string>} [groupIds]
 */

/**
 * @typedef {Object} Newer
 * @property {number} count
 */

/**
 * @typedef {Object} NextDate
 * @property {string} key
 * @property {string} label
 * @property {string} date
 * @property {number} days
 * @property {(number | null)} turns
 */

/**
 * @typedef {Object} OccasionIn
 * @property {string} kind
 * @property {(string | null)} [name]
 * @property {(string | null)} [holiday]
 * @property {(number | null)} [month]
 * @property {(number | null)} [day]
 * @property {(number | null)} [year]
 * @property {(import('../app/dec.js').Dec | null)} [budget]
 */

/**
 * @typedef {Object} OccasionOut
 * @property {string} kind
 * @property {(string | null)} [name]
 * @property {(string | null)} [holiday]
 * @property {(number | null)} [month]
 * @property {(number | null)} [day]
 * @property {(number | null)} [year]
 * @property {(import('../app/dec.js').Dec | null)} [budget]
 * @property {string} id
 * @property {string} label
 * @property {(string | null)} next
 */

/**
 * @typedef {Object} OpenRow
 * @property {string} accountId
 * @property {string} accountName
 * @property {string} instrumentId
 * @property {string} symbol
 * @property {(string | null)} name
 * @property {string} instrumentClass
 * @property {string} side
 * @property {import('../app/dec.js').Dec} quantity
 * @property {(import('../app/dec.js').Dec | null)} cost
 * @property {(import('../app/dec.js').Dec | null)} averageCost
 * @property {(import('../app/dec.js').Dec | null)} value
 * @property {(string | null)} priceSource
 * @property {(import('../app/dec.js').Dec | null)} unrealized
 * @property {(import('../app/dec.js').Dec | null)} unrealizedPct
 * @property {import('../app/dec.js').Dec} realized
 * @property {string} term
 * @property {number} days
 * @property {Array<LotOut>} lots
 * @property {(string | null)} [expiry]
 * @property {(number | null)} [daysToExpiry]
 * @property {(boolean | null)} [inTheMoney]
 */

/**
 * @typedef {Object} OptionTrade
 * @property {string} date
 * @property {string} action
 * @property {string} underlying
 * @property {string} right
 * @property {import('../app/dec.js').Dec} strike
 * @property {string} expiry
 * @property {import('../app/dec.js').Dec} contracts
 * @property {import('../app/dec.js').Dec} premium
 * @property {import('../app/dec.js').Dec} [fees]
 * @property {number} [multiplier]
 */

/**
 * @typedef {Object} OptionTradeRow
 * @property {string} accountId
 * @property {string} accountName
 * @property {string} instrumentId
 * @property {string} symbol
 * @property {string} side
 * @property {import('../app/dec.js').Dec} contracts
 * @property {string} opened
 * @property {(string | null)} closed
 * @property {(string | null)} how
 * @property {import('../app/dec.js').Dec} premiumIn
 * @property {import('../app/dec.js').Dec} premiumOut
 * @property {(import('../app/dec.js').Dec | null)} value
 * @property {(import('../app/dec.js').Dec | null)} pl
 * @property {import('../app/dec.js').Dec} capitalAtRisk
 * @property {(import('../app/dec.js').Dec | null)} returnPct
 */

/**
 * @typedef {Object} OrganisationIn
 * @property {string} name
 * @property {(string | null)} [ein]
 * @property {boolean} [deductible]
 * @property {Array<string>} [causes]
 * @property {(import('../app/dec.js').Dec | null)} [pledge]
 * @property {(string | null)} [pledgeEvery]
 * @property {(string | null)} [notes]
 */

/**
 * @typedef {Object} OrganisationOut
 * @property {string} name
 * @property {(string | null)} [ein]
 * @property {boolean} [deductible]
 * @property {Array<string>} [causes]
 * @property {(import('../app/dec.js').Dec | null)} [pledge]
 * @property {(string | null)} [pledgeEvery]
 * @property {(string | null)} [notes]
 * @property {string} id
 * @property {import('../app/dec.js').Dec} given
 * @property {boolean} canWrite
 * @property {number} version
 */

/**
 * @typedef {Object} OutcomeOut
 * @property {(string | null)} payoffDate
 * @property {number} months
 * @property {import('../app/dec.js').Dec} interest
 * @property {import('../app/dec.js').Dec} paid
 * @property {import('../app/dec.js').Dec} payment
 * @property {import('../app/dec.js').Dec} paymentAfter
 * @property {import('../app/dec.js').Dec} fees
 * @property {number} monthsSaved
 * @property {import('../app/dec.js').Dec} interestSaved
 * @property {Array<moneykata__ui__loans__Point>} balances
 */

/**
 * @typedef {Object} Page_AccountRow_
 * @property {Array<AccountRow>} items
 * @property {number} total
 * @property {number} offset
 * @property {number} limit
 */

/**
 * @typedef {Object} Page_ActivityItem_
 * @property {Array<ActivityItem>} items
 * @property {number} total
 * @property {number} offset
 * @property {number} limit
 */

/**
 * @typedef {Object} Page_BookRow_
 * @property {Array<BookRow>} items
 * @property {number} total
 * @property {number} offset
 * @property {number} limit
 */

/**
 * @typedef {Object} Page_BudgetRow_
 * @property {Array<BudgetRow>} items
 * @property {number} total
 * @property {number} offset
 * @property {number} limit
 */

/**
 * @typedef {Object} Page_CandidateOut_
 * @property {Array<CandidateOut>} items
 * @property {number} total
 * @property {number} offset
 * @property {number} limit
 */

/**
 * @typedef {Object} Page_Candidate_
 * @property {Array<Candidate>} items
 * @property {number} total
 * @property {number} offset
 * @property {number} limit
 */

/**
 * @typedef {Object} Page_CategoryOut_
 * @property {Array<CategoryOut>} items
 * @property {number} total
 * @property {number} offset
 * @property {number} limit
 */

/**
 * @typedef {Object} Page_Close_
 * @property {Array<Close>} items
 * @property {number} total
 * @property {number} offset
 * @property {number} limit
 */

/**
 * @typedef {Object} Page_DonationOut_
 * @property {Array<DonationOut>} items
 * @property {number} total
 * @property {number} offset
 * @property {number} limit
 */

/**
 * @typedef {Object} Page_GiftOut_
 * @property {Array<GiftOut>} items
 * @property {number} total
 * @property {number} offset
 * @property {number} limit
 */

/**
 * @typedef {Object} Page_GroupRow_
 * @property {Array<GroupRow>} items
 * @property {number} total
 * @property {number} offset
 * @property {number} limit
 */

/**
 * @typedef {Object} Page_HolidayOut_
 * @property {Array<HolidayOut>} items
 * @property {number} total
 * @property {number} offset
 * @property {number} limit
 */

/**
 * @typedef {Object} Page_Household_
 * @property {Array<moneykata__ui__linked__Household>} items
 * @property {number} total
 * @property {number} offset
 * @property {number} limit
 */

/**
 * @typedef {Object} Page_ImportRow_
 * @property {Array<ImportRow>} items
 * @property {number} total
 * @property {number} offset
 * @property {number} limit
 */

/**
 * @typedef {Object} Page_InstrumentOut_
 * @property {Array<InstrumentOut>} items
 * @property {number} total
 * @property {number} offset
 * @property {number} limit
 */

/**
 * @typedef {Object} Page_LinkedFile_
 * @property {Array<LinkedFile>} items
 * @property {number} total
 * @property {number} offset
 * @property {number} limit
 */

/**
 * @typedef {Object} Page_LinkedRow_
 * @property {Array<LinkedRow>} items
 * @property {number} total
 * @property {number} offset
 * @property {number} limit
 */

/**
 * @typedef {Object} Page_OptionTradeRow_
 * @property {Array<OptionTradeRow>} items
 * @property {number} total
 * @property {number} offset
 * @property {number} limit
 */

/**
 * @typedef {Object} Page_OrganisationOut_
 * @property {Array<OrganisationOut>} items
 * @property {number} total
 * @property {number} offset
 * @property {number} limit
 */

/**
 * @typedef {Object} Page_PersonOut_
 * @property {Array<PersonOut>} items
 * @property {number} total
 * @property {number} offset
 * @property {number} limit
 */

/**
 * @typedef {Object} Page_PersonRow_
 * @property {Array<PersonRow>} items
 * @property {number} total
 * @property {number} offset
 * @property {number} limit
 */

/**
 * @typedef {Object} Page_Plan_
 * @property {Array<Plan_Output>} items
 * @property {number} total
 * @property {number} offset
 * @property {number} limit
 */

/**
 * @typedef {Object} Page_PortfolioRow_
 * @property {Array<PortfolioRow>} items
 * @property {number} total
 * @property {number} offset
 * @property {number} limit
 */

/**
 * @typedef {Object} Page_ProjectionRow_
 * @property {Array<ProjectionRow>} items
 * @property {number} total
 * @property {number} offset
 * @property {number} limit
 */

/**
 * @typedef {Object} Page_Purchase_
 * @property {Array<Purchase>} items
 * @property {number} total
 * @property {number} offset
 * @property {number} limit
 */

/**
 * @typedef {Object} Page_ReceiptRow_
 * @property {Array<ReceiptRow>} items
 * @property {number} total
 * @property {number} offset
 * @property {number} limit
 */

/**
 * @typedef {Object} Page_RecurringRow_
 * @property {Array<RecurringRow>} items
 * @property {number} total
 * @property {number} offset
 * @property {number} limit
 */

/**
 * @typedef {Object} Page_RelationOut_
 * @property {Array<RelationOut>} items
 * @property {number} total
 * @property {number} offset
 * @property {number} limit
 */

/**
 * @typedef {Object} Page_RelationshipOut_
 * @property {Array<RelationshipOut>} items
 * @property {number} total
 * @property {number} offset
 * @property {number} limit
 */

/**
 * @typedef {Object} Page_ReturnRow_
 * @property {Array<ReturnRow>} items
 * @property {number} total
 * @property {number} offset
 * @property {number} limit
 */

/**
 * @typedef {Object} Page_SavedPlan_
 * @property {Array<SavedPlan>} items
 * @property {number} total
 * @property {number} offset
 * @property {number} limit
 */

/**
 * @typedef {Object} Page_Securable_
 * @property {Array<Securable>} items
 * @property {number} total
 * @property {number} offset
 * @property {number} limit
 */

/**
 * @typedef {Object} Page_SignupRow_
 * @property {Array<SignupRow>} items
 * @property {number} total
 * @property {number} offset
 * @property {number} limit
 */

/**
 * @typedef {Object} Page_TokenOut_
 * @property {Array<TokenOut>} items
 * @property {number} total
 * @property {number} offset
 * @property {number} limit
 */

/**
 * @typedef {Object} Page_TrendPoint_
 * @property {Array<TrendPoint>} items
 * @property {number} total
 * @property {number} offset
 * @property {number} limit
 */

/**
 * @typedef {Object} Page_TxnOut_
 * @property {Array<TxnOut>} items
 * @property {number} total
 * @property {number} offset
 * @property {number} limit
 */

/**
 * @typedef {Object} Page_UpcomingOut_
 * @property {Array<UpcomingOut>} items
 * @property {number} total
 * @property {number} offset
 * @property {number} limit
 */

/**
 * @typedef {Object} Page_UserRow_
 * @property {Array<UserRow>} items
 * @property {number} total
 * @property {number} offset
 * @property {number} limit
 */

/**
 * @typedef {Object} Paid
 * @property {string} transactionId
 * @property {string} date
 * @property {import('../app/dec.js').Dec} amount
 * @property {(string | null)} payee
 * @property {string} accountName
 */

/**
 * @typedef {Object} Panels
 * @property {number} year
 * @property {Array<moneykata__ui__taxpanels__RowOut>} rows
 * @property {Array<WashOut>} washes
 * @property {ScheduleDOut} scheduleD
 * @property {IncomeOut} income
 * @property {RetirementOut} retirement
 * @property {Array<TagOut>} deductions
 * @property {Array<DependentAge>} dependents
 * @property {Array<Quarter>} estimated
 * @property {(import('../app/dec.js').Dec | null)} lastYearTax
 * @property {GivingOut} giving
 * @property {Array<EducationOut>} education
 * @property {Array<StudentOut>} students
 * @property {Array<GiftTaxOut>} giftTax
 * @property {Array<string>} elections
 * @property {Array<LoanOut>} loans
 * @property {Array<ResidenceOut>} residences
 * @property {Array<IssueOut>} issues
 * @property {Array<string>} leftOut
 * @property {string} covers
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
 * @typedef {Object} Payment
 * @property {(string | null)} [id]
 * @property {number} quarter
 * @property {(string | null)} [dueDate]
 * @property {import('../app/dec.js').Dec} amount
 * @property {(string | null)} [paidOn]
 * @property {(string | null)} [transactionId]
 */

/**
 * @typedef {Object} PaymentIn
 * @property {string} date
 * @property {import('../app/dec.js').Dec} amount
 * @property {(string | null)} [fromAccountId]
 * @property {(string | null)} [transactionId]
 * @property {(import('../app/dec.js').Dec | null)} [principal]
 * @property {(import('../app/dec.js').Dec | null)} [interest]
 * @property {(import('../app/dec.js').Dec | null)} [escrowTax]
 * @property {(import('../app/dec.js').Dec | null)} [escrowInsurance]
 * @property {(import('../app/dec.js').Dec | null)} [pmi]
 * @property {(import('../app/dec.js').Dec | null)} [fees]
 */

/**
 * A payment as shown; its own model, so the contract has one schema each way.
 * @typedef {Object} PaymentView
 * @property {(string | null)} id
 * @property {number} quarter
 * @property {(string | null)} dueDate
 * @property {import('../app/dec.js').Dec} amount
 * @property {(string | null)} paidOn
 * @property {(string | null)} transactionId
 */

/**
 * @typedef {Object} PayoffOut
 * @property {OutcomeOut} schedule
 * @property {OutcomeOut} plan
 * @property {(OutcomeOut | null)} recast
 * @property {InvestedOut} invested
 * @property {Array<moneykata__ui__loans__RowOut>} planRows
 * @property {Array<moneykata__ui__loans__RowOut>} recastRows
 * @property {Array<ResetView>} assumedRates
 */

/**
 * @typedef {Object} PeriodRow
 * @property {string} start
 * @property {string} end
 * @property {Array<string>} importIds
 */

/**
 * A gift plan the caller sees, with its person.
 * @typedef {Object} PersonOut
 * @property {string} id
 * @property {string} planId
 * @property {string} name
 * @property {string} sex
 * @property {(string | null)} relation
 * @property {(string | null)} userId
 * @property {(string | null)} userName
 * @property {(number | null)} birthMonth
 * @property {(number | null)} birthDay
 * @property {(number | null)} birthYear
 * @property {(string | null)} diedOn
 * @property {(string | null)} wedding
 * @property {boolean} private
 * @property {boolean} canChangePerson
 * @property {boolean} canMakePrivate
 * @property {boolean} isUser
 * @property {(import('../app/dec.js').Dec | null)} giftBudget
 * @property {number} leadDays
 * @property {(string | null)} notes
 * @property {Array<OccasionOut>} occasions
 * @property {(NextDate | null)} next
 * @property {import('../app/dec.js').Dec} spent
 * @property {(string | null)} lastGift
 * @property {string} level
 * @property {string} ownerName
 * @property {number} version
 * @property {number} personVersion
 */

/**
 * @typedef {Object} PersonRef
 * @property {string} id
 * @property {string} name
 * @property {boolean} [deleted]
 */

/**
 * @typedef {Object} PersonRow
 * @property {string} id
 * @property {string} name
 * @property {string} sex
 * @property {(number | null)} birthMonth
 * @property {(number | null)} birthDay
 * @property {(number | null)} birthYear
 * @property {(string | null)} diedOn
 * @property {boolean} private
 * @property {(string | null)} userId
 * @property {(string | null)} relation
 * @property {boolean} canChange
 * @property {(string | null)} createdBy
 * @property {number} version
 */

/**
 * @typedef {Object} PersonSpend
 * @property {PersonRef} person
 * @property {import('../app/dec.js').Dec} spent
 * @property {(import('../app/dec.js').Dec | null)} budget
 */

/**
 * @typedef {Object} PickIn
 * @property {string} lotId
 * @property {import('../app/dec.js').Dec} quantity
 */

/**
 * The plan from a month on: the categories listed, and none other.
 * @typedef {Object} Plan_Input
 * @property {string} month
 * @property {Array<PlanLine>} lines
 */

/**
 * @typedef {Object} Plan_Output
 * @property {string} id
 * @property {string} name
 * @property {string} goal
 * @property {(string | null)} status
 * @property {string} headline
 * @property {Array<Array<unknown>>} actual
 * @property {Array<Array<unknown>>} baseline
 * @property {(string | null)} sharedBy
 * @property {Object<string, unknown>} builtOn
 */

/**
 * @typedef {Object} PlanLine
 * @property {string} categoryId
 * @property {import('../app/dec.js').Dec} amount
 * @property {string} [cadence]
 * @property {boolean} [rollover]
 */

/**
 * The inputs as saved; its own models, so the contract has one schema for each direction.
 * @typedef {Object} PlanView
 * @property {import('../app/dec.js').Dec} monthly
 * @property {(string | null)} monthlyFrom
 * @property {(string | null)} monthlyUntil
 * @property {import('../app/dec.js').Dec} yearly
 * @property {number} yearlyMonth
 * @property {Array<LumpView>} lumps
 * @property {boolean} biweekly
 * @property {import('../app/dec.js').Dec} roundTo
 * @property {boolean} recast
 * @property {import('../app/dec.js').Dec} recastFee
 * @property {string} investClass
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
 * @property {import('../app/dec.js').Dec} cash
 * @property {import('../app/dec.js').Dec} total
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
 * @property {import('../app/dec.js').Dec} value
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
 * @property {import('../app/dec.js').Dec} contributed
 * @property {import('../app/dec.js').Dec} growth
 * @property {import('../app/dec.js').Dec} start
 * @property {import('../app/dec.js').Dec} end
 */

/**
 * @typedef {Object} PositionIn
 * @property {string} label
 * @property {(string | null)} [instrumentId]
 * @property {(string | null)} [symbol]
 * @property {(import('../app/dec.js').Dec | null)} [quantity]
 * @property {(import('../app/dec.js').Dec | null)} [price]
 * @property {(import('../app/dec.js').Dec | null)} [marketValue]
 * @property {(import('../app/dec.js').Dec | null)} [costBasis]
 * @property {boolean} [cash]
 */

/**
 * @typedef {Object} PositionsView
 * @property {Summary} summary
 * @property {Array<OpenRow>} open
 * @property {Array<ClosedRow>} closed
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
 * @property {string} personId
 * @property {string} sex
 * @property {(number | null)} birthMonth
 * @property {(number | null)} birthDay
 * @property {(number | null)} birthYear
 * @property {string} alertEmails
 * @property {TwoStep} twoStep
 * @property {Array<Relation>} relations
 * @property {(Spouse | null)} spouse
 * @property {number} version
 */

/**
 * @typedef {Object} ProfileChange
 * @property {(string | null)} [displayName]
 * @property {(string | null)} [avatar]
 * @property {(string | null)} [timeZone]
 * @property {(string | null)} [theme]
 * @property {(string | null)} [sex]
 * @property {(number | null)} [birthMonth]
 * @property {(number | null)} [birthDay]
 * @property {(number | null)} [birthYear]
 * @property {(string | null)} [alertEmails]
 */

/**
 * @typedef {Object} ProjectionChange
 * @property {(string | null)} [name]
 * @property {(Object<string, unknown> | null)} [builtOn]
 * @property {(Object<string, unknown> | null)} [inputs]
 * @property {boolean} [rebaseline]
 */

/**
 * @typedef {Object} ProjectionDetail
 * @property {string} id
 * @property {string} name
 * @property {string} goal
 * @property {boolean} active
 * @property {string} level
 * @property {string} ownerName
 * @property {Object<string, unknown>} builtOn
 * @property {string} builtOnLabel
 * @property {string} headline
 * @property {(string | null)} status
 * @property {boolean} shown
 * @property {number} sharedWith
 * @property {number} version
 * @property {Object<string, unknown>} inputs
 * @property {Object<string, unknown>} result
 * @property {(Object<string, unknown> | null)} tracking
 * @property {(string | null)} baselineAt
 */

/**
 * @typedef {Object} ProjectionRow
 * @property {string} id
 * @property {string} name
 * @property {string} goal
 * @property {boolean} active
 * @property {string} level
 * @property {string} ownerName
 * @property {Object<string, unknown>} builtOn
 * @property {string} builtOnLabel
 * @property {string} headline
 * @property {(string | null)} status
 * @property {boolean} shown
 * @property {number} sharedWith
 * @property {number} version
 */

/**
 * @typedef {Object} PruneIn
 * @property {Array<string>} categories
 * @property {number} count
 */

/**
 * @typedef {Object} PruneOut
 * @property {number} files
 * @property {number} bytes
 * @property {string} backup
 */

/**
 * @typedef {Object} Purchase
 * @property {string} transactionId
 * @property {string} date
 * @property {import('../app/dec.js').Dec} amount
 * @property {(string | null)} payee
 * @property {string} accountName
 * @property {(string | null)} category
 */

/**
 * @typedef {Object} Quarter
 * @property {string} jurisdiction
 * @property {number} quarter
 * @property {import('../app/dec.js').Dec} amount
 */

/**
 * @typedef {Object} ReadingQueue
 * @property {number} waiting
 * @property {number} reading
 * @property {number} failed
 * @property {number} read
 * @property {(string | null)} lastRun
 */

/**
 * @typedef {Object} Recast
 * @property {string} date
 * @property {import('../app/dec.js').Dec} [fee]
 */

/**
 * @typedef {Object} RecastView
 * @property {string} date
 * @property {import('../app/dec.js').Dec} fee
 */

/**
 * @typedef {Object} ReceiptChange
 * @property {(string | null)} [date]
 * @property {(import('../app/dec.js').Dec | null)} [amount]
 * @property {(string | null)} [payee]
 * @property {(string | null)} [notes]
 * @property {(Array<string> | null)} [tags]
 * @property {(boolean | null)} [keep]
 */

/**
 * @typedef {Object} ReceiptDetail
 * @property {string} id
 * @property {string} fileName
 * @property {string} mediaType
 * @property {number} size
 * @property {string} uploadedAt
 * @property {string} ownerId
 * @property {string} ownerName
 * @property {string} level
 * @property {(string | null)} date
 * @property {(import('../app/dec.js').Dec | null)} amount
 * @property {(string | null)} payee
 * @property {(string | null)} notes
 * @property {Array<string>} tags
 * @property {Array<moneykata__ui__receipts__LinkOut>} links
 * @property {boolean} hasThumbnail
 * @property {string} readStatus
 * @property {(string | null)} readError
 * @property {Array<string>} filled
 * @property {boolean} keep
 * @property {(string | null)} filePrunedAt
 * @property {number} version
 * @property {Array<Suggestion>} matches
 * @property {(string | null)} text
 * @property {Object<string, Suggested>} suggested
 * @property {(string | null)} readMethod
 * @property {(string | null)} readEngine
 * @property {(string | null)} readAt
 * @property {string} kept
 * @property {string} keptState
 * @property {(string | null)} keptUntil
 * @property {boolean} keptSoon
 * @property {(string | null)} keptWhy
 */

/**
 * @typedef {Object} ReceiptRow
 * @property {string} id
 * @property {string} fileName
 * @property {string} mediaType
 * @property {number} size
 * @property {string} uploadedAt
 * @property {string} ownerId
 * @property {string} ownerName
 * @property {string} level
 * @property {(string | null)} date
 * @property {(import('../app/dec.js').Dec | null)} amount
 * @property {(string | null)} payee
 * @property {(string | null)} notes
 * @property {Array<string>} tags
 * @property {Array<moneykata__ui__receipts__LinkOut>} links
 * @property {boolean} hasThumbnail
 * @property {string} readStatus
 * @property {(string | null)} readError
 * @property {Array<string>} filled
 * @property {boolean} keep
 * @property {(string | null)} filePrunedAt
 * @property {number} version
 */

/**
 * @typedef {Object} ReconcileView
 * @property {Array<PeriodRow>} periods
 * @property {Array<Array<string>>} gaps
 * @property {Array<Array<string>>} overlaps
 * @property {Array<CheckRow>} checks
 * @property {Array<ValueCheckRow>} valueChecks
 * @property {(string | null)} holdingChecksAsOf
 * @property {Array<HoldingCheckRow>} holdingChecks
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
 * @property {import('../app/dec.js').Dec} statementBalance
 * @property {import('../app/dec.js').Dec} cleared
 * @property {import('../app/dec.js').Dec} difference
 * @property {(string | null)} finishedAt
 * @property {number} version
 */

/**
 * Shown once: only their hashes are kept.
 * @typedef {Object} RecoveryCodes
 * @property {Array<string>} codes
 */

/**
 * @typedef {Object} RecurringRow
 * @property {string} payee
 * @property {string} accountId
 * @property {string} accountName
 * @property {string} every
 * @property {string} last
 * @property {string} next
 * @property {import('../app/dec.js').Dec} usual
 * @property {import('../app/dec.js').Dec} lastAmount
 * @property {number} count
 * @property {boolean} missed
 * @property {boolean} changed
 */

/**
 * Someone the user is related to (S10.10.6): stored, or worked out from those.
 * @typedef {Object} Relation
 * @property {string} personId
 * @property {string} name
 * @property {string} word
 * @property {boolean} stored
 */

/**
 * @typedef {Object} RelationOut
 * @property {string} personId
 * @property {string} name
 * @property {string} key
 * @property {string} word
 * @property {boolean} stored
 * @property {(string | null)} label
 */

/**
 * @typedef {Object} RelationshipIn
 * @property {string} person1Id
 * @property {string} person2Id
 * @property {string} relation
 * @property {(string | null)} [label]
 * @property {(string | null)} [fromDate]
 * @property {(string | null)} [toDate]
 */

/**
 * @typedef {Object} RelationshipOut
 * @property {string} id
 * @property {Named} person1
 * @property {Named} person2
 * @property {string} relation
 * @property {(string | null)} label
 * @property {(string | null)} fromDate
 * @property {(string | null)} toDate
 * @property {(string | null)} endsOn
 * @property {boolean} canChange
 * @property {number} version
 */

/**
 * @typedef {Object} RemoteUser
 * @property {string} id
 * @property {string} username
 * @property {string} displayName
 * @property {(string | null)} email
 */

/**
 * @typedef {Object} Reset
 * @property {string} date
 * @property {import('../app/dec.js').Dec} rate
 */

/**
 * @typedef {Object} ResetView
 * @property {string} date
 * @property {import('../app/dec.js').Dec} rate
 */

/**
 * @typedef {Object} ResidenceOut
 * @property {string} name
 * @property {string} sold
 * @property {import('../app/dec.js').Dec} gain
 * @property {import('../app/dec.js').Dec} yearsOwned
 */

/**
 * @typedef {Object} RetirementOut
 * @property {Array<moneykata__ui__taxpanels__ContributionOut>} contributions
 * @property {Array<Amount>} distributions
 * @property {Array<RmdOut>} rmds
 * @property {(import('../app/dec.js').Dec | null)} basis8606
 */

/**
 * @typedef {Object} ReturnRow
 * @property {string} id
 * @property {string} name
 * @property {Object<string, (string | null)>} periods
 */

/**
 * @typedef {Object} RmdOut
 * @property {string} account
 * @property {string} owner
 * @property {number} age
 * @property {import('../app/dec.js').Dec} balance
 * @property {import('../app/dec.js').Dec} factor
 * @property {import('../app/dec.js').Dec} due
 */

/**
 * @typedef {Object} RolloverOut
 * @property {(string | null)} possibleFrom
 * @property {import('../app/dec.js').Dec} limit
 * @property {import('../app/dec.js').Dec} used
 * @property {import('../app/dec.js').Dec} eligible
 * @property {import('../app/dec.js').Dec} available
 */

/**
 * @typedef {Object} Sale
 * @property {string} soldOn
 * @property {import('../app/dec.js').Dec} proceeds
 * @property {import('../app/dec.js').Dec} fees
 * @property {import('../app/dec.js').Dec} gain
 * @property {boolean} collectable
 * @property {boolean} deductible
 */

/**
 * @typedef {Object} SaleIn
 * @property {string} soldOn
 * @property {import('../app/dec.js').Dec} proceeds
 * @property {import('../app/dec.js').Dec} [fees]
 */

/**
 * @typedef {Object} Saved
 * @property {ShareView} view
 * @property {number} alsoShared
 */

/**
 * @typedef {Object} SavedPlan
 * @property {string} id
 * @property {string} name
 * @property {PlanView} inputs
 * @property {boolean} following
 * @property {(string | null)} followingSince
 * @property {string} createdAt
 * @property {number} version
 * @property {string} headline
 */

/**
 * @typedef {Object} SavedPlanIn
 * @property {string} name
 * @property {moneykata__ui__loans__PlanIn} inputs
 */

/**
 * @typedef {Object} ScheduleDOut
 * @property {Array<BoxTotal>} boxes
 * @property {import('../app/dec.js').Dec} shortTerm
 * @property {import('../app/dec.js').Dec} longTerm
 * @property {import('../app/dec.js').Dec} collectables
 * @property {import('../app/dec.js').Dec} carryoverShort
 * @property {import('../app/dec.js').Dec} carryoverLong
 * @property {import('../app/dec.js').Dec} net
 */

/**
 * @typedef {Object} Securable
 * @property {string} id
 * @property {string} name
 * @property {string} accountId
 * @property {string} accountName
 */

/**
 * @typedef {Object} SecuredLoan
 * @property {string} accountId
 * @property {string} name
 * @property {import('../app/dec.js').Dec} owed
 */

/**
 * @typedef {Object} Series
 * @property {Array<moneykata__ui__accounts__Point>} points
 * @property {string} asOf
 */

/**
 * @typedef {Object} SeriesPoint
 * @property {string} date
 * @property {import('../app/dec.js').Dec} value
 * @property {import('../app/dec.js').Dec} contributions
 * @property {(import('../app/dec.js').Dec | null)} benchmark
 */

/**
 * @typedef {Object} ServicerCheck
 * @property {string} date
 * @property {import('../app/dec.js').Dec} servicer
 * @property {import('../app/dec.js').Dec} computed
 * @property {import('../app/dec.js').Dec} difference
 */

/**
 * @typedef {Object} SessionInfo
 * @property {Me} user
 * @property {moneykata__ui__session__Household} household
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
 * @property {number} version
 */

/**
 * @typedef {Object} Settle
 * @property {string} how
 * @property {string} date
 * @property {(import('../app/dec.js').Dec | null)} [contracts]
 */

/**
 * @typedef {Object} Setup
 * @property {string} password
 * @property {string} email
 * @property {(string | null)} [displayName]
 * @property {(string | null)} [sex]
 */

/**
 * @typedef {Object} Share
 * @property {string} label
 * @property {import('../app/dec.js').Dec} amount
 */

/**
 * @typedef {Object} ShareSave
 * @property {Object<string, string>} [users]
 * @property {Object<string, string>} [groups]
 * @property {boolean} [shareAccountsToo]
 * @property {Object<string, boolean>} [receipts]
 */

/**
 * @typedef {Object} ShareView
 * @property {string} kind
 * @property {string} itemId
 * @property {string} itemName
 * @property {Array<UserGrant>} users
 * @property {Array<GroupGrant>} groups
 * @property {Array<LinkedPeople>} links
 * @property {Object<string, Array<string>>} hidden
 * @property {Array<AccountName>} accounts
 * @property {number} [version]
 */

/**
 * @typedef {Object} Shown
 * @property {boolean} shown
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
 * @property {(string | null)} [sex]
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
 * @typedef {Object} Size
 * @property {number} files
 * @property {number} bytes
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
 * @typedef {Object} SpendingOut
 * @property {number} year
 * @property {Array<PersonSpend>} byPerson
 * @property {Array<Amount>} byOccasion
 * @property {Array<Amount>} byYear
 * @property {Array<Flag>} flagged
 */

/**
 * @typedef {Object} SplitIn
 * @property {(string | null)} [categoryId]
 * @property {import('../app/dec.js').Dec} amount
 * @property {(string | null)} [memo]
 */

/**
 * Who the user is married to today, when they are a user here (S10.10.4.3).
 * @typedef {Object} Spouse
 * @property {string} id
 * @property {string} displayName
 * @property {(number | null)} birthYear
 */

/**
 * @typedef {Object} StatementIn
 * @property {string} periodStart
 * @property {string} periodEnd
 * @property {import('../app/dec.js').Dec} opening
 * @property {import('../app/dec.js').Dec} closing
 * @property {Array<StatementRowIn>} rows
 * @property {boolean} [acceptDifference]
 * @property {(number | null)} [part]
 * @property {(string | null)} [accountId]
 * @property {boolean} [leftOut]
 */

/**
 * @typedef {Object} StatementRowIn
 * @property {string} date
 * @property {string} description
 * @property {import('../app/dec.js').Dec} amount
 * @property {boolean} [include]
 */

/**
 * @typedef {Object} StorageOut
 * @property {number} databaseBytes
 * @property {number} receiptsBytes
 * @property {Size} expired
 * @property {Size} later
 * @property {Size} forever
 * @property {number} pruned
 * @property {Array<YearSizes>} byYear
 * @property {Array<CategorySize>} expiredBy
 * @property {(number | null)} keepStatementsYears
 */

/**
 * @typedef {Object} StudentOut
 * @property {string} name
 * @property {boolean} received1098T
 * @property {import('../app/dec.js').Dec} withdrawals529
 */

/**
 * A field read from the receipt, with how sure the reader was (0–100).
 * @typedef {Object} Suggested
 * @property {string} value
 * @property {number} confidence
 */

/**
 * @typedef {Object} Suggestion
 * @property {string} transactionId
 * @property {string} accountName
 * @property {string} date
 * @property {import('../app/dec.js').Dec} amount
 * @property {(string | null)} payee
 */

/**
 * @typedef {Object} Summary
 * @property {import('../app/dec.js').Dec} unrealized
 * @property {Array<Expiring>} expiringSoon
 * @property {import('../app/dec.js').Dec} realizedThisYear
 * @property {import('../app/dec.js').Dec} realizedShort
 * @property {import('../app/dec.js').Dec} realizedLong
 */

/**
 * @typedef {Object} Suspects
 * @property {Array<Array<string>>} duplicates
 * @property {Array<string>} changed
 * @property {Array<Array<string>>} gaps
 * @property {(string | null)} firstParting
 */

/**
 * @typedef {Object} SyncOut
 * @property {number} recorded
 * @property {WalletView} wallet
 */

/**
 * @typedef {Object} TagIn
 * @property {string} [contributor]
 * @property {boolean} [fiveYear]
 */

/**
 * @typedef {Object} TagOut
 * @property {string} tag
 * @property {string} label
 * @property {import('../app/dec.js').Dec} total
 * @property {number} count
 * @property {number} withReceipts
 */

/**
 * @typedef {Object} TaxChange
 * @property {number} year
 * @property {Object<string, unknown>} values
 */

/**
 * @typedef {Object} TaxRow
 * @property {string} key
 * @property {string} label
 * @property {string} kind
 * @property {string} group
 * @property {string} source
 * @property {unknown} value
 * @property {unknown} shipped
 * @property {boolean} corrected
 */

/**
 * @typedef {Object} TaxTables
 * @property {number} year
 * @property {Array<number>} years
 * @property {Array<TaxRow>} rows
 * @property {number} version
 */

/**
 * @typedef {Object} TermsIn
 * @property {import('../app/dec.js').Dec} principal
 * @property {string} startDate
 * @property {number} termMonths
 * @property {import('../app/dec.js').Dec} rate
 * @property {string} [method]
 * @property {(import('../app/dec.js').Dec | null)} [payment]
 * @property {(import('../app/dec.js').Dec | null)} [escrowTax]
 * @property {(import('../app/dec.js').Dec | null)} [escrowInsurance]
 * @property {(import('../app/dec.js').Dec | null)} [pmi]
 * @property {(number | null)} [drawMonths]
 * @property {Array<Reset>} [resets]
 * @property {Array<Recast>} [recasts]
 * @property {(import('../app/dec.js').Dec | null)} [originalValue]
 * @property {(string | null)} [securedById]
 */

/**
 * @typedef {Object} TermsOut
 * @property {import('../app/dec.js').Dec} principal
 * @property {string} startDate
 * @property {number} termMonths
 * @property {import('../app/dec.js').Dec} rate
 * @property {string} method
 * @property {(import('../app/dec.js').Dec | null)} payment
 * @property {(import('../app/dec.js').Dec | null)} escrowTax
 * @property {(import('../app/dec.js').Dec | null)} escrowInsurance
 * @property {(import('../app/dec.js').Dec | null)} pmi
 * @property {(number | null)} drawMonths
 * @property {Array<ResetView>} resets
 * @property {Array<RecastView>} recasts
 * @property {(import('../app/dec.js').Dec | null)} originalValue
 * @property {(string | null)} securedById
 * @property {import('../app/dec.js').Dec} computedPayment
 * @property {number} version
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
 * @typedef {Object} TokenItem
 * @property {string} kind
 * @property {string} id
 */

/**
 * @typedef {Object} TokenItemOut
 * @property {string} kind
 * @property {string} id
 * @property {string} name
 */

/**
 * @typedef {Object} TokenMade
 * @property {TokenOut} token
 * @property {string} secret
 */

/**
 * @typedef {Object} TokenOut
 * @property {string} id
 * @property {string} name
 * @property {string} scope
 * @property {Array<TokenItemOut>} items
 * @property {string} createdAt
 * @property {string} expiresAt
 * @property {(string | null)} lastUsedAt
 * @property {boolean} expired
 * @property {number} version
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
 * @typedef {Object} TrendPoint
 * @property {string} month
 * @property {import('../app/dec.js').Dec} planned
 * @property {import('../app/dec.js').Dec} actual
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
 * @property {(import('../app/dec.js').Dec | null)} [amount]
 * @property {(string | null)} [payee]
 * @property {(string | null)} [memo]
 * @property {(string | null)} [categoryId]
 * @property {(import('../app/dec.js').Dec | null)} [quantity]
 * @property {(import('../app/dec.js').Dec | null)} [price]
 * @property {(import('../app/dec.js').Dec | null)} [fees]
 * @property {(string | null)} [dividendType]
 * @property {(number | null)} [contributionYear]
 * @property {(string | null)} [contributionSource]
 * @property {(import('../app/dec.js').Dec | null)} [costBasis]
 * @property {(boolean | null)} [cleared]
 * @property {(Array<SplitIn> | null)} [splits]
 * @property {(Array<string> | null)} [tags]
 */

/**
 * @typedef {Object} TxnIn
 * @property {string} accountId
 * @property {string} date
 * @property {string} [kind]
 * @property {import('../app/dec.js').Dec} amount
 * @property {(string | null)} [payee]
 * @property {(string | null)} [memo]
 * @property {(string | null)} [categoryId]
 * @property {(string | null)} [instrumentId]
 * @property {(string | null)} [symbol]
 * @property {(import('../app/dec.js').Dec | null)} [quantity]
 * @property {(import('../app/dec.js').Dec | null)} [price]
 * @property {(import('../app/dec.js').Dec | null)} [fees]
 * @property {(string | null)} [dividendType]
 * @property {(import('../app/dec.js').Dec | null)} [splitRatio]
 * @property {(number | null)} [contributionYear]
 * @property {(string | null)} [contributionSource]
 * @property {(import('../app/dec.js').Dec | null)} [costBasis]
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
 * @property {import('../app/dec.js').Dec} amount
 * @property {(string | null)} payee
 * @property {(string | null)} payeeRaw
 * @property {(string | null)} memo
 * @property {(string | null)} categoryId
 * @property {(string | null)} instrumentId
 * @property {(string | null)} symbol
 * @property {(import('../app/dec.js').Dec | null)} quantity
 * @property {(import('../app/dec.js').Dec | null)} price
 * @property {(import('../app/dec.js').Dec | null)} fees
 * @property {(string | null)} dividendType
 * @property {(number | null)} contributionYear
 * @property {(string | null)} contributionSource
 * @property {(string | null)} transferId
 * @property {(string | null)} transferAccountName
 * @property {boolean} imported
 * @property {boolean} cleared
 * @property {boolean} reconciled
 * @property {(import('../app/dec.js').Dec | null)} amountWas
 * @property {Array<moneykata__ui__transactions__SplitOut>} splits
 * @property {Array<string>} tags
 * @property {number} receipts
 * @property {string} level
 * @property {number} version
 */

/**
 * @typedef {Object} TypedPrice
 * @property {string} date
 * @property {import('../app/dec.js').Dec} price
 */

/**
 * @typedef {Object} Unlock
 * @property {string} words
 */

/**
 * @typedef {Object} Unplanned
 * @property {string} categoryId
 * @property {string} label
 * @property {import('../app/dec.js').Dec} spent
 */

/**
 * @typedef {Object} UpcomingOut
 * @property {PersonRef} person
 * @property {string} key
 * @property {string} label
 * @property {string} date
 * @property {number} days
 * @property {(number | null)} turns
 * @property {boolean} inLead
 * @property {(import('../app/dec.js').Dec | null)} budget
 * @property {import('../app/dec.js').Dec} planned
 * @property {string} missing
 * @property {Array<GiftOut>} gifts
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
 * @typedef {Object} ValuationIn
 * @property {string} date
 * @property {import('../app/dec.js').Dec} value
 * @property {string} [source]
 * @property {(string | null)} [note]
 */

/**
 * @typedef {Object} ValuationOut
 * @property {string} id
 * @property {string} date
 * @property {import('../app/dec.js').Dec} value
 * @property {string} source
 * @property {(string | null)} note
 * @property {number} version
 */

/**
 * @typedef {Object} ValueCheckRow
 * @property {string} date
 * @property {import('../app/dec.js').Dec} reported
 * @property {import('../app/dec.js').Dec} computed
 * @property {import('../app/dec.js').Dec} difference
 * @property {boolean} ok
 */

/**
 * @typedef {Object} Via
 * @property {string} groupId
 * @property {string} groupName
 * @property {string} level
 */

/**
 * @typedef {Object} WalletAddressOut
 * @property {string} address
 * @property {string} keyId
 * @property {(number | null)} chain
 * @property {(number | null)} index
 * @property {boolean} used
 * @property {number} txCount
 * @property {number} balanceSats
 * @property {(string | null)} checkedAt
 */

/**
 * @typedef {Object} WalletIn
 * @property {string} text
 * @property {number} [gapLimit]
 */

/**
 * @typedef {Object} WalletKeyOut
 * @property {string} id
 * @property {string} kind
 * @property {string} value
 * @property {string} script
 * @property {number} gapLimit
 * @property {number} addresses
 * @property {number} used
 */

/**
 * @typedef {Object} WalletView
 * @property {Array<WalletKeyOut>} keys
 * @property {Array<WalletAddressOut>} addresses
 * @property {number} watched
 * @property {number} used
 * @property {number} balanceSats
 * @property {(string | null)} checkedAt
 * @property {number} version
 */

/**
 * @typedef {Object} WashOut
 * @property {string} sold
 * @property {string} symbol
 * @property {string} account
 * @property {import('../app/dec.js').Dec} loss
 * @property {import('../app/dec.js').Dec} disallowed
 * @property {string} replacedOn
 * @property {string} replacementAccount
 * @property {import('../app/dec.js').Dec} replacementQty
 * @property {(import('../app/dec.js').Dec | null)} adjustedBasis
 * @property {boolean} review
 */

/**
 * @typedef {Object} WithdrawalYearOut
 * @property {number} year
 * @property {import('../app/dec.js').Dec} distributions
 * @property {import('../app/dec.js').Dec} expenses
 * @property {import('../app/dec.js').Dec} notCovered
 */

/**
 * @typedef {Object} WithdrawalsView
 * @property {Array<WithdrawalYearOut>} years
 * @property {Array<ExpenseOut>} expenses
 * @property {Array<Array<unknown>>} kinds
 * @property {boolean} canWrite
 */

/**
 * @typedef {Object} Words
 * @property {Array<string>} words
 */

/**
 * @typedef {Object} YearPct
 * @property {number} year
 * @property {(import('../app/dec.js').Dec | null)} percent
 */

/**
 * @typedef {Object} YearSizes
 * @property {number} year
 * @property {Array<CategorySize>} categories
 */

/**
 * @typedef {Object} Zones
 * @property {string} server
 * @property {Array<string>} zones
 */

/**
 * @typedef {Object} moneykata__ui__accounts__Point
 * @property {string} date
 * @property {import('../app/dec.js').Dec} value
 */

/**
 * @typedef {Object} moneykata__ui__education__ContributionOut
 * @property {string} transactionId
 * @property {string} date
 * @property {import('../app/dec.js').Dec} amount
 * @property {string} contributor
 * @property {string} name
 * @property {(string | null)} relationship
 * @property {boolean} fiveYear
 * @property {number} [version]
 */

/**
 * @typedef {Object} moneykata__ui__education__DocumentIn
 * @property {string} receiptId
 */

/**
 * @typedef {Object} moneykata__ui__education__PlanIn
 * @property {(string | null)} [planState]
 * @property {(string | null)} [planName]
 * @property {(BeneficiaryRef | null)} [beneficiary]
 * @property {(string | null)} [openedOn]
 * @property {(import('../app/dec.js').Dec | null)} [stateDeduction]
 */

/**
 * @typedef {Object} moneykata__ui__education__PlanOut
 * @property {(string | null)} planState
 * @property {(string | null)} planName
 * @property {(BeneficiaryOut | null)} beneficiary
 * @property {(string | null)} openedOn
 * @property {(import('../app/dec.js').Dec | null)} stateDeduction
 * @property {import('../app/dec.js').Dec} contributedThisYear
 * @property {RolloverOut} rollover
 * @property {boolean} canWrite
 * @property {number} [version]
 */

/**
 * @typedef {Object} moneykata__ui__gifts__DocumentIn
 * @property {string} receiptId
 */

/**
 * A gift plan, and the person it is for: an existing one (`personId`) or a new one.
 * @typedef {Object} moneykata__ui__gifts__PersonIn
 * @property {(string | null)} [personId]
 * @property {string} [name]
 * @property {(string | null)} [sex]
 * @property {(number | null)} [birthMonth]
 * @property {(number | null)} [birthDay]
 * @property {(number | null)} [birthYear]
 * @property {(string | null)} [diedOn]
 * @property {(boolean | null)} [private]
 * @property {boolean} [differentPerson]
 * @property {(import('../app/dec.js').Dec | null)} [giftBudget]
 * @property {number} [leadDays]
 * @property {(string | null)} [notes]
 * @property {(Array<OccasionIn> | null)} [occasions]
 */

/**
 * @typedef {Object} moneykata__ui__giving__DocumentIn
 * @property {string} receiptId
 */

/**
 * @typedef {Object} moneykata__ui__giving__PlanIn
 * @property {number} year
 * @property {string} [targetKind]
 * @property {(import('../app/dec.js').Dec | null)} [percent]
 * @property {(import('../app/dec.js').Dec | null)} [amount]
 * @property {string} [incomeBasis]
 * @property {(import('../app/dec.js').Dec | null)} [income]
 * @property {string} [dafCounted]
 */

/**
 * @typedef {Object} moneykata__ui__giving__PlanOut
 * @property {string} id
 * @property {number} year
 * @property {string} targetKind
 * @property {(import('../app/dec.js').Dec | null)} percent
 * @property {(import('../app/dec.js').Dec | null)} amount
 * @property {string} incomeBasis
 * @property {(import('../app/dec.js').Dec | null)} income
 * @property {string} dafCounted
 * @property {string} level
 * @property {string} ownerName
 * @property {number} version
 */

/**
 * @typedef {Object} moneykata__ui__items__DocumentIn
 * @property {string} receiptId
 */

/**
 * @typedef {Object} moneykata__ui__linked__Household
 * @property {string} linkId
 * @property {string} colour
 * @property {(string | null)} serverName
 * @property {(string | null)} name
 * @property {(Object<string, unknown> | null)} avatar
 * @property {number} items
 * @property {(string | null)} syncedAt
 * @property {boolean} locked
 */

/**
 * @typedef {Object} moneykata__ui__links__LinkOut
 * @property {string} id
 * @property {string} state
 * @property {string} role
 * @property {(string | null)} peerName
 * @property {(string | null)} householdName
 * @property {(Object<string, unknown> | null)} householdAvatar
 * @property {(string | null)} address
 * @property {(string | null)} fingerprint
 * @property {(string | null)} peerVersion
 * @property {(string | null)} codeExpiresAt
 * @property {(string | null)} lastOkAt
 * @property {(string | null)} lastError
 * @property {(string | null)} failingSince
 * @property {string} createdAt
 * @property {(string | null)} endedAt
 * @property {Array<RemoteUser>} users
 * @property {(CopyOut | null)} [linkedCopy]
 * @property {Array<Incoming>} [incoming]
 */

/**
 * @typedef {Object} moneykata__ui__loans__PlanIn
 * @property {import('../app/dec.js').Dec} [monthly]
 * @property {(string | null)} [monthlyFrom]
 * @property {(string | null)} [monthlyUntil]
 * @property {import('../app/dec.js').Dec} [yearly]
 * @property {number} [yearlyMonth]
 * @property {Array<Lump>} [lumps]
 * @property {boolean} [biweekly]
 * @property {import('../app/dec.js').Dec} [roundTo]
 * @property {boolean} [recast]
 * @property {import('../app/dec.js').Dec} [recastFee]
 * @property {string} [investClass]
 */

/**
 * @typedef {Object} moneykata__ui__loans__Point
 * @property {string} date
 * @property {import('../app/dec.js').Dec} balance
 */

/**
 * @typedef {Object} moneykata__ui__loans__RowOut
 * @property {string} date
 * @property {import('../app/dec.js').Dec} payment
 * @property {import('../app/dec.js').Dec} principal
 * @property {import('../app/dec.js').Dec} interest
 * @property {import('../app/dec.js').Dec} escrow
 * @property {import('../app/dec.js').Dec} pmi
 * @property {import('../app/dec.js').Dec} balance
 * @property {boolean} past
 * @property {import('../app/dec.js').Dec} overpayment
 */

/**
 * @typedef {Object} moneykata__ui__loans__SplitOut
 * @property {import('../app/dec.js').Dec} principal
 * @property {import('../app/dec.js').Dec} interest
 * @property {import('../app/dec.js').Dec} escrowTax
 * @property {import('../app/dec.js').Dec} escrowInsurance
 * @property {import('../app/dec.js').Dec} pmi
 * @property {import('../app/dec.js').Dec} fees
 * @property {import('../app/dec.js').Dec} overpayment
 */

/**
 * @typedef {Object} moneykata__ui__people__PersonIn
 * @property {string} name
 * @property {(string | null)} [sex]
 * @property {(number | null)} [birthMonth]
 * @property {(number | null)} [birthDay]
 * @property {(number | null)} [birthYear]
 * @property {(string | null)} [diedOn]
 * @property {boolean} [private]
 * @property {boolean} [differentPerson]
 */

/**
 * @typedef {Object} moneykata__ui__prices__SecretSet
 * @property {string} setAt
 * @property {(string | null)} setBy
 */

/**
 * A transaction it supports, or (a statement) the account it is kept on.
 * @typedef {Object} moneykata__ui__receipts__LinkOut
 * @property {(string | null)} transactionId
 * @property {string} accountId
 * @property {string} accountName
 * @property {(string | null)} date
 * @property {(import('../app/dec.js').Dec | null)} amount
 * @property {(string | null)} payee
 */

/**
 * @typedef {Object} moneykata__ui__session__Household
 * @property {string} name
 * @property {Object<string, unknown>} avatar
 */

/**
 * A stored secret as the UI shows it: set, when and by whom.
 * @typedef {Object} moneykata__ui__settings__SecretSet
 * @property {string} setAt
 * @property {(string | null)} setBy
 */

/**
 * @typedef {Object} moneykata__ui__taxes__DocumentIn
 * @property {string} [direction]
 * @property {string} form
 * @property {(string | null)} [issuer]
 * @property {(string | null)} [accountId]
 * @property {(string | null)} [filingId]
 * @property {(string | null)} [receiptId]
 * @property {(string | null)} [notes]
 */

/**
 * @typedef {Object} moneykata__ui__taxpanels__ContributionOut
 * @property {string} account
 * @property {string} kind
 * @property {string} owner
 * @property {import('../app/dec.js').Dec} contributed
 * @property {(import('../app/dec.js').Dec | null)} limit
 * @property {boolean} over
 * @property {string} note
 */

/**
 * @typedef {Object} moneykata__ui__taxpanels__RowOut
 * @property {string} description
 * @property {(string | null)} acquired
 * @property {string} sold
 * @property {import('../app/dec.js').Dec} proceeds
 * @property {(import('../app/dec.js').Dec | null)} basis
 * @property {string} code
 * @property {import('../app/dec.js').Dec} adjustment
 * @property {(import('../app/dec.js').Dec | null)} gain
 * @property {boolean} longTerm
 * @property {string} box
 * @property {string} account
 * @property {boolean} collectable
 */

/**
 * @typedef {Object} moneykata__ui__transactions__SplitOut
 * @property {(string | null)} [categoryId]
 * @property {import('../app/dec.js').Dec} amount
 * @property {(string | null)} [memo]
 * @property {string} id
 */

export {};
