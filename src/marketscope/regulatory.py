from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Reachability(StrEnum):
    """How an institution in the regulatory ranking is reachable through EDGAR."""

    COVERED_TOP_TIER = "covered_top_tier"
    COVERED_US_SUBSIDIARY = "covered_us_subsidiary"
    ABSENT_NO_REGISTRATION = "absent_no_registration"
    ABSENT_FOREIGN_PARENT = "absent_foreign_parent"


@dataclass(frozen=True)
class Mapping:
    name: str
    reachability: Reachability
    cik: int | None
    note: str = ""


# Keyed on the FDIC identifier of the group: the RSSD of the regulatory high holder, or
# the institution's own certificate number where the FDIC records no holder. Identifiers
# are used rather than names because names do not survive matching.
REFERENCE_MAP: dict[str, Mapping] = {
    "HC:1039502": Mapping("JPMorgan Chase & Co", Reachability.COVERED_TOP_TIER, 19617),
    "HC:1073757": Mapping("Bank of America Corporation", Reachability.COVERED_TOP_TIER, 70858),
    "HC:1951350": Mapping("Citigroup Inc", Reachability.COVERED_TOP_TIER, 831001),
    "HC:1120754": Mapping("Wells Fargo & Company", Reachability.COVERED_TOP_TIER, 72971),
    "HC:1119794": Mapping("U.S. Bancorp", Reachability.COVERED_TOP_TIER, 36104),
    "HC:1069778": Mapping("PNC Financial Services Group", Reachability.COVERED_TOP_TIER, 713676),
    "HC:1074156": Mapping("Truist Financial Corporation", Reachability.COVERED_TOP_TIER, 92230),
    "HC:2380443": Mapping("The Goldman Sachs Group, Inc.", Reachability.COVERED_TOP_TIER, 886982),
    "HC:2277860": Mapping("Capital One Financial Corp", Reachability.COVERED_TOP_TIER, 927628),
    "HC:1238565": Mapping(
        "The Toronto-Dominion Bank",
        Reachability.ABSENT_FOREIGN_PARENT,
        None,
        "TD Group US Holdings files FR Y-9C; no US entity is an SEC registrant",
    ),
    "HC:2162966": Mapping("Morgan Stanley", Reachability.COVERED_TOP_TIER, 895421),
    "HC:1026632": Mapping("The Charles Schwab Corporation", Reachability.COVERED_TOP_TIER, 316709),
    "HC:3587146": Mapping(
        "The Bank of New York Mellon Corporation", Reachability.COVERED_TOP_TIER, 1390777
    ),
    "HC:1111435": Mapping("State Street Corporation", Reachability.COVERED_TOP_TIER, 93751),
    "HC:1132449": Mapping("Citizens Financial Group Inc", Reachability.COVERED_TOP_TIER, 759944),
    "BANK:59017": Mapping(
        "First Republic Bank",
        Reachability.ABSENT_NO_REGISTRATION,
        None,
        "State-chartered bank with no holding company and no registered securities. "
        "CIK 1132979 carries only ownership forms and returns 404 from company facts",
    ),
    "HC:1031449": Mapping("SVB Financial Group", Reachability.COVERED_TOP_TIER, 719739),
    "HC:1070345": Mapping("Fifth Third Bancorp", Reachability.COVERED_TOP_TIER, 35527),
    "HC:1037003": Mapping("M&T Bank Corporation", Reachability.COVERED_TOP_TIER, 36270),
    "HC:1068025": Mapping("KeyCorp", Reachability.COVERED_TOP_TIER, 91576),
    "HC:1068191": Mapping("Huntington Bancshares Inc", Reachability.COVERED_TOP_TIER, 49196),
    "HC:1562859": Mapping("Ally Financial Inc.", Reachability.COVERED_TOP_TIER, 40729),
    "HC:1231333": Mapping(
        "Bank of Montreal",
        Reachability.ABSENT_FOREIGN_PARENT,
        None,
        "BMO Financial Corp files FR Y-9C; no US entity is an SEC registrant",
    ),
    "HC:1857108": Mapping(
        "HSBC Holdings plc",
        Reachability.COVERED_US_SUBSIDIARY,
        83246,
        "HSBC USA Inc. files 10-K with XBRL against its registered debt",
    ),
    "HC:1275216": Mapping("American Express Company", Reachability.COVERED_TOP_TIER, 4962),
    "HC:1199611": Mapping("Northern Trust Corporation", Reachability.COVERED_TOP_TIER, 73124),
    "HC:3242838": Mapping("Regions Financial Corporation", Reachability.COVERED_TOP_TIER, 1281761),
    "HC:3846375": Mapping("Discover Financial Services", Reachability.COVERED_TOP_TIER, 1393612),
    "HC:4795461": Mapping(
        "UBS Group AG",
        Reachability.ABSENT_FOREIGN_PARENT,
        None,
        "UBS Americas Holding files FR Y-9C; the parent files 20-F without US bank detail",
    ),
    "HC:1447376": Mapping(
        "United Services Automobile Association",
        Reachability.ABSENT_NO_REGISTRATION,
        None,
        "Member-owned reciprocal inter-insurance exchange with no registered securities",
    ),
    "BANK:57053": Mapping(
        "Signature Bank",
        Reachability.ABSENT_NO_REGISTRATION,
        None,
        "State-chartered bank with no holding company. CIK 1288784 carries only ownership "
        "forms and returns 404 from company facts",
    ),
    "HC:1075612": Mapping("First Citizens BancShares Inc", Reachability.COVERED_TOP_TIER, 798941),
    "HC:1232497": Mapping(
        "Royal Bank of Canada",
        Reachability.ABSENT_FOREIGN_PARENT,
        None,
        "RBC US Group Holdings files FR Y-9C; no US entity is an SEC registrant",
    ),
    "HC:1239254": Mapping(
        "Banco Santander SA",
        Reachability.COVERED_US_SUBSIDIARY,
        811830,
        "Santander Holdings USA, Inc. files 10-K with XBRL against its registered debt",
    ),
    "HC:4504654": Mapping("Synchrony Financial", Reachability.COVERED_TOP_TIER, 1601712),
    "HC:1231968": Mapping(
        "BNP Paribas",
        Reachability.ABSENT_FOREIGN_PARENT,
        None,
        "BNP Paribas USA files FR Y-9C; no US entity is an SEC registrant",
    ),
    "BANK:32541": Mapping(
        "Flagstar Bank, National Association",
        Reachability.COVERED_TOP_TIER,
        910073,
        "The FDIC record carries no high holder at this date, weeks after the New York "
        "Community Bancorp acquisition closed. Its holder files as CIK 910073",
    ),
    "BANK:2270": Mapping(
        "Zions Bancorporation, N.A.",
        Reachability.COVERED_TOP_TIER,
        109380,
        "Dissolved its holding company in 2018 and files as the bank itself. Shows that "
        "the driver of absence is registered securities, not holding-company structure",
    ),
    "HC:1199844": Mapping("Comerica Incorporated", Reachability.COVERED_TOP_TIER, 28412),
    "HC:1094640": Mapping("First Horizon Corporation", Reachability.COVERED_TOP_TIER, 36966),
    "HC:1145476": Mapping("Webster Financial Corporation", Reachability.COVERED_TOP_TIER, 801337),
    "HC:2349815": Mapping(
        "Western Alliance Bancorporation", Reachability.COVERED_TOP_TIER, 1212545
    ),
    "HC:1129382": Mapping("Popular, Inc.", Reachability.COVERED_TOP_TIER, 763901),
    "HC:2734233": Mapping("East West Bancorp, Inc.", Reachability.COVERED_TOP_TIER, 1069157),
    "HC:1078846": Mapping("Synovus Financial Corp.", Reachability.COVERED_TOP_TIER, 18349),
    "HC:3815157": Mapping("Raymond James Financial, Inc.", Reachability.COVERED_TOP_TIER, 720005),
    "HC:1048773": Mapping("Valley National Bancorp", Reachability.COVERED_TOP_TIER, 714310),
    "HC:2260406": Mapping("Wintrust Financial Corporation", Reachability.COVERED_TOP_TIER, 1015328),
    "BANK:33653": Mapping(
        "Bank of China",
        Reachability.ABSENT_FOREIGN_PARENT,
        None,
        "US branch network of a Chinese bank; no US entity is an SEC registrant",
    ),
    "BANK:33692": Mapping(
        "Standard Chartered Bank, PLC",
        Reachability.ABSENT_FOREIGN_PARENT,
        None,
        "US branch of a UK bank; no US entity is an SEC registrant",
    ),
}


# The two kinds of FDIC group key, and the BankFind field each selects on.
HOLDER_PREFIX = "HC:"
INSTITUTION_PREFIX = "BANK:"


def group_filter(key: str) -> str:
    """BankFind filter selecting every insured institution in an FDIC group.

    A group keyed on its regulatory high holder is every institution reporting that holder in
    the quarter; one keyed on a certificate is the institution alone, which is how a bank
    with no holding company appears.
    """
    if key.startswith(HOLDER_PREFIX):
        return f"RSSDHCR:{key.removeprefix(HOLDER_PREFIX)}"
    if key.startswith(INSTITUTION_PREFIX):
        return f"CERT:{key.removeprefix(INSTITUTION_PREFIX)}"
    raise ValueError(f"Unrecognised FDIC group key {key!r}")


def mapped_registrants() -> dict[str, int]:
    """FDIC group key to SEC CIK, for every group the pinned table reaches through EDGAR."""
    return {key: mapping.cik for key, mapping in REFERENCE_MAP.items() if mapping.cik is not None}
