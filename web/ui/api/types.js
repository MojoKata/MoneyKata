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
 * @typedef {Object} Activated
 * @property {(string | null)} replaced
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
 * @property {string} amount
 */

/**
 * @typedef {Object} Approval
 * @property {Array<string>} [groupIds]
 */

/**
 * @typedef {Object} AssumptionsView
 * @property {Object<string, unknown>} figures
 * @property {Array<Array<unknown>>} classes
 * @property {Array<Array<unknown>>} bitcoinModels
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
 */

/**
 * @typedef {Object} BeneficiaryRef
 * @property {string} kind
 * @property {string} id
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
 */

/**
 * @typedef {Object} BoxTotal
 * @property {string} box
 * @property {string} proceeds
 * @property {string} basis
 * @property {string} adjustment
 * @property {string} gain
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
 * @property {string} amount
 * @property {(string | null)} payee
 */

/**
 * @typedef {Object} Carried
 * @property {((number | string) | null)} [agi]
 * @property {((number | string) | null)} [totalTax]
 * @property {((number | string) | null)} [overpaymentApplied]
 * @property {((number | string) | null)} [capitalLossShort]
 * @property {((number | string) | null)} [capitalLossLong]
 * @property {((number | string) | null)} [basis8606]
 * @property {((number | string) | null)} [charitableCarryover]
 */

/**
 * @typedef {Object} CarriedView
 * @property {(string | null)} [agi]
 * @property {(string | null)} [totalTax]
 * @property {(string | null)} [overpaymentApplied]
 * @property {(string | null)} [capitalLossShort]
 * @property {(string | null)} [capitalLossLong]
 * @property {(string | null)} [basis8606]
 * @property {(string | null)} [charitableCarryover]
 */

/**
 * @typedef {Object} CashFlow
 * @property {string} month
 * @property {Array<Flow>} sources
 * @property {Array<Flow>} uses
 * @property {string} income
 * @property {string} spending
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
 * @typedef {Object} ClosedRow
 * @property {(string | null)} saleId
 * @property {string} accountId
 * @property {string} accountName
 * @property {string} instrumentId
 * @property {string} symbol
 * @property {string} instrumentClass
 * @property {string} side
 * @property {string} quantity
 * @property {string} opened
 * @property {string} closed
 * @property {string} how
 * @property {string} proceeds
 * @property {(string | null)} cost
 * @property {(string | null)} realized
 * @property {string} term
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
 * @property {(number | string)} amount
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
 * @typedef {Object} CountIn
 * @property {(boolean | null)} counted
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
 * @property {((number | string) | null)} [amount]
 * @property {(string | null)} [description]
 * @property {(string | null)} [transactionId]
 * @property {(string | null)} [fromAccountId]
 * @property {(string | null)} [dafAccountId]
 * @property {(string | null)} [lotId]
 * @property {((number | string) | null)} [quantity]
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
 * @property {string} amount
 * @property {boolean} deductible
 * @property {boolean} counted
 * @property {boolean} needsAck
 * @property {boolean} acknowledged
 * @property {(string | null)} transactionId
 * @property {(string | null)} description
 * @property {(string | null)} symbol
 * @property {(string | null)} quantity
 * @property {(string | null)} basis
 * @property {(boolean | null)} longTerm
 * @property {(boolean | null)} granted
 * @property {(string | null)} notes
 * @property {boolean} canWrite
 */

/**
 * @typedef {Object} DonationRow
 * @property {string} date
 * @property {string} name
 * @property {string} kindLabel
 * @property {string} amount
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
 * @property {(string | null)} stateDeduction
 * @property {string} distributions
 * @property {string} expenses
 * @property {string} notCovered
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
 * @property {string} value
 * @property {string} owed
 * @property {string} equity
 * @property {string} ltv
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
 * @property {(number | string)} amount
 */

/**
 * @typedef {Object} ExpenseOut
 * @property {string} id
 * @property {string} date
 * @property {number} year
 * @property {string} kind
 * @property {string} kindLabel
 * @property {(string | null)} description
 * @property {string} amount
 * @property {Array<ReceiptRow>} documents
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
 * @property {((number | string) | null)} [resultAmount]
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
 * @property {(string | null)} resultAmount
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
 * @property {string} given
 * @property {string} exclusion
 */

