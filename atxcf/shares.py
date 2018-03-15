import time
from portfolio import get_portfolio_nav, get_portfolio
from accounts import (
    set_balance, transfer, inc_balance, dec_balance, has_user,
    get_users, get_balance, add_post_set_balance_callback,
    add_user
)
from settings import get_setting, set_setting, get_settings_filename
import cmd
from utils import append_record
from PriceSource import PriceSource
from PriceNetwork import add_source

from threading import current_thread, RLock
from collections import defaultdict

class SharesError(RuntimeError):
    pass


def get_shares_logfile_name(portfolio_name):
    default = "%s.shares.%s.csv" % (get_settings_filename(),
                                    portfolio_name)
    return get_setting("shares",
                       portfolio_name,
                       "shareslog",
                       default=default)


def get_initial_rate(portfolio_name):
    """
    Starting exchange rate to use when a fund has zero
    shares outstanding.
    """
    return get_setting("shares",
                       portfolio_name,
                       "initial_rate",
                       default=0.001)


def set_initial_rate(portfolio_name, rate):
    """
    Modify the initial rate to use when a fund has
    zero shares outstanding.
    """
    set_setting("shares",
                portfolio_name,
                "initial_rate",
                rate)


def get_initial_rate_asset(portfolio_name):
    """
    The asset to use as a base value metric when
    creating the first sharesz. Also used when granting
    shares to calculate relative value of shares granted.
    """
    return get_setting("shares",
                       portfolio_name,
                       "initial_rate_asset",
                       default="BTC")


def set_initial_rate_asset(portfolio_name, asset):
    """
    Modifiy the initial rate asset setting for the specified
    portfolio.
    """
    set_setting("shares",
                portfolio_name,
                "initial_rate_asset",
                asset)


def get_share_creation_fee_rate(portfolio_name):
    """
    Returns the fee applied to share creation in percent of value used.
    to create shares. Doesn't apply to share granting.
    """
    return get_setting("shares",
                       portfolio_name,
                       "share_creation_fee_rate",
                       default=0.01)


def set_share_creation_fee_rate(portfolio_name, fee):
    """
    Sets the share creation fee.
    """
    set_setting("shares",
                portfolio_name,
                "share_creation_fee_rate",
                fee)


def get_share_redemption_fee_rate(portfolio_name):
    """
    Returns the fee applied to share redemption in percent of value of
    assets redeemed.
    """
    return get_setting("shares",
                       portfolio_name,
                       "share_redemption_fee_rate",
                       default=0.025)


def set_share_redemption_fee_rate(portfolio_name, fee):
    """
    Sets the share redemption fee in percent of value of redeemed assets.
    """
    set_setting("shares",
                portfolio_name,
                "share_redemption_fee_rate",
                fee)

    
def get_share_creation_fee_account(portfolio_name):
    """
    Where share creation fees end up for a particular portfolio.
    """
    default_name = portfolio_name + "_share_creation_fees"
    return get_setting("shares",
                       portfolio_name,
                       "share_creation_fee_account",
                       default=default_name)

                       
def set_share_creation_fee_account(portfolio_name, fee_account):
    """
    Set where share creation fees end up for a particular portfolio.
    """
    set_setting("shares",
                portfolio_name,
                "share_creation_fee_account",
                fee_account)


def get_share_redemption_fee_account(portfolio_name):
    """
    Where share redemption fees end up for a particular portfolio's shares.
    """
    default_name = portfolio_name + "_share_redemption_fees"
    return get_setting("shares",
                       portfolio_name,
                       "share_redemption_fee_account",
                       default=default_name)

                       
def set_share_redemption_fee_account(portfolio_name, fee_account):
    """
    Set where share creation fees end up for a particular portfolio's shares.
    """
    set_setting("shares",
                portfolio_name,
                "share_redemption_fee_account",
                fee_account)


def get_num_shares_outstanding(portfolio_name):
    return get_setting("shares", portfolio_name, "outstanding", default=0)


