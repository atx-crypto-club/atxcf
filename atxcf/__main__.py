#!/usr/bin/env python
# -*- coding: utf-8 -*-

import webapi
import settings
from settings import get_settings_option
from . import start_agent
import PriceNetwork

import threading
import sys
import cmd

def _webapi_enabled():
    """
    Returns whether webapi is enabled. It is False by default.
    """
    return get_settings_option("webapi_enabled", default=False)

def _agent_enabled():
    """
    Returns whether the agent slackbot is enabled. It is False by default.
    """
    return get_settings_option("agent_enabled", default=False)

def _tornado_enabled():
    """
    Returns whether we are using the tornado server for web api stuff.
    If this is true, it will override using the flask webapi
    """
    return get_settings_option("tornado_enabled", default=False)


def _price_updater_enabled():
    """
    Returns wether we should start the price updater thread.
    """
    return get_settings_option("price_updater_thread_enabled", default=False)


PriceNetwork.init() # avoid lazy init

webapi_enabled = _webapi_enabled()
agent_enabled = _agent_enabled()
tornado_enabled = _tornado_enabled()
price_updater_enabled = _price_updater_enabled()

argv = sys.argv[1:]

# set flags based on initial args
while len(argv) > 0:
    arg = argv[0]
    if arg == "webapi":
        webapi_enabled = True
    elif arg == "nowebapi":
        webapi_enabled = False 
    elif arg == "agent":
        agent_enabled = True
    elif arg == "noagent":
        agent_enabled = False
    elif arg == "tornado":
	tornado_enabled = True
	webapi_enabled = False
    elif arg == "updater":
	price_updater_enabled = True
    elif arg == "noupdater":
	price_updater_enabled = False
    else:
        break
    argv = argv[1:]

if len(argv) > 0:
    print str(cmd._run_cmd(*argv))
else:
    cmds = cmd.get_commands() + ['webapi', 'nowebapi', 'agent', 'noagent',
				 'tornado']
    print "Known commands: {}".format(sorted(cmds))

def _launch_webapi():
    webapi.main(argv[1:])

# webapi thread
wapi_thread = None
if webapi_enabled:
    wapi_thread = threading.Thread(target=_launch_webapi)
    print "Starting webapi thread..."
    wapi_thread.start()

# slackbot atxcf agent thread
agent_thread = None
if agent_enabled:
    agent_thread = threading.Thread(target=start_agent)
    print "Starting slackbot agent thread..."
    agent_thread.start()

# price updater thread
if price_updater_enabled:
    cmd.keep_prices_updated()

# tornado must run in the main thread
if tornado_enabled:
    import tornado_api
    tornado_api.main()