/**
 * @typedef {Object} Flow
 * @property {string} name
 * @property {string} amount
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
 * @property {string} expected
 * @property {string} actual
 * @property {string} ahead
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
 * @property {string} balance
 * @property {string} contributed
 * @property {string} granted
 */

/**
 * @typedef {Object} GainGroup
 * @property {string} key
 * @property {string} label
 * @property {string} shortTerm
 * @property {string} longTerm
 * @property {string} total
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
 * @property {((number | string) | null)} [cost]
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
 * @property {(string | null)} cost
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
 * @property {string} given
 * @property {string} exclusion
 */

/**
 * @typedef {Object} GiftYearOut
 * @property {string} contributor
 * @property {string} name
 * @property {number} year
 * @property {string} counted
 * @property {string} exclusion
 * @property {boolean} over
 * @property {(number | null)} fromElection
 */

/**
 * @typedef {Object} GivingOut
 * @property {Array<DonationRow>} deductible
 * @property {Array<DonationRow>} apart
 * @property {string} deductibleTotal
 * @property {number} missingAcks
 * @property {Array<string>} notes
 */

/**
 * @typedef {Object} GivingView
 * @property {number} year
 * @property {(moneykata__ui__giving__PlanOut | null)} plan
 * @property {string} income
 * @property {string} target
 * @property {string} given
 * @property {string} pace
 * @property {string} pledged
 * @property {string} projected
 * @property {Array<string>} byMonth
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
 * @typedef {Object} HolidayOut
 * @property {string} key
 * @property {string} label
 * @property {(string | null)} date
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
 * @typedef {Object} ImprovementIn
 * @property {string} date
 * @property {string} description
 * @property {(number | string)} amount
 */

/**
 * @typedef {Object} ImprovementOut
 * @property {string} id
 * @property {string} date
 * @property {string} description
 * @property {string} amount
 */

/**
 * @typedef {Object} IncomeOut
 * @property {Array<Amount>} interest
 * @property {string} interestTotal
 * @property {string} ordinary
 * @property {string} qualified
 * @property {string} capitalGainDistributions
 * @property {string} returnOfCapital
 * @property {Array<Amount>} dividendsByPayer
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
 * @property {number} rate
 * @property {string} contributed
 * @property {string} value
 * @property {string} gain
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
 * @property {string} quantity
 * @property {string} valuation
 * @property {(string | null)} metal
 * @property {(string | null)} fineOunces
 * @property {string} basis
 * @property {string} value
 * @property {string} gain
 * @property {number} years
 * @property {(ValuationOut | null)} latest
 * @property {boolean} stale
 * @property {(Sale | null)} sale
 * @property {Array<SecuredLoan>} loans
 * @property {(string | null)} equity
 * @property {number} version
 * @property {(string | null)} description
 * @property {string} costBasis
 * @property {(string | null)} location
 * @property {(string | null)} serial
 * @property {(string | null)} condition
 * @property {(string | null)} insuredValue
 * @property {(string | null)} policy
 * @property {(string | null)} notes
 * @property {(string | null)} unitWeight
 * @property {(string | null)} weightUnit
 * @property {(string | null)} purity
 * @property {string} sellPremium
 * @property {(string | null)} depreciationRate
 * @property {(string | null)} address
 * @property {(string | null)} closingCosts
 * @property {boolean} primaryResidence
 * @property {boolean} personalUse
 * @property {(string | null)} spot
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
 * @property {(number | string)} costBasis
 * @property {(number | string)} [quantity]
 * @property {(string | null)} [location]
 * @property {(string | null)} [serial]
 * @property {(string | null)} [condition]
 * @property {((number | string) | null)} [insuredValue]
 * @property {(string | null)} [policy]
 * @property {(string | null)} [notes]
 * @property {string} [valuation]
 * @property {(string | null)} [metal]
 * @property {((number | string) | null)} [unitWeight]
 * @property {(string | null)} [weightUnit]
 * @property {(string | null)} [purity]
 * @property {(number | string)} [sellPremium]
 * @property {((number | string) | null)} [depreciationRate]
 * @property {(string | null)} [address]
 * @property {((number | string) | null)} [closingCosts]
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
 * @property {string} quantity
 * @property {string} valuation
 * @property {(string | null)} metal
 * @property {(string | null)} fineOunces
 * @property {string} basis
 * @property {string} value
 * @property {string} gain
 * @property {number} years
 * @property {(ValuationOut | null)} latest
 * @property {boolean} stale
 * @property {(Sale | null)} sale
 * @property {Array<SecuredLoan>} loans
 * @property {(string | null)} equity
 * @property {number} version
 */

