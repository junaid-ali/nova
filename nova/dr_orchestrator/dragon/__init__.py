import oslo.config.cfg

import nova.openstack.common.importutils

_dragon_opts = [
    oslo.config.cfg.StrOpt('dragon_api_class',
                           default='nova.dr_orchestrator.dragon.dragon.API',
                           help='The full class name of the '
                                'dragon API class to use'),
]

oslo.config.cfg.CONF.register_opts(_dragon_opts)


def API():
    importutils = nova.openstack.common.importutils
    dragon_api_class = oslo.config.cfg.CONF.dragon_api_class
    cls = importutils.import_class(dragon_api_class)
    return cls()
