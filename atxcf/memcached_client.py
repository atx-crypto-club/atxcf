import json
import threading
from pymemcache.client.base import Client
import settings


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
    return settings.get_option("using_memcached")


def default_key_expiration():
    """
    Returns the default number of seconds a key should
    persist in the cache.
    """
    return int(settings.get_option("memcached_default_key_expiration"))


def servers():
    """
    Returns a tuple of hostname, port pairs for the memcached servers used.
    """
    return settings.get_option("memcached_servers")


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


# Initialize default setting options for memcached_client
# if they aren't present.
# TODO: clean this up
if not settings.has_option("using_memcached"):
    settings.set_option("using_memcached", True)
if not settings.has_option("memcached_default_key_expiration"):
    settings.set_option("memcached_default_key_expiration", 60)
if not settings.has_option("memcached_servers"):
    settings.set_option("memcached_servers", [("localhost", 11211)])
