"""What account types are and how they group (requirements S1.1)."""

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
    "mortgage": "liabilities",
    "heloc": "liabilities",
    "auto-loan": "liabilities",
    "student-loan": "liabilities",
    "personal-loan": "liabilities",
    "loan": "liabilities",
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
    "mortgage": "Mortgage",
    "heloc": "HELOC",
    "auto-loan": "Auto loan",
    "student-loan": "Student loan",
    "personal-loan": "Personal loan",
    "loan": "Loan",
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
    "mortgage": None,
    "heloc": None,
    "auto-loan": None,
    "student-loan": None,
    "personal-loan": None,
    "loan": None,
}


def investing(account_type: str) -> bool:
    """Holds instruments, so it has Holdings and Positions tabs."""
    return GROUPS[account_type] in ("investing", "retirement")


def reconcilable(account_type: str) -> bool:
    """Banking, card and brokerage accounts have a Reconcile tab (S1.11); a loan is checked
    against its servicer's balance on its own screen (S1.9.4)."""
    from ..loans import is_loan

    if is_loan(account_type):
        return False
    return GROUPS[account_type] in ("banking", "liabilities") or account_type == "brokerage"


def retirement(account_type: str) -> bool:
    return GROUPS[account_type] == "retirement"
