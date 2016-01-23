from slackbot.bot import Bot
from slackbot.bot import respond_to
from slackbot.bot import listen_to
from subprocess import check_output, CalledProcessError, STDOUT
import re
import string

import prices
import PriceNetwork

@respond_to('hi', re.IGNORECASE)
def hi(message):
    message.reply('Hello, World!')


@respond_to('get_prices')
def get_prices(message):
    # Message is replied to the sender (prefixed with @user)
    p = prices.get_fund_asset_prices()
    message.reply(str(p))
    print p


_pn = PriceNetwork.PriceNetwork()

@respond_to('get_symbols')
def get_symbols(message):
    symbols = _pn.get_symbols()
    message.reply(" ".join(sorted(symbols)))


@respond_to('get_price (.*) (.*)', re.IGNORECASE)
def get_price(message, value, trade_pair_str):
    #price = prices.get_price(value, trade_pair_str)

    asset_strs = string.split(trade_pair_str,"/",1)
    if len(asset_strs) != 2:
        raise RuntimeError("Invalid trade_pair_str %s" % trade_pair_str)
    asset_strs = [cur.strip() for cur in asset_strs]

    price = _pn.get_price(asset_strs[0], asset_strs[1], value)
    r_msg = "{0} {1} for {2} {3}".format(value, asset_strs[0], 
                                         price, asset_strs[1])
    message.reply(r_msg)


@respond_to('get_markets')
def get_markets(message):
    mkts = _pn.get_markets()
    message.reply(" ".join(sorted(mkts)))


#@respond_to("run_shell (.*)")
#def run_shell(message, cmd):
#    print "Executing: %s" % cmd
#    out_str = check_output(cmd, stderr=STDOUT,
#                           shell=True)
#    message.reply(out_str)


def main():
    bot = Bot()
    bot.run()


if __name__ == "__main__":
    main()