/**
 * @typedef {Object} ItemsView
 * @property {Array<ItemRow>} items
 * @property {Array<MetalOut>} metals
 * @property {string} value
 * @property {string} basis
 * @property {string} gain
 * @property {boolean} canWrite
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
 * @typedef {Object} LastYear
 * @property {string} filing
 * @property {CarriedView} figures
 */

/**
 * A transaction it supports, or (a statement) the account it is kept on.
 * @typedef {Object} LinkOut
 * @property {(string | null)} transactionId
 * @property {string} accountId
 * @property {string} accountName
 * @property {(string | null)} date
 * @property {(string | null)} amount
 * @property {(string | null)} payee
 */

/**
 * @typedef {Object} LoanOut
 * @property {string} account
 * @property {string} form
 * @property {string} interest
 * @property {string} pmi
 * @property {string} propertyTax
 * @property {(string | null)} securedBy
 */

/**
 * @typedef {Object} LoanView
 * @property {(TermsOut | null)} terms
 * @property {string} balance
 * @property {string} rate
 * @property {string} payment
 * @property {string} total
 * @property {(string | null)} nextDate
 * @property {(string | null)} payoffDate
 * @property {(string | null)} originalPayoff
 * @property {string} interestPaid
 * @property {string} interestAhead
 * @property {string} principalThisYear
 * @property {string} overpaid
 * @property {Array<moneykata__ui__loans__RowOut>} rows
 * @property {(ServicerCheck | null)} servicer
 * @property {(Equity | null)} [equity]
 * @property {(Following | null)} [following]
 * @property {boolean} canWrite
 */

/**
 * @typedef {Object} Login
 * @property {string} login
 */

/**
 * @typedef {Object} LotOut
 * @property {string} acquiredOn
 * @property {string} quantity
 * @property {(string | null)} basis
 * @property {number} days
 * @property {boolean} longTerm
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
 * @typedef {Object} Lump
 * @property {string} date
 * @property {(number | string)} amount
 */

/**
 * @typedef {Object} LumpView
 * @property {string} date
 * @property {string} amount
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
 * @property {string} ounces
 * @property {string} cost
 * @property {(string | null)} averageCost
 * @property {(string | null)} spot
 * @property {(string | null)} spotAsOf
 * @property {string} value
 * @property {string} gain
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
 * @property {(number | null)} price
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
 * @property {string} planned
 * @property {string} carried
 * @property {string} actual
 * @property {string} remaining
 * @property {string} state
 */

/**
 * @typedef {Object} MonthView
 * @property {string} month
 * @property {Array<MonthRow>} rows
 * @property {Array<Unplanned>} unplanned
 * @property {string} income
 * @property {string} expectedIncome
 * @property {string} spent
 * @property {string} plannedSpending
 * @property {number} uncategorised
 * @property {number} daysLeft
 * @property {boolean} canWrite
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
 * @property {(boolean | null)} [countInNetWorth]
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
 * @typedef {Object} NewBook
 * @property {number} year
 * @property {Array<string>} filers
 * @property {boolean} [fromLastYear]
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
 * @property {((number | string) | null)} [budget]
 */

/**
 * @typedef {Object} OccasionOut
 * @property {string} kind
 * @property {(string | null)} [name]
 * @property {(string | null)} [holiday]
 * @property {(number | null)} [month]
 * @property {(number | null)} [day]
 * @property {(number | null)} [year]
 * @property {(string | null)} [budget]
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
 * @property {string} quantity
 * @property {(string | null)} cost
 * @property {(string | null)} averageCost
 * @property {(string | null)} value
 * @property {(string | null)} unrealized
 * @property {(number | null)} unrealizedPct
 * @property {string} realized
 * @property {string} term
 * @property {number} days
 * @property {Array<LotOut>} lots
 */

