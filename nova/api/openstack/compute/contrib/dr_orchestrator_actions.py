"""The DR-Orchestrator extension."""

from oslo.config import cfg
import webob
from webob import exc
from nova.api.openstack import extensions as exts
from nova.api.openstack import wsgi

from nova import exception
from nova.openstack.common.gettextutils import _

#from nova.dr_orchestrator import api as dr_orchestrator_api
from nova import dr_orchestrator

auth_protect_volume = exts.extension_authorizer('compute', 'protect_volume')
auth_protect_vm = exts.extension_authorizer('compute', 'protect_vm')
auth_recover = exts.extension_authorizer('compute', 'recover')


class DROrchestratorProtectController(wsgi.Controller):
    def __init__(self, *args, **kwargs):
        super(DROrchestratorProtectController, 
                                       self).__init__(*args, **kwargs)
        self.dr_orchestrator_api = dr_orchestrator.API()


    @wsgi.action('drProtectVM')
    def _protect_vm(self, req, id, body):
        """Protect a VM instance."""
        context = req.environ["nova.context"]
        auth_protect_vm(context)

        try:
            self.dr_orchestrator_api.protect(context, id, "Instance")
        except exception.InstanceNotFound:
            msg = _("Server not found")
            raise exc.HTTPNotFound(explanation=msg)
        except exception.DROrchestrationInstanceNotActive as e:
            raise exc.HTTPConflict(explanation=e.format_message())
        except exception.DROrchestrationUnknownResourceType as e:
            raise exc.HTTPBadRequest(explanation=e.format_message())
        except exception.DROrchestrationNoNetworkCapacity as e:
            raise exc.HTTPForbidden(explanation=e.format_message())

        return webob.Response(status_int=202)


    @wsgi.action('drProtectVolume')
    def _protect_volume(self, req, id, body):
        """Protect a Volume."""
        context = req.environ["nova.context"]
        auth_protect_volume(context)

        try:
            self.dr_orchestrator_api.protect(context, id, "Volume")
        except exception.NotFound as e:
            raise exc.HTTPNotFound(explanation=e.format_message())
        except exception.DROrchestrationVolumeNotAvailable as e:
            raise exc.HTTPConflict(explanation=e.format_message())
        except exception.DROrchestrationUnknownResourceType as e:
            raise exc.HTTPBadRequest(explanation=e.format_message())
        except exception.DROrchestrationNoNetworkCapacity as e:
            raise exc.HTTPForbidden(explanation=e.format_message())

        return webob.Response(status_int=202)


class DROrchestratorRecoverController(wsgi.Controller):
    def __init__(self, *args, **kwargs):
        super(DROrchestratorRecoverController, self).__init__(*args, **kwargs)
        self.dr_orchestrator_api = dr_orchestrator.API()

    @wsgi.action('drRecover')
    def _recover(self, req, id, body):
        """Recover a failed datacenter."""
        context = req.environ["nova.context"]
        auth_recover(context)

        datacenter = id #body["dr-recover"]["datacenter"]

        try:
            self.dr_orchestrator_api.recover(context, datacenter)
        except exception.DROrchestratorDatacenterNotFound as e:
            raise exc.HTTPBadRequest(explanation=e.format_message())

        return webob.Response(status_int=202)


class Dr_orchestrator_actions(exts.ExtensionDescriptor):
    """DR_Orchestrator actions."""

    name = "DROrchestrator"
    alias = "os-dr-orchestrator"
    namespace = "http://docs.openstack.org/compute/ext/dr-orchestrator-actions/api/v1.0"
    updated = "2015-06-08T00:00:00+00:00"

    def get_controller_extensions(self):
        extensions = []

        controller = DROrchestratorProtectController()
        extension = exts.ControllerExtension(self, 'servers', controller)
        extensions.append(extension)

        controller = DROrchestratorRecoverController()
        extension = exts.ControllerExtension(self, 'servers', controller)
        extensions.append(extension)

        return extensions


