from oslo.config import cfg

from nova.openstack.common import importutils


logic_driver_opts = [
    cfg.StrOpt('logic_driver',
            default='nova.dr_orchestrator.logic.dummy_logic.DummyLogic',
            help='Default drivar to use for the logic optimization.'),
]

CONF = cfg.CONF
CONF.register_opts(logic_driver_opts)


class Logic():
    """Create the LOGIC object based on the default logic to use."""

    def __init__(self, logic_driver=None, *args, **kwargs):
        if not logic_driver:
            logic_driver = CONF.logic_driver
        self.driver = importutils.import_object(logic_driver)


    def get_optimization_actions(self, context, new_resources):
        return self.driver.get_optimization_actions(context, new_resources)
 
