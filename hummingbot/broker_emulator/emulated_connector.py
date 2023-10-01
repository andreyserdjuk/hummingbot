from decimal import Decimal

from hummingbot.broker_emulator.budget_checker import BudgetChecker
from hummingbot.core.data_type.common import PriceType


class EmulatedConnector:
    _mid_price: Decimal = None

    budget_checker = BudgetChecker()

    def get_mid_price(self) -> Decimal:
        return self._mid_price

    def get_price_by_type(self, _, price_type: PriceType = PriceType.MidPrice):
        # if price_type == PriceType.BestAsk:
        return self._mid_price

    def add_listener(self, event_tag, listener):
        pass

    def remove_listener(self, event_tag, listener):
        pass

    def get_listeners(self, event_tag):
        return []

    def trigger_event(self, event_tag, message):
        pass