/**
 * @typedef {Object} OptionTrade
 * @property {string} date
 * @property {string} action
 * @property {string} underlying
 * @property {string} right
 * @property {(number | string)} strike
 * @property {string} expiry
 * @property {(number | string)} contracts
 * @property {(number | string)} premium
 * @property {(number | string)} [fees]
 * @property {number} [multiplier]
 */

/**
 * @typedef {Object} OrganisationIn
 * @property {string} name
 * @property {(string | null)} [ein]
 * @property {boolean} [deductible]
 * @property {Array<string>} [causes]
 * @property {((number | string) | null)} [pledge]
 * @property {(string | null)} [pledgeEvery]
 * @property {(string | null)} [notes]
 */

/**
 * @typedef {Object} OrganisationOut
 * @property {string} name
 * @property {(string | null)} [ein]
 * @property {boolean} [deductible]
 * @property {Array<string>} [causes]
 * @property {(string | null)} [pledge]
 * @property {(string | null)} [pledgeEvery]
 * @property {(string | null)} [notes]
 * @property {string} id
 * @property {string} given
 * @property {boolean} canWrite
 * @property {number} version
 */

/**
 * @typedef {Object} OutcomeOut
 * @property {(string | null)} payoffDate
 * @property {number} months
 * @property {string} interest
 * @property {string} paid
 * @property {string} payment
 * @property {string} paymentAfter
 * @property {string} fees
 * @property {number} monthsSaved
 * @property {string} interestSaved
 * @property {Array<moneykata__ui__loans__Point>} balances
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
 * @typedef {Object} Paid
 * @property {string} transactionId
 * @property {string} date
 * @property {string} amount
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
 * @property {Array<Quarter>} estimated
 * @property {(string | null)} lastYearTax
 * @property {GivingOut} giving
 * @property {Array<EducationOut>} education
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
 * @property {(number | string)} amount
 * @property {(string | null)} [paidOn]
 * @property {(string | null)} [transactionId]
 */

/**
 * @typedef {Object} PaymentIn
 * @property {string} date
 * @property {(number | string)} amount
 * @property {(string | null)} [fromAccountId]
 * @property {(string | null)} [transactionId]
 * @property {((number | string) | null)} [principal]
 * @property {((number | string) | null)} [interest]
 * @property {((number | string) | null)} [escrowTax]
 * @property {((number | string) | null)} [escrowInsurance]
 * @property {((number | string) | null)} [pmi]
 * @property {((number | string) | null)} [fees]
 */

/**
 * A payment as shown; its own model, so the contract has one schema each way.
 * @typedef {Object} PaymentView
 * @property {(string | null)} id
 * @property {number} quarter
 * @property {(string | null)} dueDate
 * @property {string} amount
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
 * @typedef {Object} Person
 * @property {string} id
 * @property {string} displayName
 */

/**
 * @typedef {Object} PersonIn
 * @property {string} name
 * @property {(string | null)} [relationship]
 * @property {(string | null)} [userId]
 * @property {(number | null)} [birthMonth]
 * @property {(number | null)} [birthDay]
 * @property {(number | null)} [birthYear]
 * @property {((number | string) | null)} [giftBudget]
 * @property {number} [leadDays]
 * @property {(string | null)} [notes]
 * @property {(Array<OccasionIn> | null)} [occasions]
 */

/**
 * @typedef {Object} PersonOut
 * @property {string} id
 * @property {string} name
 * @property {(string | null)} relationship
 * @property {(string | null)} userId
 * @property {(string | null)} userName
 * @property {(number | null)} birthMonth
 * @property {(number | null)} birthDay
 * @property {(number | null)} birthYear
 * @property {(string | null)} giftBudget
 * @property {number} leadDays
 * @property {(string | null)} notes
 * @property {Array<OccasionOut>} occasions
 * @property {(NextDate | null)} next
 * @property {string} spent
 * @property {(string | null)} lastGift
 * @property {string} level
 * @property {string} ownerName
 * @property {number} version
 */

/**
 * @typedef {Object} PersonRef
 * @property {string} id
 * @property {string} name
 */

/**
 * @typedef {Object} PersonSpend
 * @property {PersonRef} person
 * @property {string} spent
 * @property {(string | null)} budget
 */

