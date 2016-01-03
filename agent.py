from slackbot.bot import Bot
from slackbot.bot import respond_to
from slackbot.bot import listen_to
from subprocess import check_output, CalledProcessError
import re

import prices

@respond_to('hi', re.IGNORECASE)
def hi(message):
    message.reply('Hello, World!')


@respond_to('get_prices')
def get_prices(message):
    # Message is replied to the sender (prefixed with @user)
    p = prices.get_fund_asset_prices()
    message.reply(str(p))
    print p


@respond_to("run_shell (.*)")
def run_shell(message, cmd):
    out_str = "$ %s" % cmd
    message.reply(out_str)
    print out_str


def main():
    bot = Bot()
    bot.run()


if __name__ == "__main__":
    main()
