 --^--
/^ ^ ^\
   | O R B I T
   |
 | | http://www.orbitproject.eu/
  U


Introduction
===============

This repository includes a set of patches that aims to introduce I/O 
Hypervisor capabilities in OpenStack Nova by implementing an new nova 
component that integrates IBM's I/O Hypervisor functionality.

The main objective of these I/O Hypervisor is to consolidate resources as well
as to offload CPU cycles to a centralized apliance. The main different from 
Openstack viewpoint is that volumes will be attached to the I/O Hypervisor 
instead of directly to the VMs, and from there they are link to the VMs 
through the network, encapsulated in VMs own VLANS for security reasons. 
Note that, for now, the integration is limited to VLANs networks, but it will
be easily extensible to more advance network configurations, such as VxLANs or
GRE.


Prerequisites
===============

As nova-iorcl main task is to include the I/O hypervisor functionality at 
OpenStack level, the main prerequisite is to have the I/O Hypervisor installed
-- in at leastd one (dedicated) server

These patches are based on the Juno version of Nova. Make sure that your
OpenStack setup is running or is compatible with Nova running Juno.


Installation
===============

To install the OpenStack extended functionality, as well as the new nova-IORCL
component, over an already configured OpenStack (Juno version), the next steps
need to be performed:

* Download the code from the ORBIT EU FP7 github repository:

    * Nova code: https://github.com/orbitfp7/nova/tree/nova-iorcl


* Copy the downloaded code into your current nova source code path -- note 
  this will add new folders and replace some existing files.

* Create the nova-iorcl service daemon file at the I/O Hypervisor servers, in
  `/usr/lib/systemd/system/openstack-nova-iorcl`. The content is:

  ```
  [Unit]
  Description=OpenStack Nova IORCL Server
  After=syslog.target network.target

  [Service]
  Environment=LIBGUESTFS_ATTACH_METHOD=appliance
  Type=notify
  Restart=always
  User=nova
  ExecStart=/usr/bin/nova-iorcl

  [Install]
  WantedBy=multi-user.target
  ```


* Create the nova-dr_orchestrator init script at the I/O Hypervisor servers, 
  in `/usr/bin/`:

  ```
  #!/usr/bin/python

  import sys

  from nova.cmd.iorcl import main


  if __name__ == "__main__":
      sys.exit(main())
  ```


* Restart the affected services in all the workers:

  * sudo systemctl restart [openstack-nova-compute]


* Enable the access to the new I/O Hypervisor APIs at the compute.filters. For
  instance, at `/usr/share/nova/rootwrap/compute.filters`:
  ```
  # nova/iorcl/manager.py:
  iohyp_create_blk_device.sh: CommandFilter, iohyp_create_blk_device.sh, root
  iohyp_remove_blk_device.sh: CommandFilter, iohyp_remove_blk_device.sh, root
  ```

Setting up
===============

* Start the nova-iorcl daemon at the I/O Hypervisor server(s):
	
	* sudo systemctl reload

	* sudo systemctl start openstack-nova-iorcl


Usage
===============

Enabling the use of the I/O Hypervisor is done at instance level, i.e., when 
an instance is created, the user needs to decide if the volumes that will be
attached to it will made use of the I/O Hypervisor or they will be attached
following the normal OpenStack volume attachment flow.

To create a VM ready to use the I/O Hypervisor, the instance need to be 
created with a flavor that specifies the need of using the I/O Hypervisor. To
do so, the `io:enabled=1` needs to be included into the flavor extra_specs. 
This can be done in many ways, for instance, by using the python-novaclient:

* `nova flavor-key FLAVOR_ID set io:enabled=1`

Then, the volume attachment is perform in the same way as the normal volume
attachment in OpenStack, and the I/O Hyp will be use in a fully transparent
manner from the user point of view.
