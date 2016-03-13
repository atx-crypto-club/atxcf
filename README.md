catx agent bot
--------------

Makes price info available to the [ATX Crypto Club] slack and a web API used by [catx.io]. Prices are currently based on last exchange price and not order book availability (yet).

Module deps:

  - slackbot
  - flask
  - flask-cors
  - pyquery
  - networkx
  - coinmarketcap
  - filelock
  - krakenex (optional for now)

This thing is a work in progress and has known issues like being slow and crashy especially after a storm of get_price requests (like in the web API case). I usually run it with the following script:

    #!/bin/bash
    export SLACKBOT_API_TOKEN="<your slackbot API token>"
    until python agent.py; do
        echo "Server 'agent.py' crashed with exit code $?.  Respawning.." >&2
        sleep 1
    done

I recommend running webapi.py similarly (doesn't need the API token for that case).

**Supported commands**

  - get_symbols - Returns a list of known cryptocurrency and asset symbols. Assets are prefixed by an underscore.
  - get_markets - Returns a list of asset pairs for known markets
  - get_price - Returns the amount of an asset you would get given some amount of another asset in exchange.
  - get_top_coins - Returns the top N coin symbols (where N defaults to 10) in terms of market cap.

  [catx.io]: http://catx.io/
  [ATX Crypto Club]: http://atxcf.slack.com/
