"""Maps each entity onto its table (requirements S14.1.2). Imported once, at start."""

from sqlalchemy import event
from sqlalchemy.orm import registry

from .entities import Record, _now
from .entities import accounts as acc
from .entities import assets as asx
from .entities import budgets as bd
from .entities import education as ed
from .entities import giving as gv
from .entities import links as lk
from .entities import prices as pr
from .entities import projections as pj
from .entities import receipts as rc
from .entities import sharing as sh
from .entities import taxes as tx
from .entities.alerts import Alert, AlertState
from .entities.core import Activity, Secret, Setting, TaskRun
from .entities.users import (
    AccessToken,
    Group,
    OneTimeToken,
    RecoveryCode,
    Session,
    SignupRequest,
    User,
    UserGroup,
)
from .tables import (
    accounts,
    activity,
    alerts,
    assets,
    budgets,
    core,
    education,
    giving,
    links,
    loans,
    options,
    people,
    prices,
    projections,
    receipts,
    sharing,
    taxes,
    users,
    wallets,
)

mapper_registry = registry()
_done = False


def _versioned(entity, table, **kw) -> None:
    mapper_registry.map_imperatively(entity, table, version_id_col=table.c.version, **kw)


def map_all() -> None:
    global _done
    if _done:
        return
    _done = True
    _versioned(User, users.User)
    _versioned(Group, users.Group)
    _versioned(AccessToken, users.AccessToken)
    mapper_registry.map_imperatively(UserGroup, users.UserGroups)
    mapper_registry.map_imperatively(Session, users.Session)
    mapper_registry.map_imperatively(OneTimeToken, users.OneTimeToken)
    mapper_registry.map_imperatively(RecoveryCode, users.RecoveryCode)
    mapper_registry.map_imperatively(SignupRequest, users.SignupRequest)
    mapper_registry.map_imperatively(Alert, alerts.Alert)
    mapper_registry.map_imperatively(AlertState, alerts.AlertState)
    for entity, table in (
        (acc.Category, accounts.Category),
        (acc.Account, accounts.Account),
        (acc.Instrument, accounts.Instrument),
        (acc.ImportMapping, accounts.ImportMapping),
        (acc.StatementLayout, accounts.StatementLayout),
        (acc.Loan, loans.Loan),
        (acc.OptionContract, options.OptionContract),
        (acc.WalletKey, wallets.WalletKey),
        (acc.PayoffPlan, loans.PayoffPlan),
        (tx.TaxBook, taxes.TaxBook),
        (tx.Filing, taxes.Filing),
        (tx.EstimatedPayment, taxes.EstimatedPayment),
        (tx.TaxDocument, taxes.TaxDocument),
        (gv.GivingPlan, giving.GivingPlan),
        (gv.Organisation, giving.Organisation),
        (gv.Donation, giving.Donation),
        (ed.Person, people.Person),
        (ed.Occasion, people.Occasion),
        (ed.Gift, people.Gift),
        (ed.EducationPlan, education.EducationPlan),
        (ed.Contribution, education.Contribution),
        (ed.QualifiedExpense, education.QualifiedExpense),
        (asx.Item, assets.Item),
        (asx.ItemValuation, assets.ItemValuation),
        (asx.Improvement, assets.Improvement),
        (acc.Import, accounts.Import),
        (acc.Transaction, accounts.Transaction),
        (acc.Split, accounts.Split),
        (acc.Lot, accounts.Lot),
        (acc.Holding, accounts.Holding),
        (acc.Anchor, accounts.Anchor),
        (acc.Reconciliation, accounts.Reconciliation),
    ):
        _versioned(entity, table)
    mapper_registry.map_imperatively(acc.TransactionTag, accounts.TransactionTags)
    mapper_registry.map_imperatively(acc.LotPick, accounts.LotPicks)
    _versioned(pr.PriceSource, prices.PriceSource)
    _versioned(pr.Price, prices.Price)
    _versioned(sh.Portfolio, sharing.Portfolio)
    _versioned(sh.Share, sharing.Share)
    mapper_registry.map_imperatively(sh.PortfolioAccount, sharing.PortfolioAccounts)
    _versioned(bd.Budget, budgets.Budget)
    _versioned(bd.BudgetLine, budgets.BudgetLine)
    mapper_registry.map_imperatively(bd.BudgetAccount, budgets.BudgetAccounts)
    _versioned(rc.Receipt, receipts.Receipt)
    mapper_registry.map_imperatively(rc.ReceiptLink, receipts.ReceiptLinks)
    mapper_registry.map_imperatively(ed.GiftPerson, people.GiftPersons)
    mapper_registry.map_imperatively(acc.WashSale, options.WashSale)
    mapper_registry.map_imperatively(acc.WalletAddress, wallets.WalletAddress)
    mapper_registry.map_imperatively(tx.TaxBookFiler, taxes.TaxBookFilers)
    mapper_registry.map_imperatively(tx.TaxBookAccount, taxes.TaxBookAccounts)
    _versioned(pj.AssumptionSet, projections.AssumptionSet)
    _versioned(pj.Projection, projections.Projection)
    _versioned(pj.TaxFigure, projections.TaxFigure)
    mapper_registry.map_imperatively(pj.ShownProjection, projections.ShownProjections)
    mapper_registry.map_imperatively(sh.CountedAccount, sharing.CountedAccounts)
    _versioned(Setting, core.Setting)
    _versioned(lk.Link, links.Link)
    mapper_registry.map_imperatively(lk.LinkedItem, links.LinkedItem)
    mapper_registry.map_imperatively(lk.LinkSent, links.LinkSent)
    mapper_registry.map_imperatively(lk.LinkColour, links.LinkColours)
    mapper_registry.map_imperatively(Secret, core.Secret)
    mapper_registry.map_imperatively(TaskRun, core.TaskRun)
    mapper_registry.map_imperatively(Activity, activity.Activity)


@event.listens_for(Record, "before_update", propagate=True)
def _touch(mapper, connection, target) -> None:
    target.updatedAt = _now()


@event.listens_for(Setting, "before_update")
def _touch_setting(mapper, connection, target) -> None:
    target.updatedAt = _now()
