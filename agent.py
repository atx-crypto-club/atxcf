from slackbot.bot import Bot
from slackbot.bot import respond_to
from slackbot.bot import listen_to
import re

@respond_to('hi', re.IGNORECASE)
def hi(message):
    message.reply('Hello, World!')

@listen_to('prices')
def help(message):
    # Message is replied to the sender (prefixed with @user)
    message.reply('Coming soon!')

def main():
    bot = Bot()
    bot.run()

if __name__ == "__main__":
    main()