# Keep the shares outstanding updated.
def _post_set_portfolio_share_balance(name, asset, amount, cur_time=None, meta={}):
    if name == asset:
        set_setting("shares", asset, "outstanding", abs(float(amount)))
add_post_set_balance_callback("shares_outstanding", _post_set_portfolio_share_balance)


# Keep the list of shareholders updated.
def _post_set_portfolio_shareholders(name, asset, amount, cur_time=None, meta={}):
    if has_shares(asset):
        set_setting("shares", asset, "shareholders", name, amount)
add_post_set_balance_callback("shareholders", _post_set_portfolio_shareholders)


def get_portfolio_nav_share_ratio(portfolio_name, base_asset):
    """
    Returns the exchange rate for one share of the specified
    portfolio.
    """
    if get_num_shares_outstanding(portfolio_name) == 0:
        return 0

    p_nav = get_portfolio_nav(portfolio_name, base_asset)
    return p_nav / get_num_shares_outstanding(portfolio_name)


def is_shareholder(portfolio_name, shareholder_name):
    """
    Returns a boolean flagging whether a specified shareholder holds
    a balance of shares of the specified portfolio.
    """
    if not has_user(portfolio_name):
        raise SharesError("Invalid portfolio: %s" % portfolio_name)
    if not has_user(shareholder_name):
        raise SharesError("Invalid shareholder: %s" % shareholder_name)
    return get_balance(shareholder_name, portfolio_name) > 0


def get_shareholder_names(portfolio_name):
    shareholder_names = []
    for user in get_users():
        if is_shareholder(portfolio_name, user):
            shareholder_names.append(user)
    return shareholder_names


def get_shareholders(portfolio_name):
    shareholders = {}
    for user in get_users():
        if is_shareholder(portfolio_name, user):
            shareholders[user] = get_balance(user, portfolio_name)
    return shareholders


def get_num_shareholders(portfolio_name):
    return len(get_shareholder_names(portfolio_name))


def has_shares(portfolio_name):
    return get_num_shares_outstanding(portfolio_name) > 0


def grant_shares(portfolio_name, shareholder_name, num_shares_to_grant):
    """
    Grants the specified number of shares to the specified shareholder.
    This dilutes the supply of shares of the specified portfolio if there
    are already shares. Otherwise, this creates shares for a portfolio
    with existing assets and credits them to the specified shareholder.
    """
    if num_shares_to_grant <= 0:
        raise SharesError("Invalid number of shares to grant: %d" % num_shares_to_grant)
    if not has_user(portfolio_name):
        raise SharesError("Invalid portfolio: %s" % portfolio_name)
    if not has_user(shareholder_name):
        raise SharesError("Invalid shareholder: %s" % shareholder_name)
    
    _next_serial_no = get_setting("shares", "serial_no", default=0)
    initial_rate_asset = get_initial_rate_asset(portfolio_name)
    portfolio_nav = get_portfolio_nav(portfolio_name, initial_rate_asset)
    shares_outstanding = get_num_shares_outstanding(portfolio_name)
    cur_time = time.time()
    value = 0.0
    if shares_outstanding == 0:
        value = portfolio_nav
    else:
        redemption_ratio = num_shares_to_grant / shares_outstanding
        value = portfolio_nav * redemption_ratio
    xch_rate = value / num_shares_to_grant
    meta = {
        "grant_shares": num_shares_to_grant,
        "xch_rate": xch_rate,
        "serial_no": _next_serial_no
    }
    transfer(portfolio_name, shareholder_name, portfolio_name,
             num_shares_to_grant, cur_time, meta)

    fields = ["grant", cur_time, _next_serial_no, shareholder_name,
              num_shares_to_grant, "", 0.0, xch_rate]
    append_record(get_shares_logfile_name(portfolio_name), fields)

    _next_serial_no += 1
    set_setting("shares", "serial_no", _next_serial_no)


