from slackbot.bot import Bot
from slackbot.bot import respond_to
from slackbot.bot import listen_to
from subprocess import check_output, CalledProcessError, STDOUT
import re
import string
import threading
import time

import PriceNetwork
import cmd

import coinmarketcap # for top marketcap coins and stats


class AgentError(PriceNetwork.PriceNetworkError):
    pass


@respond_to('hi', re.IGNORECASE)
def hi(message):
    message.reply('Hello, World!')


@respond_to('about', re.IGNORECASE)
def about(message):
    message.reply('~~~ atxcf agent bot ~~~\ncommands: %s' % cmd.get_commands())


@respond_to('get_symbols')
def get_symbols(message):
    symbols = cmd.get_symbols()
    message.reply(" ".join(sorted(symbols)))


@respond_to('get_price (.*) (.*)', re.IGNORECASE)
def get_price(message, value, trade_pair_str):

    asset_strs = string.split(trade_pair_str,"/",1)
    if len(asset_strs) != 2:
        raise AgentError("Invalid trade pair %s" % trade_pair_str)
    asset_strs = [cur.strip() for cur in asset_strs]

    price = cmd.get_price(value, trade_pair_str)
    r_msg = "{0} {1} for {2} {3}".format(value, asset_strs[0], 
                                         price, asset_strs[1])
    message.reply(r_msg)


@respond_to('get_markets')
def get_markets(message):
    mkts = cmd.get_markets()
    message.reply(" ".join(sorted(mkts)))


@respond_to('get_top_coins$', re.IGNORECASE)
@respond_to('get_top_coins (.*)', re.IGNORECASE)
def get_top_coins(message, top=10):
    top_symbols = cmd.get_top_coins(top)
    message.reply(" ".join(top_symbols))


@respond_to('get_commands$', re.IGNORECASE)
def get_commands(message):
    cmds = cmd.get_commands()
    message.reply(" ".join(sorted(cmds)))



# listen to people talking in the slack and respond with price info
_last_queries_lock = threading.RLock()
_last_queries = {}
_timeout = 5 * 60.0 # don't spam the chat with the same info...

@listen_to('(\w+)/(\w+)', re.IGNORECASE)
def listen_get_pair_price(message, from_asset, to_asset):
    global _last_queries_lock
    global _last_queries
    global _timeout
    
    all_symbols = cmd.get_symbols()
    if from_asset in all_symbols and to_asset in all_symbols:
        pair = from_asset+"/"+to_asset
        last_time = 0.0
        if pair in _last_queries:
            last_time = _last_queries[pair]
        cur_time = time.time()
        if cur_time - last_time > _timeout:
            message.reply("%s/%s: %f" % (from_asset, to_asset, cmd.get_price(pair)))
            _last_queries[pair] = cur_time


@listen_to('\b(\w+)\b', re.IGNORECASE)
def listen_get_price(message, asset):
    global _last_queries_lock
    global _last_queries
    global _timeout

    all_symbols = cmd.get_symbols()
    if asset in all_symbols:
        last_time = 0.0
        if asset in _last_queries:
            last_time = _last_queries[pair]
        cur_time = time.time()
        if cur_time - last_time > _timeout:
            message.reply("%s/BTC: %f" % (asset, cmd.get_price(asset+"/BTC")))
            message.reply("%s/USD: %f" % (asset, cmd.get_price(asset+"/USD")))
            _last_queries[asset+"/BTC"] = cur_time
            _last_queries[asset+"/USD"] = cur_time

#@respond_to('help$', re.IGNORECASE)
#@respond_to('get_help (.*)', re.IGNORECASE)
#@respond_to('get_help$', re.IGNORECASE)
#@respond_to('get_help (.*)', re.IGNORECASE)
#def get_help(message, cmd_str="get_help"):
#    return cmd.get_help(cmd_str)


#@respond_to("run_shell (.*)")
#def run_shell(message, cmd):
#    print "Executing: %s" % cmd
#    out_str = check_output(cmd, stderr=STDOUT,
#                           shell=True)
#    message.reply(out_str)


def main():
    restart = True
    while restart:
        try:
            bot = Bot()
            bot.run()
        except TypeError as e:
            pass
        except Exception:
            restart = False    


if __name__ == "__main__":
    main()
