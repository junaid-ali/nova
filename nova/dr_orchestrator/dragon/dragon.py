"""
Handles all requests relating to drago.
"""

import copy
import sys
import os

from dragonclient import client as dragon_client

from oslo.config import cfg
import six.moves.urllib.parse as urlparse

from nova.i18n import _
from nova.i18n import _LW
from nova.openstack.common import log as logging
from nova.openstack.common import strutils

from keystoneclient.v2_0 import client as ksclient
from swiftclient import client as swift_client

dragon_opts = [
    cfg.StrOpt('url',
               help='The URL of the dragon endpoint'),
    cfg.IntOpt('url_timeout',
               default=600,
               help='Time out for connection'),
    cfg.StrOpt('admin_username',
               default='admin',
               help='Dragon user name'),
    cfg.StrOpt('admin_tenant_name',
               default='admin',
               help='The tenant to use for dragon'),
    cfg.StrOpt('admin_password',
               help=''),
    cfg.StrOpt('backup_swift_url',
               help='The URL of the Swift endpoint'),
    cfg.StrOpt('backup_swift_key',
               help='Swith key for authentication'),
    cfg.StrOpt('backup_swift_tenant',
               default='admin',
               help='The tenant to use for swift'),
    cfg.StrOpt('backup_swift_user',
               default='admin',
               help='Swift user name'),
]

CONF = cfg.CONF
CONF.register_opts(dragon_opts, group='dragon')


PROJECT_ID = None


def swiftclient(context):
    args = {
            'auth_version': '2.0',
            'tenant_name': CONF.dragon['backup_swift_tenant'],
            'user': CONF.dragon['backup_swift_user'],
            'key': CONF.dragon['backup_swift_key'],
            'authurl': CONF.dragon['backup_swift_url'],
            'retries': 3,
            'starting_backoff': 2
    }

    return swift_client.Connection(**args)


def dragonclient(context):
    global PROJECT_ID
    args = {'auth_version': '2.0',
             'tenant_name': CONF.dragon['admin_tenant_name'],
             'username': CONF.dragon['admin_username'],
             'key': None,
             'auth_url': CONF.dragon['url'],
             'password': CONF.dragon['admin_password'],
             'insecure': False,
             'timeout': CONF.dragon['url_timeout'],
             'cert_file': None,
             }

    keystone_client = _get_ksclient(**args)


    endpoint = keystone_client.service_catalog.url_for(service_type='dr',
                                                endpoint_type='publicURL')

    args["token"] =  keystone_client.auth_token
    args["auth_token"] = keystone_client.auth_token
    args["project"] = keystone_client.tenant_id
    PROJECT_ID = keystone_client.tenant_id

    c = dragon_client.Client("1", endpoint, **args)

    return c


def _get_ksclient(**kwargs):
    """Get an endpoint and auth token from Keystone.

    :param username: name of user
    :param password: user's password
    :param tenant_id: unique identifier of tenant
    :param tenant_name: name of tenant
    :param auth_url: endpoint to authenticate against
    """
    return ksclient.Client(username=kwargs.get('username'),
                           password=kwargs.get('password'),
                           tenant_id=kwargs.get('tenant_id'),
                           tenant_name=kwargs.get('tenant_name'),
                           auth_url=kwargs.get('auth_url'),
                           insecure=kwargs.get('insecure'))


class API(object):
    """API for interacting with the dragon manager."""

    def list_actions(self, context, resource_type_id):
        item = dragonclient(context).dr.list_actions(resource_type_id)
        return item

    def list_workload_policies(self, context):
        item = dragonclient(context).dr.list_workload_policies()
        return item

    def list_policy_executions(self, context, policy_id):
        item = dragonclient(context).dr.list_policy_executions(policy_id)
        return item


    def get_resource(self, context, resource_id):
        item = dragonclient(context).dr.get_resource(resource_id)
        return item

    def get_resource_action(self, context, policy_id, resource_id):
        item = dragonclient(context).dr.get_policy_resource_action(
                                                               policy_id,
                                                               resource_id)
        return item


    def create_workload_policy(self, context, policy_name):
        item = dragonclient(context).dr.create_workload_policy(policy_name,
                                                               PROJECT_ID)
        return item

    def create_resource(self, context, resource_id, resource_name, 
                        resource_type):
        item = dragonclient(context).dr.create_resource(resource_id, 
                                                        resource_name,
                                                        resource_type)

    def create_resource_action(self, context, resource_id, action_id, 
                               policy_id):
        item = dragonclient(context).dr.create_resource_action(resource_id,
                                                               action_id,
                                                               policy_id)


    def protect(self, context, policy_id):
        item = dragonclient(context).dr.protect(policy_id)


    def recovery_list_policy_executions(self, context, policy):
        item = dragonclient(context).dr.recovery_list_policy_executions(
                                            policy)
        return item

    def recover(self, context, container_id):
        item = dragonclient(context).dr.recover(container_id)

    def recovery_list_policies(self, context):
        item = dragonclient(context).dr.recovery_list_policies()
        return item


    def delete_policy_execution(self, context, policy_execution_id):
        for data in swiftclient(context).get_container(policy_execution_id)[1]:
            swiftclient(context).delete_object(policy_execution_id, 
                                               data['name'])
        swiftclient(context).delete_container(policy_execution_id)

