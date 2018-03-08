"""
Main set of commands known by the atxcf bot.
"""

from PriceNetwork import instance as _instance
from PriceNetwork import (
    PriceSourceError,
    get_price, get_prices, get_nav, get_symbols,
    get_base_symbols, get_markets, get_market_sources,
    get_all_prices
)
from stats import (
    log_prices, compute_candles, get_candle,
    get_current_candle_bin,
    get_candle_begin, get_candle_end,
    get_candle_low, get_candle_high,
    get_current_begin, get_current_end,
    get_current_low, get_current_high,
    get_current_percent_change
)
import settings
from settings import get_setting, set_setting
from settings import get_settings_option as _get_settings_option

from accounts import (
    number_of_users, get_users, has_user, add_user,
    get_user_email, set_user_email, get_assets,
    get_balance, set_balance, inc_balance, dec_balance,
    get_metadata_value, set_metadata_value,
    transfer
)

from portfolio import (
    get_portfolio, get_portfolio_values, get_portfolio_nav
)

from shares import (
    get_initial_rate, get_initial_rate_asset, set_initial_rate,
    set_initial_rate_asset, get_num_shares_outstanding,
    get_portfolio_nav_share_ratio, is_shareholder, get_shareholders,
    get_shareholder_names, get_num_shareholders, has_shares,
    create_shares, redeem_shares, grant_shares
)

import cache

#import coinmarketcap

import string
import sys
import threading
import time


class CmdError(RuntimeError):
    pass

    
_updater_thread = None
def keep_prices_updated():
    """
    Launches a thread to keep prices in the cache updated.
    """
    global _updater_thread
    if not _updater_thread:
        def updater():
            interval = _get_settings_option("price_update_interval", 60)
            last_prices = {}
            while True:
                for mkt in get_markets():
                    last_price = None
                    if mkt in last_prices:
                        last_price = last_prices[mkt]
                    price = get_price(mkt)
                    if last_price != price:
                        print "updater: ", time.time(), mkt, price
                        last_prices[mkt] = price
                time.sleep(interval)
        print "Launching price updater thread"
        _updater_thread = threading.Thread(target=updater)
        _updater_thread.daemon = True
        _updater_thread.start()


def get_top_coins(top=10):
    """
    Returns the top market cap coinz....
    """
    pass
    #key = "top_coins_" + str(top)
    #if cache.has_key(key):
    #    return cache.get_val(key)
    #top_coins = [coinmarketcap.short(name) for name in coinmarketcap.top(int(top))]
    #cache.set_val(key, top_coins, expire=3600) # expire every hour
    #return top_coins


def is_cmd(cmd):
    """
    Returns whether specified command is valid.
    """
    cmd_obj = getattr(sys.modules[__name__], cmd)
    is_callable = hasattr(cmd_obj, "__call__")
    is_class = isinstance(cmd_obj, type)
    is_public = not cmd.startswith('_')
    return is_callable and is_public and not is_class


def get_commands():
    """
    Returns all bot commands.

    All the functions in this module are considered bot commands
    unless their names begin with a '_' character.
    """
    return [cmd for cmd in dir(sys.modules[__name__]) if is_cmd(cmd)]


def get_help(*args):
    """
    Returns help for the specified command, which is just it's docstring.
    """
    if len(args) > 0:
        cmd_name = args[0]
        if not cmd_name in get_commands():
            raise CmdError("Invalid command %s" % cmd_name)
        cmd_module = sys.modules[__name__]
        return getattr(cmd_module, cmd_name).__doc__
    else:
        return get_help.__doc__


def exit():
    """
    Exits the process.
    """
    sys.exit()


def _run_cmd(*args):
    """
    Helper function to run a command given command args including the command
    as the first argument.
    """
    if len(args) > 0:
        if not is_cmd(args[0]):
            raise CmdError("Invalid command %s" % args[0])
        cmd = getattr(sys.modules[__name__], args[0])
        return cmd(*args[1:])
    else:
        raise CmdError("No command specified")
