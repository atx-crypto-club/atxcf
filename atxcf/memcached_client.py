import json
import threading
from pymemcache.client.base import Client
from settings import get_settings_option

def json_serializer(key, value):
    if type(value) == str:
        return value, 1
    return json.dumps(value), 2


def json_deserializer(key, value, flags):
    if flags == 1:
        return value
    if flags == 2:
        return json.loads(value)
    raise Exception("Unknown serialization format")


def enabled():
    """
    Returns whether we are using memcached or not.
    """
    return get_settings_option("using_memcached", True)


def default_key_expiration():
    """
    Returns the default number of seconds a key should
    persist in the cache.
    """
    return int(get_settings_option("memcached_default_key_expiration", default=86400))


def servers():
    """
    Returns a tuple of hostname, port pairs for the memcached servers used.
    """
    return get_settings_option("memcached_servers", default=(("localhost", 11211),))


_client_lock = threading.RLock()
_client = None
def _get_client():
    global _client
    if not _client:
        # TODO: use all the servers listed in the settings file
        _client = Client(tuple(servers()[0]), serializer=json_serializer,
                         deserializer=json_deserializer)
    return _client


# TODO: consider adding expiration times for keys
#       that match a particular regex in the settings file.
#       We might want certain keys to persist longer than others.
def set(some_key, some_value, expire=None):
    if enabled():
        if not expire:
            expire = default_key_expiration()
        with _client_lock:
            _get_client().set(some_key, some_value, expire=expire)


def get(some_key):
    if not enabled():
        return None
    try:
        with _client_lock:
            return _get_client().get(some_key)
    except KeyError:
        return None


def has_key(some_key):
    return get(some_key) != None
