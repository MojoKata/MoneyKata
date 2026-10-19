# Terms

The acronyms the guides use (requirements S12.7.7). Each heading is an acronym and what it
stands for; the paragraph under it, a sentence or two of plain text, says what it means. A
guide's acronym shows both on hover or keyboard focus, the first time it appears under each
heading. Kept in alphabetical order; a test fails when a guide uses an acronym missing here.

## AGI: Adjusted Gross Income

Your total income less certain adjustments, such as deductible IRA and HSA contributions. It is
on the first page of Form 1040, and many deductions, credits and limits are measured against it.

## API: Application Programming Interface

The requests a program accepts from other programs, as its buttons are for people. A key or
token decides what another program may ask for.

## APR: Annual Percentage Rate

A loan's or card's yearly cost of borrowing, as a percentage. A loan's includes some fees on top
of the interest rate; a card charges interest from it, usually daily.

## BIP39: Bitcoin Improvement Proposal 39

A standard list of 2,048 short words for recovery phrases. Each word carries 11 bits, and the
last word also carries a short checksum that catches most mistyped words.

## BTC: Bitcoin

Bitcoin's ticker symbol. One BTC is 100,000,000 satoshis, or sats.

## CD: Certificate of Deposit

Money deposited at a bank for a fixed term at a fixed rate. Taking it out before it matures
usually costs a penalty, often a few months' interest.

## CSV: Comma-Separated Values

A table written as plain text: one row per line, its columns split by commas. Each institution
chooses its own columns, so an import maps them once.

## DAF: Donor-Advised Fund

A giving account held by a sponsoring charity, such as Fidelity Charitable. You deduct a
contribution the year you make it, then recommend grants from it to charities over time.

## EIN: Employer Identification Number

The nine-digit number the IRS gives a business or a charity, written 12-3456789. It identifies
an organisation on tax forms as a Social Security number does a person.

## ETF: Exchange-Traded Fund

A fund that trades on an exchange like a stock, priced throughout the day. Most follow an index,
such as VT for the world's stocks.

## FID: Financial Institution ID

The id, up to 32 letters and digits, that identifies a bank or broker to OFX servers. It is sent
with the institution's ORG when signing in, and both come from the OFX directory.

## FIFO: First In, First Out

Sells the oldest shares first. It is the IRS's default when you don't name the lots you sold.

## HEIC: High Efficiency Image Container

The format iPhones save photos in by default: smaller than a JPEG of the same quality.

## HELOC: Home Equity Line of Credit

A revolving loan secured by your home. During the draw period you borrow up to a limit and pay
interest on what's drawn; after it, the balance is repaid over the repayment period.

## HIFO: Highest In, First Out

Sells the shares that cost the most first, which usually makes the smallest gain or the largest
loss.

## HSA: Health Savings Account

An account paired with a high-deductible health plan. Contributions are deductible, growth isn't
taxed, and withdrawals for medical costs are tax-free.

## IRA: Individual Retirement Account

A retirement account you open yourself, outside an employer's plan; the IRS calls it an
individual retirement arrangement. A traditional IRA's contributions may be deductible and its
withdrawals are taxed; a Roth IRA's are taxed going in and come out tax-free in retirement.

## IRC: Internal Revenue Code

The US federal tax law, Title 26 of the United States Code. Its sections, such as §1091 on wash
sales, are cited for the rules MoolaKata follows.

## IRR: Internal Rate of Return

The yearly rate that makes your deposits, withdrawals and ending value balance out. It measures
how your money did, counting when you added it or took it out.

## IRS: Internal Revenue Service

The US federal tax agency. Its forms, limits and tables are the ones MoolaKata's tax figures
follow.

## LAN: Local Area Network

The network in your home or office: the devices behind your router, which reach each other but
can't be reached from the internet.

## LIFO: Last In, First Out

Sells the newest shares first. Shares bought lately are often held under a year, so their gains
are short-term.

## MAGI: Modified Adjusted Gross Income

AGI with certain deductions and exclusions added back; each rule that uses it says which. It
decides who may contribute to a Roth IRA and who may deduct a traditional IRA contribution.

## MCP: Model Context Protocol

An open standard that lets an AI assistant use outside tools and data. MoolaKata's MCP endpoint
lets an assistant read what its token allows.

## MS: Mint State

A grade for a coin that never circulated, from MS-60 to a flawless MS-70 on the 70-point
Sheldon scale. Dealers commonly call MS-65 Gem Uncirculated.

## NAV: Net Asset Value

A fund's value per share: what it holds less what it owes, divided by its shares. Mutual funds
are bought and sold at the NAV struck after each day's close.

## OCC: Options Clearing Corporation

The clearinghouse behind every US-listed option. When a company splits, merges or pays a large
special dividend, it adjusts the open contracts and says how in an information memo.

## OCR: Optical Character Recognition

Reading the text in a photo or a scanned page, so a receipt's date, total and merchant can be
filled in for you.

## OFX: Open Financial Exchange

The standard file format banks and brokers use for downloads and direct connections. Each
transaction carries an id of its own, so importing the same file again adds only what's new.

## ORG: Organisation

The name that identifies a bank or broker to OFX servers, sent with its FID when signing in.
Both come from the OFX directory.

## PCGS: Professional Coin Grading Service

A company that grades coins and seals each in a labelled holder. Its grade, such as PCGS MS-64,
moves a coin's value.

## PMI: Private Mortgage Insurance

Insurance a lender usually requires when a conventional mortgage is more than 80% of the home's
value. It protects the lender, and ends when the balance is scheduled to reach 78% of the
original value, or from 80% if you ask.

## QCD: Qualified Charitable Distribution

A gift paid straight from an IRA to a charity, allowed from age 70½. It counts toward that
year's RMD and is left out of your income.

## QFX: Quicken Financial Exchange

Quicken's version of OFX, with a few fields of its own. MoolaKata reads it as OFX.

## RMD: Required Minimum Distribution

The least you must withdraw each year from traditional IRAs and most workplace plans, from age
73 (75 if born in 1960 or later). It is last year-end's balance divided by an IRS life-expectancy
factor.

## RPC: Remote Procedure Call

A way for one program to ask another, over the network, to run a command for it. Bitcoin Core
takes requests this way, with a user and password of its own.

## SHA: Secure Hash Algorithm

A family of functions that turn any data into a short fingerprint; SHA-256's is 64 hex digits.
Matching fingerprints mean the same certificate or file.

## SMTP: Simple Mail Transfer Protocol

How email is sent between servers. MoolaKata hands its mail to your provider's SMTP server,
which delivers it.

## TLS: Transport Layer Security

The encryption behind https: it keeps a connection private and proves, with a certificate,
which server you reached.

## TOTP: Time-based One-Time Password

A code, usually six digits, that an authenticator app works out from a shared key and the time,
new every 30 seconds.

## TXF: Tax Exchange Format

A plain-text file of tax figures that TurboTax, H&R Block and other tax programs import.

## UTC: Coordinated Universal Time

The world's reference clock, with no time zones or daylight saving. Midnight UTC is 7 or 8 in
the evening before, US Eastern time.

## VIN: Vehicle Identification Number

The 17-character code on a vehicle's dashboard and title that identifies that one vehicle. It
decodes to its maker, model and year.

## WIF: Wallet Import Format

A way of writing one bitcoin private key as text, starting with 5, K or L, so a wallet can
import it.
