from dataclasses import dataclass
from decimal import Decimal


class BudgetChecker:
    def adjust_candidate(self, order_candidate):
        return OrderCandidate(Decimal("123"))


@dataclass
class OrderCandidate:
    amount: Decimal
