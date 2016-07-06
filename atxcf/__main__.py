#!/usr/bin/env python
# -*- coding: utf-8 -*-

import webapi
import settings
from . import start_agent
import PriceNetwork

import threading
import sys
import cmd

def _webapi_enabled():
    """
    Returns whether webapi is enabled. It is true by default.
    """
    enabled = False 
    try:
        enabled = settings.get_option("webapi_enabled")
    except settings.SettingsError:
        settings.set_option("webapi_enabled", enabled)
    return enabled 

def _agent_enabled():
    """
    Returns whether the agent slackbot is enabled. It is true by default.
    """
    enabled = False
    try:
        enabled = settings.get_option("agent_enabled")
    except settings.SettingsError:
        settings.set_option("agent_enabled", enabled)
    return enabled 


PriceNetwork.init() # avoid lazy init

webapi_enabled = _webapi_enabled()
agent_enabled = _agent_enabled()

argv = sys.argv[1:]
def _launch_webapi():
    webapi.main(argv[1:])

argc = len(argv)
if argc > 0:
    if argv[0] == "webapi":
        webapi_enabled = True
    elif argv[0] == "agent":
        agent_enabled = True
    else:
        print str(cmd._run_cmd(*argv))
else:
    cmds = cmd.get_commands() + ['webapi', 'agent']
    print "Known commands: {}".format(sorted(cmds))

# webapi thread
wapi_thread = threading.Thread(target=_launch_webapi)
if webapi_enabled:
    wapi_thread.start()

# slackbot atxcf agent thread
agent_thread = threading.Thread(target=start_agent)
if agent_enabled:
    agent_thread.start()

