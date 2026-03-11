"""Supervisor addon package."""


def make_supervisor_rpcinterface(supervisord, **config):
    from .rpcinterface import make_supervisor_rpcinterface as _factory

    return _factory(supervisord, **config)


__all__ = ["make_supervisor_rpcinterface"]