/**
 * @typedef {Object} PickIn
 * @property {string} lotId
 * @property {(number | string)} quantity
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
 * @property {(number | string)} amount
 * @property {string} [cadence]
 * @property {boolean} [rollover]
 */

/**
 * The inputs as saved; its own models, so the contract has one schema for each direction.
 * @typedef {Object} PlanView
 * @property {string} monthly
 * @property {(string | null)} monthlyFrom
 * @property {(string | null)} monthlyUntil
 * @property {string} yearly
 * @property {number} yearlyMonth
 * @property {Array<LumpView>} lumps
 * @property {boolean} biweekly
 * @property {string} roundTo
 * @property {boolean} recast
 * @property {string} recastFee
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
 * @typedef {Object} Purchase
 * @property {string} transactionId
 * @property {string} date
 * @property {string} amount
 * @property {(string | null)} payee
 * @property {string} accountName
 * @property {(string | null)} category
 */

/**
 * @typedef {Object} Quarter
 * @property {string} jurisdiction
 * @property {number} quarter
 * @property {string} amount
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
 * @property {(number | string)} [fee]
 */

/**
 * @typedef {Object} RecastView
 * @property {string} date
 * @property {string} fee
 */

/**
 * @typedef {Object} ReceiptChange
 * @property {(string | null)} [date]
 * @property {((number | string) | null)} [amount]
 * @property {(string | null)} [payee]
 * @property {(string | null)} [notes]
 * @property {(Array<string> | null)} [tags]
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
 * @property {(string | null)} amount
 * @property {(string | null)} payee
 * @property {(string | null)} notes
 * @property {Array<string>} tags
 * @property {Array<LinkOut>} links
 * @property {boolean} hasThumbnail
 * @property {string} readStatus
 * @property {(string | null)} readError
 * @property {Array<string>} filled
 * @property {number} version
 * @property {Array<Suggestion>} matches
 * @property {(string | null)} text
 * @property {Object<string, Suggested>} suggested
 * @property {(string | null)} readMethod
 * @property {(string | null)} readEngine
 * @property {(string | null)} readAt
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
 * @property {(string | null)} amount
 * @property {(string | null)} payee
 * @property {(string | null)} notes
 * @property {Array<string>} tags
 * @property {Array<LinkOut>} links
 * @property {boolean} hasThumbnail
 * @property {string} readStatus
 * @property {(string | null)} readError
 * @property {Array<string>} filled
 * @property {number} version
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
 * @typedef {Object} RecurringRow
 * @property {string} payee
 * @property {string} accountId
 * @property {string} accountName
 * @property {string} every
 * @property {string} last
 * @property {string} next
 * @property {string} usual
 * @property {string} lastAmount
 * @property {number} count
 * @property {boolean} missed
 * @property {boolean} changed
 */

/**
 * @typedef {Object} Reset
 * @property {string} date
 * @property {(number | string)} rate
 */

/**
 * @typedef {Object} ResetView
 * @property {string} date
 * @property {string} rate
 */

/**
 * @typedef {Object} ResidenceOut
 * @property {string} name
 * @property {string} sold
 * @property {string} gain
 * @property {number} yearsOwned
 */

/**
 * @typedef {Object} RetirementOut
 * @property {Array<moneykata__ui__taxpanels__ContributionOut>} contributions
 * @property {Array<Amount>} distributions
 * @property {Array<RmdOut>} rmds
 * @property {(string | null)} basis8606
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
 * @property {string} balance
 * @property {number} factor
 * @property {string} due
 */

/**
 * @typedef {Object} RolloverOut
 * @property {(string | null)} possibleFrom
 * @property {string} limit
 * @property {string} used
 * @property {string} eligible
 * @property {string} available
 */

/**
 * @typedef {Object} Sale
 * @property {string} soldOn
 * @property {string} proceeds
 * @property {string} fees
 * @property {string} gain
 * @property {boolean} collectable
 * @property {boolean} deductible
 */

/**
 * @typedef {Object} SaleIn
 * @property {string} soldOn
 * @property {(number | string)} proceeds
 * @property {(number | string)} [fees]
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
 * @property {string} shortTerm
 * @property {string} longTerm
 * @property {string} collectables
 * @property {string} carryoverShort
 * @property {string} carryoverLong
 * @property {string} net
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
 * @property {string} owed
 */

