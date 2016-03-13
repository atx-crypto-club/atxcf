from slackbot.bot import Bot
from slackbot.bot import respond_to
from slackbot.bot import listen_to
from subprocess import check_output, CalledProcessError, STDOUT
import re
import string

import PriceNetwork

import coinmarketcap # for top marketcap coins and stats


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


@respond_to('hi', re.IGNORECASE)
def hi(message):
    message.reply('Hello, World!')


@respond_to('about', re.IGNORECASE)
def hi(message):
    message.reply('~~~ atxcf agent bot ~~~')


@respond_to('get_symbols')
def get_symbols(message):
    pn = _get_price_network()
    symbols = pn.get_symbols()
    message.reply(" ".join(sorted(symbols)))


@respond_to('get_price (.*) (.*)', re.IGNORECASE)
def get_price(message, value, trade_pair_str):
    #price = prices.get_price(value, trade_pair_str)

    asset_strs = string.split(trade_pair_str,"/",1)
    if len(asset_strs) != 2:
        raise RuntimeError("Invalid trade_pair_str %s" % trade_pair_str)
    asset_strs = [cur.strip() for cur in asset_strs]

    pn = _get_price_network()
    price = pn.get_price(asset_strs[0], asset_strs[1], value)
    r_msg = "{0} {1} for {2} {3}".format(value, asset_strs[0], 
                                         price, asset_strs[1])
    message.reply(r_msg)


@respond_to('get_markets')
def get_markets(message):
    pn = _get_price_network()
    mkts = pn.get_markets()
    message.reply(" ".join(sorted(mkts)))


@respond_to('get_top_coins$', re.IGNORECASE)
@respond_to('get_top_coins (.*)', re.IGNORECASE)
def get_top_coins(message, top=10):
    top_symbols = [coinmarketcap.short(name) for name in coinmarketcap.top(int(top))]
    message.reply(" ".join(top_symbols))


#@respond_to("run_shell (.*)")
#def run_shell(message, cmd):
#    print "Executing: %s" % cmd
#    out_str = check_output(cmd, stderr=STDOUT,
#                           shell=True)
#    message.reply(out_str)


def main():
    bot = Bot()
    init() # make sure the price network is available
    bot.run()


if __name__ == "__main__":
    main()
