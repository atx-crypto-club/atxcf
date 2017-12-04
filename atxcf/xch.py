# -*- coding: utf-8 -*-

import csv
import time
from collections import defaultdict
from collections import OrderedDict

import accounts
from settings import (
    get_settings_option, get_settings, set_settings, set_option
)

from utils import (
    append_csv_row
)

        
def get_exchange_logfile_name():
    """
    Returns the exchange logfile name from the options.
    """
    return get_settings_option("exchangelog", "exchange.csv")


def get_exchange_marketlog_name():
    """
    Returns the marketlog file name from the options.
    """
    return get_settings_option("marketlog", "market.csv")


def exchange(swap_a, swap_b, meta={}):
    """
    Exchanges an amount of an asset specified in swap_a,
    with that of the asset specified in swap_b.

    Both arguments are tuples of the form (user, asset, amount).
    """
    cur_time = time.time()
    accounts.transfer(swap_a[0], swap_b[0], swap_a[1], swap_a[2], cur_time, False)
    accounts.transfer(swap_b[0], swap_a[0], swap_b[1], swap_b[2], cur_time, False)

    # append to exchange log csv
    asset_pair = swap_a[1] + "/" + swap_b[1]
    rate = float(swap_b[2]) / float(swap_a[2])
    fields=[cur_time, swap_a[0], swap_b[0], asset_pair, swap_a[2], swap_b[2], rate, meta]
    append_csv_row(get_exchange_logfile_name(), fields)

    accounts.sync_account_settings()


class Order(object):

    _next_id = 0
    
    def __init__(self, user, to_asset, from_asset, amount, price):
        self._time = time.time()
        self._user = user
        self._to = to_asset
        self._from = from_asset
        self._initial_amount = float(amount)
        self._price = float(price)
        self._id = self._next_id
        self._next_id += 1

        # TODO: add state flag - open, cancelled

        # amount left to fill. When 0, the order is filled
        self._leftover_amount = self._initial_amount
        
        self._next_order = None # linked list of orders

    @property
    def user(self):
        return self._user
        
    @property
    def time(self):
        return self._time

    @property
    def to_asset(self):
        return self._to

    @property
    def from_asset(self):
        return self._from
    
    @property
    def price(self):
        return self._price
        
    @property
    def initial_amount(self):
        return self._initial_amount
        
    @property
    def next(self):
        return self._next_order

    @next.setter
    def next(self, next_order):
        self._next_order = next_order

    @property
    def amount(self):
        return self._leftover_amount

    @property
    def filled(self):
        return float(self._leftover_amount) == 0.0

    @property
    def id(self):
        return self._id
    
    def fill(self, amount):
        if self._leftover_amount <= 0.0:
            return 0.0
        
        self._leftover_amount -= amount
        if self._leftover_amount < 0.0:
            leftover = self._leftover_amount
            self._leftover_amount = 0.0
            return leftover * -1.0
        return 0.0


