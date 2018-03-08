import os
from settings import get_setting

os.environ["SLACKBOT_API_TOKEN"] = get_setting("agent", "api_token", default="")

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

from settings import get_settings_option
from accounts import (
    has_user, add_user, get_user_email, set_user_email
)


class AgentError(PriceNetwork.PriceNetworkError):
    pass


def get_message_user(message):
    """
    Returns the username of the user from whom the messaged originated.
    """
    user_id = message._get_user_id()
    client = message._client
    return client.users[user_id]['name']


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


@respond_to('price (.*)', re.IGNORECASE)
def get_price2(message, trade_pair_str):
    asset_strs = string.split(trade_pair_str,"/",1)
    if len(asset_strs) != 2:
        raise AgentError("Invalid trade pair %s" % trade_pair_str)
    asset_strs = [cur.strip() for cur in asset_strs]

    value = 1.0
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


@respond_to('get_user_email$', re.IGNORECASE)
def _get_user_email(message):
    username = get_message_user(message)
    domain = get_settings_option("domain", default="localhost")
    if not has_user(username):
        add_user(username, "%s@%s" % (username, domain))
    message.reply(get_user_email(username))


@respond_to('set_user_email (.*)$', re.IGNORECASE)
def _set_user_email(message, email):
    username = get_message_user(message)
    if not has_user(username):
        add_user(username, "%s@%s" % (username, domain))
    meta = {
        "user": username,
        "cmd": "set_user_email",
        "args": (email, )
    }
    set_user_email(username, email)
    message.reply("OK")
        

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