def create_shares(portfolio_name, shareholder_name, assets):
    """
    Creates shares for a portfolio and transfers them to the
    specified shareholder. The exchange rate is calculated
    using the portfolio NAV divided by the number of shares
    outstanding. A portfolio should have no assets if number
    of shares is zero.
    assets is a dict of asset, balance pairs.
    """
    if not has_user(portfolio_name):
        raise SharesError("Invalid portfolio: %s" % portfolio_name)
    if not has_user(shareholder_name):
        raise SharesError("Invalid shareholder: %s" % shareholder_name)
    
    _next_serial_no = get_setting("shares", "serial_no", default=0)
    num_shares = get_num_shares_outstanding(portfolio_name)
    initial_rate = get_initial_rate(portfolio_name)
    initial_rate_asset = get_initial_rate_asset(portfolio_name)

    cur_time = time.time()

    # TODO: throw an error if num shares is zero and we have assets

    # for each asset offered in exchange for shares, compute
    # number of new shares to create, then transfer the assets
    # to the portfolio and credit the shareholder with the new
    # shares.
    xch_rates = {} # compute the rates before transferring assets
    for asset in assets:
        if asset == portfolio_name:
            continue
        if num_shares != 0:
            xch_rates[asset] = get_portfolio_nav_share_ratio(portfolio_name,
                                                             asset)
        else:
            xch_rates[asset] = cmd.get_price(initial_rate,
                                             initial_rate_asset,
                                             asset)

    fee_rate = get_share_creation_fee_rate(portfolio_name) / 100.0 # normalized from percent
    fee_account = get_share_creation_fee_account(portfolio_name)
    if not has_user(fee_account):
        add_user(fee_account)
    
    share_balance_per_asset = {}
    for asset, balance in assets.iteritems():
        if asset == portfolio_name:
            continue
        
        xch_rate = xch_rates[asset]
        new_shares = balance / xch_rate

        meta = {
            "create_shares": new_shares,
            "xch_rate": xch_rate,
            "serial_no": _next_serial_no,
            "value": balance,
            "fee": fee_rate
        }
        
        # TODO: check for sufficient shareholder balances

        # extract fee if any
        if fee_rate != 0.0:
            transfer(shareholder_name, fee_account, asset, balance * fee_rate,
                     cur_time, meta)
                       
        transfer(shareholder_name, portfolio_name, asset, balance,
                 cur_time, meta)
        transfer(portfolio_name, shareholder_name, portfolio_name,
                 new_shares, cur_time, meta)
        
        fields = ["create", cur_time, _next_serial_no, shareholder_name,
                  new_shares, asset, balance, xch_rate]
        append_record(get_shares_logfile_name(portfolio_name), fields)

        _next_serial_no += 1
        set_setting("shares", "serial_no", _next_serial_no)
        

def redeem_shares(portfolio_name, shareholder_name, num_shares_to_redeem):
    """
    Redeems shares for a portfolio and transfers the specified
    assets to the shareholder in exchange. assets is a list of 
    asset names held in the portfolio. Any that aren't are
    ignored.
    """
    if not has_user(portfolio_name):
        raise SharesError("Invalid portfolio: %s" % portfolio_name)
    if not has_user(shareholder_name):
        raise SharesError("Invalid shareholder: %s" % shareholder_name)
    
    _next_serial_no = get_setting("shares", "serial_no", default=0)
    num_shares = get_num_shares_outstanding(portfolio_name)
    if num_shares == 0:
        return # no-op

    cur_time = time.time()

    # Transfer the portion of value that the shares represented to the
    # shareholder.
    redemption_ratio = float(num_shares_to_redeem) / float(num_shares)
    portfolio = get_portfolio(portfolio_name)

    xch_rates = {}
    for asset in portfolio:
        xch_rates[asset] = get_portfolio_nav_share_ratio(portfolio_name, asset)

    fee_rate = get_share_redemption_fee_rate(portfolio_name) / 100.0 # normalized from percent
    fee_account = get_share_redemption_fee_account(portfolio_name)
    if not has_user(fee_account):
        add_user(fee_account)
                       
    for asset, balance in portfolio.iteritems():
        xch_rate = xch_rates[asset]
        value = balance * redemption_ratio
        meta = {
            "xch_rate": xch_rate,
            "serial_no": _next_serial_no,
            "value": value,
            "fee": fee_rate
        }

        # extract fee if any
        if fee_rate != 0.0:
            transfer(shareholder_name, fee_account, asset,
                     value * fees,
                     cur_time, meta)
        
        transfer(portfolio_name, shareholder_name, asset,
                 value, cur_time, meta)
        
        fields = ["redeem", cur_time, _next_serial_no, shareholder_name,
                  num_shares_to_redeem, asset, balance, xch_rate]
        append_record(get_shares_logfile_name(portfolio_name), fields)
        
        _next_serial_no += 1
        set_setting("shares", "serial_no", _next_serial_no)

    # Destroy the shares all at once.
    transfer(shareholder_name, portfolio_name, portfolio_name,
             num_shares_to_redeem, cur_time, meta)


