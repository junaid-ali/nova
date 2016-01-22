from nova.dr_orchestrator.logic import driver_logic

class MPCLogic(driver_logic.Logic):
    """MPC Logic implementation.

    It execute the MPC controller and applies the output actions.

    It also returns protect and includes all resources.
    """
    def __init__(self, *args, **kwargs):
        super(MPCLogic, self).__init__(*args, **kwargs)

    def get_optimization_actions(self, context, new_resources):
        """ perform the network traffic shaping. """
        self._optimize_traffic_sharing()

        """ returns triggerProtect and resources_to_include. """
        return False, new_resources


    #########################################
    def _optimize_traffic_sharing(self):
        ids_to_control = self._get_ids()

        traffic_performance_metrics = self._get_performance_metrics(
                                                ids_to_control)

        # execute MPC controller with current values
        traffic_shaping_actions = self._run_MPC_controller(
                                           traffic_performance_metrics)


        # apply the controller actions
        self._update_traffic_shares(traffic_shaping_actions)


    def _get_ids(self):
        # it should get the IDs from the system (DRBD and image_copy daemons)
        # but for now it just reads them from a file
        pass


    def _get_performance_metrics(self, ids_to_control):
        # it gets the next performance metrics for the IDs to control:
        # ...
        pass


    def _run_MPC_controller(self, traffic_performance_metrics):
        # execute Jonas code
        pass


    def _update_traffic_shares(self, traffic_shaping_actions):
        # applies the output of the controller
        pass

        