/**
 * @typedef {Object} Series
 * @property {Array<moneykata__ui__accounts__Point>} points
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
 * @typedef {Object} ServicerCheck
 * @property {string} date
 * @property {string} servicer
 * @property {string} computed
 * @property {string} difference
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
 * @typedef {Object} Share
 * @property {string} label
 * @property {string} amount
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
 * @property {(number | string)} amount
 * @property {(string | null)} [memo]
 */

/**
 * @typedef {Object} StatementIn
 * @property {string} periodStart
 * @property {string} periodEnd
 * @property {(number | string)} opening
 * @property {(number | string)} closing
 * @property {Array<StatementRowIn>} rows
 * @property {boolean} [acceptDifference]
 */

/**
 * @typedef {Object} StatementRowIn
 * @property {string} date
 * @property {string} description
 * @property {(number | string)} amount
 * @property {boolean} [include]
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
 * @property {string} amount
 * @property {(string | null)} payee
 */

/**
 * @typedef {Object} Summary
 * @property {string} unrealized
 * @property {string} realizedThisYear
 * @property {string} realizedShort
 * @property {string} realizedLong
 */

/**
 * @typedef {Object} Suspects
 * @property {Array<Array<string>>} duplicates
 * @property {Array<string>} changed
 * @property {Array<Array<string>>} gaps
 * @property {(string | null)} firstParting
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
 * @property {string} total
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
 */

/**
 * @typedef {Object} TermsIn
 * @property {(number | string)} principal
 * @property {string} startDate
 * @property {number} termMonths
 * @property {(number | string)} rate
 * @property {string} [method]
 * @property {((number | string) | null)} [payment]
 * @property {((number | string) | null)} [escrowTax]
 * @property {((number | string) | null)} [escrowInsurance]
 * @property {((number | string) | null)} [pmi]
 * @property {(number | null)} [drawMonths]
 * @property {Array<Reset>} [resets]
 * @property {Array<Recast>} [recasts]
 * @property {((number | string) | null)} [originalValue]
 * @property {(string | null)} [securedById]
 */

/**
 * @typedef {Object} TermsOut
 * @property {string} principal
 * @property {string} startDate
 * @property {number} termMonths
 * @property {string} rate
 * @property {string} method
 * @property {(string | null)} payment
 * @property {(string | null)} escrowTax
 * @property {(string | null)} escrowInsurance
 * @property {(string | null)} pmi
 * @property {(number | null)} drawMonths
 * @property {Array<ResetView>} resets
 * @property {Array<RecastView>} recasts
 * @property {(string | null)} originalValue
 * @property {(string | null)} securedById
 * @property {string} computedPayment
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
 * @property {string} planned
 * @property {string} actual
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
 * @property {Array<moneykata__ui__transactions__SplitOut>} splits
 * @property {Array<string>} tags
 * @property {number} receipts
 * @property {string} level
 * @property {number} version
 */

/**
 * @typedef {Object} TypedPrice
 * @property {string} date
 * @property {(number | string)} price
 */

/**
 * @typedef {Object} Unplanned
 * @property {string} categoryId
 * @property {string} label
 * @property {string} spent
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
 * @property {(string | null)} budget
 * @property {string} planned
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
 * @property {(number | string)} value
 * @property {string} [source]
 * @property {(string | null)} [note]
 */

/**
 * @typedef {Object} ValuationOut
 * @property {string} id
 * @property {string} date
 * @property {string} value
 * @property {string} source
 * @property {(string | null)} note
 */

/**
 * @typedef {Object} Via
 * @property {string} groupId
 * @property {string} groupName
 * @property {string} level
 */

/**
 * @typedef {Object} WashOut
 * @property {string} sold
 * @property {string} symbol
 * @property {string} account
 * @property {string} loss
 * @property {string} disallowed
 * @property {string} replacedOn
 * @property {string} replacementAccount
 * @property {string} replacementQty
 * @property {(string | null)} adjustedBasis
 */

/**
 * @typedef {Object} WithdrawalYearOut
 * @property {number} year
 * @property {string} distributions
 * @property {string} expenses
 * @property {string} notCovered
 */

