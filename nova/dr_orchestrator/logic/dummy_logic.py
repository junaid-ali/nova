from nova.dr_orchestrator.logic import driver_logic

class DummyLogic(driver_logic.Logic):
    """Dummy Logic implementation.

    It just returns protect (if previous one already finished)
    and include all resources.
    """
    def __init__(self, *args, **kwargs):
        super(DummyLogic, self).__init__(*args, **kwargs)

    def get_optimization_actions(self, context, new_resources):
        """ returns triggerProect and resources_to_include. """
        return False, new_resources

        

