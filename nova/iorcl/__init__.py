import oslo.config.cfg

from nova.iorcl import api as iorcl_api


def API(*args, **kwargs):
    use_local = kwargs.pop('use_local', False)
    if oslo.config.cfg.CONF.iorcl.use_local or use_local:
        api = iorcl_api.LocalAPI
    else:
        api = iorcl_api.API
    return api(*args, **kwargs)


def ComputeTaskAPI(*args, **kwargs):
    use_local = kwargs.pop('use_local', False)
    if oslo.config.cfg.CONF.iorcl.use_local or use_local:
        api = iorcl_api.LocalComputeTaskAPI
    else:
        api = iorcl_api.ComputeTaskAPI
    return api(*args, **kwargs)
