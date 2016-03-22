"""
Main set of commands known by the atxcf bot.
"""

import PriceNetwork
import settings

import coinmarketcap

import string


class CmdError(PriceNetwork.PriceNetworkError):
    pass


_pn = None
def init():
    global _pn
    _pn = PriceNetwork.PriceNetwork()
    _pn.init_graph()


def _get_price_network():
    global _pn
    if not _pn:
        init()
    return _pn


def get_symbols():
    """
    Returns all asset symbols known by the bot.
    """
    pn = _get_price_network()
    return pn.get_symbols()


def get_price(*args):
    """
    Returns price dependings on args:
    - 1 == len(args) -> from/to pair string (aka trade_pair_str)
    - 2 == len(args) -> (value, trade_pair_str)
    - 3 == len(args) -> (value, from_asset, to_asset)
    """

    def _do_get_price(value, trade_pair_str):
        asset_strs = string.split(trade_pair_str,"/",1)
        if len(asset_strs) != 2:
            raise CmdError("Invalid trade pair %s" % trade_pair_str)
        asset_strs = [cur.strip() for cur in asset_strs]

        pn = _get_price_network()
        return pn.get_price(asset_strs[0], asset_strs[1], value)

    if len(args) == 1:
        # treat args as a from/to pair with amount == 1
        value = 1.0
        trade_pair_str = args[0]
        return _do_get_price(value, trade_pair_str)
    elif len(args) == 2:
        # treat args as a pair of (value, trade_pair_str)
        value = float(args[0])
        trade_pair_str = args[1]
        return _do_get_price(value, trade_pair_str)
    elif len(args) == 3:
        # treat args as a triple of (value, from_asset, to_asset)
        value = float(args[0])
        from_asset = args[1].strip()
        to_asset = args[2].strip()
        trade_pair_str = "%s/%s" % (from_asset, to_asset)
        return _do_get_price(value, trade_pair_str)
    else:
        raise CmdError("Invalid argument list for command get_price: %s" % str(args))


def get_markets():
    """
    Returns all markets known by the bot.
    """
    pn = _get_price_network()
    return pn.get_markets()


def get_top_coins(top=10):
    """
    Returns the top market cap coinz....
    """
    return [coinmarketcap.short(name) for name in coinmarketcap.top(int(top))]
