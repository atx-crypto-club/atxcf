import time
from portfolio import get_portfolio_nav, get_portfolio
from accounts import (
    set_balance, transfer, inc_balance, dec_balance, has_user,
    get_users
)
from settings import get_setting, set_setting
import cmd
from utils import append_csv_row
from PriceSource import PriceSource
from PriceNetwork import add_source


class SharesError(RuntimeError):
    pass


def get_shares_logfile_name(portfolio_name):
    default_shares_log = "shares.%s.csv" % portfolio_name
    return get_setting("shares",
                       portfolio_name,
                       "shareslog",
                       default=default_shares_log)


def get_initial_rate(portfolio_name):
    return get_setting("shares",
                       portfolio_name,
                       "initial_rate",
                       default=0.001)


def get_initial_rate_asset(portfolio_name):
    return get_setting("shares",
                       portfolio_name,
                       "initial_rate_asset",
                       default="BTC")


# TODO: add callback for set_balance and set "outstanding" to absolute
# value of portfolio_name balance of it's own shares.
def get_num_shares_outstanding(portfolio_name):
    return get_setting("shares", portfolio_name, "outstanding", default=0)


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
    transfer(portfolio_name, shareholder_name, portfolio_name, num_shares_to_grant, cur_time, meta)
    set_setting("shares", portfolio_name, "outstanding", shares_outstanding + num_shares_to_grant)

    fields = ["grant", cur_time, _next_serial_no, shareholder_name, num_shares_to_grant, "", 0.0, xch_rate]
    append_csv_row(get_shares_logfile_name(portfolio_name), fields)

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

    # for each asset offered in exchange for shares, compute
    # number of new shares to create, then transfer the assets
    # to the portfolio and credit the shareholder with the new
    # shares.
    xch_rates = {} # compute the rates before transferring assets
    for asset in assets:
        if asset == portfolio_name:
            continue
        if num_shares != 0:
            xch_rates[asset] = get_portfolio_nav_share_ratio(portfolio_name, asset)
        else:
            xch_rates[asset] = cmd.get_price(initial_rate, initial_rate_asset, asset)
    
    share_balance_per_asset = {}
    for asset, balance in assets.iteritems():
        if asset == portfolio_name:
            continue
        
        xch_rate = xch_rates[asset]
        new_shares = balance / xch_rate

        meta = {
            "create_shares": new_shares,
            "xch_rate": xch_rate,
            "serial_no": _next_serial_no
        }
        # TODO: check for sufficient shareholder balances
        transfer(shareholder_name, portfolio_name, asset, balance, cur_time, meta)
        transfer(portfolio_name, shareholder_name, portfolio_name, new_shares, cur_time, meta)
        set_setting("shares", portfolio_name, "outstanding", num_shares + new_shares)
        
        fields = ["create", cur_time, _next_serial_no, shareholder_name, new_shares, asset, balance, xch_rate]
        append_csv_row(get_shares_logfile_name(portfolio_name), fields)

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

    for asset, balance in portfolio.iteritems():
        xch_rate = xch_rates[asset]
        meta = {
            "redeem_shares": num_shares_to_redeem,
            "xch_rate": xch_rate,
            "serial_no": _next_serial_no
        }
        transfer(portfolio_name, shareholder_name, asset, balance * redemption_ratio, cur_time, meta)
        
        fields = ["redeem", cur_time, _next_serial_no, shareholder_name, num_shares_to_redeem, asset, balance, xch_rate]
        append_csv_row(get_shares_logfile_name(portfolio_name), fields)
        
        _next_serial_no += 1
        set_setting("shares", "serial_no", _next_serial_no)

    # Destroy the shares all at once.
    transfer(shareholder_name, portfolio_name, portfolio_name, num_shares_to_redeem, cur_time, meta)
    set_setting("shares", portfolio_name, "outstanding", num_shares - num_shares_to_redeem)


class PortfolioNAV(PriceSource):

    def __init__(self, base_symbols=["BTC", "USD"]):
        super(PortfolioNAV, self).__init__()
        self._base_symbols = base_symbols


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


    def get_price(self, from_asset, to_asset, amount=1.0):
        """
        Returns the price known of one portfolio's share in terms of another portfolio's share.
        """
        from_value = 0.0
        to_value = 0.0
        base_asset = self._base_symbols[0]

        if has_shares(from_asset):
            from_value = get_portfolio_nav_share_ratio(from_asset, base_asset)
        else:
            from_value = cmd.get_price(1.0, from_asset, base_asset)

        if has_shares(to_asset):
            to_value = get_portfolio_nav_share_ratio(to_asset, base_asset)
        else:
            to_value = cmd.get_price(1.0, to_asset, base_asset)

        price = 0.0
        try:
            price = from_value / to_value
        except ZeroDivisionError:
            pass
        return price * amount
            
            
add_source(PortfolioNAV())
