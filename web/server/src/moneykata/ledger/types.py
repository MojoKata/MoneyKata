"""What account types are and how they group (requirements §4.1)."""

GROUPS = {
    "checking": "banking",
    "savings": "banking",
    "money-market": "banking",
    "cd": "banking",
    "credit-card": "liabilities",
    "brokerage": "investing",
    "ira": "retirement",
    "roth-ira": "retirement",
    "401k": "retirement",
    "403b": "retirement",
    "457b": "retirement",
    "hsa": "retirement",
}
GROUP_ORDER = [
    "banking",
    "investing",
    "retirement",
    "education",
    "crypto",
    "giving",
    "liabilities",
    "physical-assets",
]
LABELS = {
    "checking": "Checking",
    "savings": "Savings",
    "money-market": "Money market",
    "cd": "CD",
    "credit-card": "Credit card",
    "brokerage": "Brokerage",
    "ira": "Traditional IRA",
    "roth-ira": "Roth IRA",
    "401k": "401(k)",
    "403b": "403(b)",
    "457b": "457(b)",
    "hsa": "HSA",
}
TAX = {
    "checking": "taxable",
    "savings": "taxable",
    "money-market": "taxable",
    "cd": "taxable",
    "credit-card": None,
    "brokerage": "taxable",
    "ira": "deferred",
    "roth-ira": "free",
    "401k": "deferred",
    "403b": "deferred",
    "457b": "deferred",
    "hsa": "free",
}


def investing(account_type: str) -> bool:
    """Holds instruments, so it has Holdings and Positions tabs."""
    return GROUPS[account_type] in ("investing", "retirement")


def reconcilable(account_type: str) -> bool:
    """Banking, card, brokerage and loan accounts have a Reconcile tab (§4.11)."""
    return GROUPS[account_type] in ("banking", "liabilities") or account_type == "brokerage"


def retirement(account_type: str) -> bool:
    return GROUPS[account_type] == "retirement"