class Market(object):

    _rec_id = 0 # default start record id
    
    def __init__(self, market_pair):
        # to / from

        symbol = market_pair.split("/")

        self._to = symbol[0]
        self._from = symbol[1]

        self._asks = None
        self._bids = None

        self._user_orders = defaultdict(list)

        self._rec_id = get_settings_option("market_rec_id_start", self._rec_id)


    def get_bids(self):
        bids = {}
        bid = self._bids
        while bid:
            price = bid.price
            amount = bid.amount
            if price in bids:
                bids[price]+=amount
            else:
                bids[price]=amount
            bid = bid.next
        return OrderedDict(sorted(bids.items(), key=lambda t: t[0], reverse=True))

    
    def get_asks(self):
        asks = {}
        ask = self._asks
        while ask:
            price = ask.price
            amount = ask.amount
            if price in asks:
                asks[price]+=amount
            else:
                asks[price]=amount
            ask = ask.next
        return OrderedDict(sorted(asks.items(), key=lambda t: t[0]))

    
    def _record_new_order(self, new_order, new_order_type):
        """
        Records the order in the marketlog.
        """
        fields=[new_order.time, self._rec_id, new_order.id, new_order_type,
                new_order.user, new_order.to_asset, new_order.from_asset,
                new_order.amount, new_order.price]
        append_csv_row(get_exchange_marketlog_name(), fields)
        self._rec_id += 1
        # keep the settings updated
        set_option("market_rec_id_start", self._rec_id)        

        
    def limit_buy(self, user, amount, price):
        """
        Sets a limit buy order and returns it.
        """
        new_order = Order(user, self._to,
                          self._from, amount, price)

        # TODO: check if order is valid, balance is sufficient, etc.

        self._record_new_order(new_order, "limit_buy")
        self._user_orders[user].append(("buy", new_order))
        
        if not self._bids:
            self._bids = new_order
        else:

            # find the first order that we're bigger
            # than and insert the Order in front of that.
            prev_bid = None
            bid = self._bids
            while bid:
                if bid.price < new_order.price:
                    break
                prev_bid = bid
                next_bid = bid.next
                bid = next_bid
                
            if prev_bid:
                prev_bid.next = new_order
                new_order.next = bid
            else:
                new_order.next = bid
                self._bids = new_order

        return new_order


    def limit_sell(self, user, amount, price):
        """
        Sets a limit sell order and returns it.
        """
        new_order = Order(user, self._to,
                          self._from, amount, price)

        # TODO: check if order is valid, balance is sufficient, etc.

        self._record_new_order(new_order, "limit_sell")
        self._user_orders[user].append(("sell", new_order))

        if not self._asks:
            self._asks = new_order
        else:

            # find the first order that we're smaller
            # than and insert the Order in front of that.
            prev_ask = None
            ask = self._asks
            while ask:
                if ask.price > new_order.price:
                    break
                prev_ask = ask
                next_ask = ask.next
                ask = next_ask
                
            if prev_ask:
                prev_ask.next = new_order
                new_order.next = ask
            else:
                new_order.next = ask
                self._asks = new_order

        return new_order
    
    
    def resolve(self):
        """
        matches orders that can be matched
        """
        bid = self._bids
        ask = self._asks

        spread = ask.price - bid.price
        while spread <= 0:


            price = 0.0
            if ask.time > bid.time:
                # if the ask came later, fill the orders
                # with an exchange at the bid rate
                price = bid.price
            else:
                # otherwise, use the ask price
                price = ask.price

            ask_amount = price * (ask.amount - ask.fill_amount)
            bid_amount = price * (bid.amount - bid.fill_amount)

            #TODO: finish this!! it's fuckeD!!!
            
            dx = ask_amount - bid_amount
            if dx > 0:
                # ask amount was greater so mark the bid filled
                bid.fill_amount = bid.amount
                bid.filled = True
                ask.fill_amount += bid_amount
            elif dx < 0:
                # bid amount was greater so mark the ask filled
                ask.fill_amount = ask.amount
                ask.filled = True
                bid.fill_amount += ask_amount

            # if ask_amount >= bid_amount:
            #     ask.fill_amount = bid_amount
            #     bid.fill_amount = bid_amount

                
            # bid.filled = True
            
            #ask_amount = ask.price * ask.amount
            #bid_amount = bid.price * bid.amount

            #dx = ask_amount - bid_amount
            
            exchange((ask.user, self._from, ask.amount),
                     (bid.user, self._to, bid.amount))
            
            # check if no more orders in the book
            if not ask or not bid:
                break

            # calculate the new spread
            spread = ask.price - bid.price
        

        # TODO finish meeeee
        
_markets = {}
def _get_market(market_pair):
    global _markets
    if not market_pair in _markets:
        _markets[market_pair] = Market(market_pair)
    return _markets[market_pair]


def limit_buy(user, market_pair, amount, price):
    """
    Add a limit buy order to the book and executes and fills
    the orders until there is a spread between the bid and ask
    or no orders on the book left.
    """
    _get_market(market_pair).limit_buy(user, amount, price)
    #_markets[market].resolve()

    
def limit_sell(user, market_pair, amount, price):
    """
    Add a limit sell order to the book and executes and fills
    the orders until there is a spread between the bid and ask
    or no orders on the book left.
    """
    _get_market(market_pair).limit_sell(user, amount, price)
    #_markets[market].resolve()


def orderbook(market_pair):
    """
    Returns the orderbook as a dict
    """
    mkt = _get_market(market_pair)
    return {"bids": mkt.get_bids(),
            "asks": mkt.get_asks()}

