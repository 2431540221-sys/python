from contextvars import ContextVar


_applying_remote_change = ContextVar("dbsync_applying_remote_change", default=False)


def is_applying_remote_change():
    return _applying_remote_change.get()


def applying_remote_change():
    return _applying_remote_change.set(True)


def reset_applying_remote_change(token):
    _applying_remote_change.reset(token)
