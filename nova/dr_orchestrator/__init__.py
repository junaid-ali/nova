import oslo.config.cfg

from nova.dr_orchestrator import api as dr_orchestrator_api


def API(*args, **kwargs):
    api = dr_orchestrator_api.API
    return api(*args, **kwargs)