class PortfolioNAV(PriceSource):

    def __init__(self, base_symbols=["BTC", "USD"]):
        super(PortfolioNAV, self).__init__()
        self._base_symbols = base_symbols

        # to track recursive calls
        self._lock = RLock()
        self._recur = defaultdict(lambda: defaultdict(str))
        self._recur_depth = defaultdict(int)


    def get_shared_portfolios(self):
        portfolios = []
        for portfolio in get_users():
            if has_shares(portfolio):
                portfolios.append(portfolio)
        return portfolios

        
    def get_symbols(self):
        """
        Returns a list of portfolios that have shares of themselves outstanding and
        base asset symbols.
        """
        return self.get_shared_portfolios() + self._base_symbols

    
    def get_base_symbols(self):
        """
        Provided when instantiating self.
        """
        return self._base_symbols


    def get_markets(self):
        """
        Returns known value conversions that this price source can compute.
        """
        mkts = []
        for portfolio in self.get_shared_portfolios():
            for base_symbol in self.get_base_symbols():
                mkts.append(portfolio + "/" + base_symbol)
        return mkts


    def _get_depth(self):
        with self._lock:
            return self._recur_depth[current_thread().ident]


    def _inc_depth(self):
        with self._lock:
            self._recur_depth[current_thread().ident] += 1

            
    def _dec_depth(self):
        with self._lock:
            self._recur_depth[current_thread().ident] -= 1
            if self._recur_depth[current_thread().ident] <= 0:
                self._recur_depth[current_thread().ident] = 0
                self._recur = defaultdict(lambda: defaultdict(str))
            

    def get_price(self, from_asset, to_asset, amount=1.0):
        """
        Returns the price known of one portfolio's share in terms of another asset
        or vice versa.
        """
        if amount == 0.0:
            return amount
        
        from_value = 0.0
        to_value = 0.0
        base_asset = self._base_symbols[0]

        price = 0.0

        self._inc_depth()
        
        # If we have already priced this in this series of recursive calls,
        # let subsequent recursive calls return a price of zero so it's not
        # counted multiple times.
        with self._lock:
            if self._recur[current_thread().ident][from_asset] == to_asset:
                self._dec_depth()
                return price
            else:
                self._recur[current_thread().ident][from_asset] = to_asset
        
        if has_shares(from_asset):
            from_value = get_portfolio_nav_share_ratio(from_asset, base_asset)
        else:
            from_value = cmd.get_price(1.0, from_asset, base_asset)

        if has_shares(to_asset):
            to_value = get_portfolio_nav_share_ratio(to_asset, base_asset)
        else:
            to_value = cmd.get_price(1.0, to_asset, base_asset)

        try:
            price = from_value / to_value
        except ZeroDivisionError:
            pass
        self._dec_depth()
        return price * amount
            
            
add_source(PortfolioNAV())