/**
 * @typedef {Object} WithdrawalsView
 * @property {Array<WithdrawalYearOut>} years
 * @property {Array<ExpenseOut>} expenses
 * @property {Array<Array<unknown>>} kinds
 * @property {boolean} canWrite
 */

/**
 * @typedef {Object} YearPct
 * @property {number} year
 * @property {(number | null)} percent
 */

/**
 * @typedef {Object} Zones
 * @property {string} server
 * @property {Array<string>} zones
 */

/**
 * @typedef {Object} moneykata__ui__accounts__Point
 * @property {string} date
 * @property {string} value
 */

/**
 * @typedef {Object} moneykata__ui__education__ContributionOut
 * @property {string} transactionId
 * @property {string} date
 * @property {string} amount
 * @property {string} contributor
 * @property {string} name
 * @property {(string | null)} relationship
 * @property {boolean} fiveYear
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
 * @property {((number | string) | null)} [stateDeduction]
 */

/**
 * @typedef {Object} moneykata__ui__education__PlanOut
 * @property {(string | null)} planState
 * @property {(string | null)} planName
 * @property {(BeneficiaryOut | null)} beneficiary
 * @property {(string | null)} openedOn
 * @property {(string | null)} stateDeduction
 * @property {string} contributedThisYear
 * @property {RolloverOut} rollover
 * @property {boolean} canWrite
 */

/**
 * @typedef {Object} moneykata__ui__gifts__DocumentIn
 * @property {string} receiptId
 */

/**
 * @typedef {Object} moneykata__ui__giving__DocumentIn
 * @property {string} receiptId
 */

/**
 * @typedef {Object} moneykata__ui__giving__PlanIn
 * @property {number} year
 * @property {string} [targetKind]
 * @property {((number | string) | null)} [percent]
 * @property {((number | string) | null)} [amount]
 * @property {string} [incomeBasis]
 * @property {((number | string) | null)} [income]
 * @property {string} [dafCounted]
 */

/**
 * @typedef {Object} moneykata__ui__giving__PlanOut
 * @property {string} id
 * @property {number} year
 * @property {string} targetKind
 * @property {(string | null)} percent
 * @property {(string | null)} amount
 * @property {string} incomeBasis
 * @property {(string | null)} income
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
 * @typedef {Object} moneykata__ui__loans__PlanIn
 * @property {(number | string)} [monthly]
 * @property {(string | null)} [monthlyFrom]
 * @property {(string | null)} [monthlyUntil]
 * @property {(number | string)} [yearly]
 * @property {number} [yearlyMonth]
 * @property {Array<Lump>} [lumps]
 * @property {boolean} [biweekly]
 * @property {(number | string)} [roundTo]
 * @property {boolean} [recast]
 * @property {(number | string)} [recastFee]
 * @property {string} [investClass]
 */

/**
 * @typedef {Object} moneykata__ui__loans__Point
 * @property {string} date
 * @property {string} balance
 */

/**
 * @typedef {Object} moneykata__ui__loans__RowOut
 * @property {string} date
 * @property {string} payment
 * @property {string} principal
 * @property {string} interest
 * @property {string} escrow
 * @property {string} pmi
 * @property {string} balance
 * @property {boolean} past
 * @property {string} overpayment
 */

/**
 * @typedef {Object} moneykata__ui__loans__SplitOut
 * @property {string} principal
 * @property {string} interest
 * @property {string} escrowTax
 * @property {string} escrowInsurance
 * @property {string} pmi
 * @property {string} fees
 * @property {string} overpayment
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
 * @property {string} contributed
 * @property {(string | null)} limit
 * @property {boolean} over
 * @property {string} note
 */

/**
 * @typedef {Object} moneykata__ui__taxpanels__RowOut
 * @property {string} description
 * @property {(string | null)} acquired
 * @property {string} sold
 * @property {string} proceeds
 * @property {(string | null)} basis
 * @property {string} code
 * @property {string} adjustment
 * @property {(string | null)} gain
 * @property {boolean} longTerm
 * @property {string} box
 * @property {string} account
 * @property {boolean} collectable
 */

/**
 * @typedef {Object} moneykata__ui__transactions__SplitOut
 * @property {(string | null)} [categoryId]
 * @property {string} amount
 * @property {(string | null)} [memo]
 * @property {string} id
 */

export {};
