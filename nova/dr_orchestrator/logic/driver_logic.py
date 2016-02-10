class Logic(object):
    """The base class that all Logic classes should inherit from."""

    def __init__(self):
        pass

    def get_optimization_actions(self, context, new_resources):
        """Must override get_optimization_actions method for logic to work."""
        msg = _("Driver must implement get_optimization_actions")
        raise NotImplementedError(msg)

