import time
from portfolio import get_portfolio_nav, get_portfolio
from accounts import set_balance, transfer, inc_balance, dec_balance
from settings import get_setting, set_setting
from cmd import get_price
from utils import append_csv_row


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


def get_shareholders(portfolio_name):
    return get_setting("shares", portfolio_name, "shareholders", default={})


def get_shareholder_names(portfolio_name):
    return [name for name in get_shareholders(portfolio_name)]


def get_num_shareholders(portfolio_name):
    return len(get_shareholders(portfolio_name))


def create_shares(portfolio_name, shareholder_name, assets):
    """
    Creates shares for a portfolio and transfers them to the
    specified shareholder. The exchange rate is calculated
    using the portfolio NAV divided by the number of shares
    outstanding.
    assets is a dict of asset, balance pairs.
    """
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
            xch_rates[asset] = get_price(initial_rate, initial_rate_asset, asset)
    
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
        transfer(shareholder_name, portfolio_name, asset, balance, cur_time, meta)
        transfer(portfolio_name, shareholder_name, portfolio_name, new_shares, cur_time, meta)
        set_setting("shares", portfolio_name, "outstanding", num_shares + new_shares)
        
        fields = ["create", _next_serial_no, shareholder_name, new_shares, asset, balance, xch_rate]
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
        
        fields = ["redeem", _next_serial_no, shareholder_name, num_shares_to_redeem, asset, balance, xch_rate]
        append_csv_row(get_shares_logfile_name(portfolio_name), fields)
        
        _next_serial_no += 1
        set_setting("shares", "serial_no", _next_serial_no)

    # Destroy the shares all at once.
    transfer(shareholder_name, portfolio_name, portfolio_name, num_shares_to_redeem, cur_time, meta)
    set_setting("shares", portfolio_name, "outstanding", num_shares - num_shares_to_redeem)
