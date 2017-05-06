"""
Main set of commands known by the atxcf bot.
"""

from PriceNetwork import _get_price_network
import PriceNetwork
import settings
from settings import get_settings_option
import memcached_client

import coinmarketcap

import string
import sys
import threading
import time


_mutex = threading.Lock()
class Mutex(object):
    def __init__(self):
        pass
    def __enter__(self):
        _mutex.acquire()
    def __exit__(self, exc_type, exc_val, exc_tb):
        _mutex.release()


class CmdError(PriceNetwork.PriceNetworkError):
    pass


def get_symbols():
    """
    Returns all asset symbols known by the bot.
    """
    with Mutex():
        pn = _get_price_network()
        return sorted(pn.get_symbols())


def _do_get_price(value, trade_pair_str, get_last=False):        
    asset_strs = string.split(trade_pair_str,"/",1)
    if len(asset_strs) != 2:
        raise CmdError("Invalid trade pair %s" % trade_pair_str)
    asset_strs = [cur.strip() for cur in asset_strs]

    with Mutex():
        pn = _get_price_network()
        price = pn.get_price(asset_strs[0], asset_strs[1], value, get_last)
        if not price:
            price = float('NaN')

        return price


def get_price(*args, **kwargs):
    """
    Returns price dependings on args:
    - 1 == len(args) -> from/to pair string (aka trade_pair_str)
    - 2 == len(args) -> (value, trade_pair_str)
    - 3 == len(args) -> (value, from_asset, to_asset)

    Supports a keyword arg 'get_last' that flags whether we should
    just return the last price cached or if we should try to get an
    updated value.
    """
    value = 1.0
    trade_pair_str = ""
    if len(args) == 1:
        # treat args as a from/to pair with amount == 1
        value = 1.0
        trade_pair_str = args[0]
    elif len(args) == 2:
        # treat args as a pair of (value, trade_pair_str)
        value = float(args[0])
        trade_pair_str = args[1]
    elif len(args) == 3:
        # treat args as a triple of (value, from_asset, to_asset)
        value = float(args[0])
        from_asset = args[1].strip()
        to_asset = args[2].strip()
        trade_pair_str = "%s/%s" % (from_asset, to_asset)
    else:
        raise CmdError("Invalid argument list for command get_price: %s" % str(args))
    get_last = True
    if "get_last" in kwargs:
        get_last = kwargs["get_last"]
    return _do_get_price(value, trade_pair_str, get_last)


_updater_thread = None
def keep_prices_updated():
    """
    Launches a thread to keep prices in the cache updated.
    """
    global _updater_thread
    if not _updater_thread:
        def updater():
            interval = get_settings_option("price_update_interval", 60)
            last_prices = {}
            while True:
                for mkt in get_markets():
                    last_price = None
                    if mkt in last_prices:
                        last_price = last_prices[mkt]
                    price = get_price(mkt, get_last=False)
                    if last_price != price:
                        print "updater: ", time.time(), mkt, price
                        last_prices[mkt] = price
                time.sleep(interval)
        print "Launching price updater thread"
        _updater_thread = threading.Thread(target=updater)
        _updater_thread.daemon = True
        _updater_thread.start()


def get_markets():
    """
    Returns all markets known by the bot.
    """
    with Mutex():
        pn = _get_price_network()
        return pn.get_markets()


def get_top_coins(top=10):
    """
    Returns the top market cap coinz....
    """
    return [coinmarketcap.short(name) for name in coinmarketcap.top(int(top))]


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
