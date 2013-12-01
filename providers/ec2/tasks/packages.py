from base import Task
from common import phases
from common.tasks import packages
from common.tasks.host import CheckPackages


class HostPackages(Task):
	description = 'Adding more required host packages'
	phase = phases.preparation
	predecessors = [packages.HostPackages]
	successors = [CheckPackages]

	def run(self, info):
		if info.manifest.volume['backing'] == 's3':
			info.host_packages.add('euca2ools')


class ImagePackages(Task):
	description = 'Adding more required image packages'
	phase = phases.preparation
	predecessors = [packages.ImagePackages]

	def run(self, info):
		manifest = info.manifest
		include, exclude = info.img_packages
		include.add('openssh-server')
		include.add('file')  # Needed for the init scripts
		include.add('dhcpcd')  # isc-dhcp-client doesn't work properly with ec2
		include.add('grub-pc')

		exclude.add('isc-dhcp-client')
		exclude.add('isc-dhcp-common')

		# In squeeze, we need a special kernel flavor for xen
		kernels = {'squeeze': {'amd64': 'linux-image-xen-amd64',
		                       'i386':  'linux-image-xen-686', },
		           'wheezy':  {'amd64': 'linux-image-amd64',
		                       'i386':  'linux-image-686', }, }
		include.add(kernels.get(manifest.system['release']).get(manifest.system['architecture']))
