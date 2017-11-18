import csv
import time

import accounts
from settings import (
    get_settings_option, get_settings, set_settings, set_option
)


def _append_csv_row(csv_filename, fields):
    """
    Appends row to specified csv file. 'fields' should be
    a list.
    """
    with open(csv_filename, 'ab') as f:
        writer = csv.writer(f)
        writer.writerow(fields)

        
def get_exchange_logfile_name():
    """
    Returns the exchange logfile name from the options.
    """
    return get_settings_option("exchangelog", "exchange.csv")


def exchange(swap_a, swap_b):
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
    fields=[cur_time, swap_a[0], swap_b[0], asset_pair, swap_a[2], swap_b[2], rate]
    _append_csv_row(get_exchange_logfile_name(), fields)

    accounts.sync_account_settings()


class Order(object):

    def __init__(self, user, to_asset, from_asset, amount, price):
        self._time = time.time()
        self._user = user
        self._to = to_asset
        self._from = from_asset
        self._initial_amount = float(amount)
        self._price = price

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

    def __init__(self, to_asset, from_asset):
        # to / from

        self._to = to_asset
        self._from = from_asset

        self._asks = None
        self._bids = None


    def limit_buy(self, user, amount, price):
        """
        Sets a limit buy order and returns it.
        """
        new_order = Order(user, self._to,
                          self._from, amount, price)

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
                bid = bid.next
                

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
                ask = ask.next
                

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
        
