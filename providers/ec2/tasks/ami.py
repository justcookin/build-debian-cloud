from base import Task
from common import phases
from common.exceptions import TaskError
from common.tools import log_check_call
from ebs import Snapshot
from common.tasks import workspace
from connection import Connect
import os.path

cert_ec2 = os.path.normpath(os.path.join(os.path.dirname(__file__), '../assets/certs/cert-ec2.pem'))


class AMIName(Task):
	description = 'Determining the AMI name'
	phase = phases.preparation
	predecessors = [Connect]

	def run(self, info):
		image_vars = {'release':        info.manifest.system['release'],
		              'architecture':   info.manifest.system['architecture'],
		              'virtualization': info.manifest.virtualization,
		              'backing':        info.manifest.volume['backing']}
		from datetime import datetime
		now = datetime.now()
		time_vars = ['%a', '%A', '%b', '%B', '%c', '%d', '%f', '%H',
		             '%I', '%j', '%m', '%M', '%p', '%S', '%U', '%w',
		             '%W', '%x', '%X', '%y', '%Y', '%z', '%Z']
		for var in time_vars:
			image_vars[var] = now.strftime(var)

		ami_name = info.manifest.image['name'].format(**image_vars)
		ami_description = info.manifest.image['description'].format(**image_vars)

		images = info.connection.get_all_images()
		for image in images:
			if ami_name == image.name:
				msg = 'An image by the name {ami_name} already exists.'.format(ami_name=ami_name)
				raise TaskError(msg)
		info.ami_name = ami_name
		info.ami_description = ami_description


class BundleImage(Task):
	description = 'Bundling the image'
	phase = phases.image_registration

	def run(self, info):
		bundle_name = 'bundle-{id:x}'.format(id=info.run_id)
		info.bundle_path = os.path.join(info.workspace, bundle_name)
		log_check_call(['/usr/bin/euca-bundle-image',
		                '--image', info.volume.image_path,
		                '--user', info.credentials['user-id'],
		                '--privatekey', info.credentials['private-key'],
		                '--cert', info.credentials['certificate'],
		                '--ec2cert', cert_ec2,
		                '--destination', info.bundle_path,
		                '--prefix', info.ami_name])


class UploadImage(Task):
	description = 'Uploading the image bundle'
	phase = phases.image_registration
	predecessors = [BundleImage]

	def run(self, info):
		manifest_file = os.path.join(info.bundle_path, info.ami_name + '.manifest.xml')
		if info.host['region'] == 'us-east-1':
			s3_url = 'https://s3.amazonaws.com/'
		else:
			s3_url = 'https://s3-{region}.amazonaws.com/'.format(region=info.host['region'])
		log_check_call(['/usr/bin/euca-upload-bundle',
		                '--bucket', info.manifest.image['bucket'],
		                '--manifest', manifest_file,
		                '--access-key', info.credentials['access-key'],
		                '--secret-key', info.credentials['secret-key'],
		                '--url', s3_url,
		                '--region', info.host['region'],
		                '--ec2cert', cert_ec2])


class RemoveBundle(Task):
	description = 'Removing the bundle files'
	phase = phases.cleaning
	successors = [workspace.DeleteWorkspace]

	def run(self, info):
		from shutil import rmtree
		rmtree(info.bundle_path)
		del info.bundle_path


class RegisterAMI(Task):
	description = 'Registering the image as an AMI'
	phase = phases.image_registration
	predecessors = [Snapshot, UploadImage]

	# Source: http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/UserProvidedKernels.html#AmazonKernelImageIDs
	kernel_mapping = {'ap-northeast-1': {  # Asia Pacific (Tokyo) Region
	                  'hd0':  {'i386':  'aki-136bf512',   # pv-grub-hd0_1.04-i386.gz
	                           'amd64': 'aki-176bf516'},  # pv-grub-hd0_1.04-x86_64.gz
	                  'hd00': {'i386':  'aki-196bf518',   # pv-grub-hd00_1.04-i386.gz
	                           'amd64': 'aki-1f6bf51e'}   # pv-grub-hd00_1.04-x86_64.gz
	                  },
	                  'ap-southeast-1': {  # Asia Pacific (Singapore) Region
	                  'hd0':  {'i386':  'aki-ae3973fc',   # pv-grub-hd0_1.04-i386.gz
	                           'amd64': 'aki-503e7402'},  # pv-grub-hd0_1.04-x86_64.gz
	                  'hd00': {'i386':  'aki-563e7404',   # pv-grub-hd00_1.04-i386.gz
	                           'amd64': 'aki-5e3e740c'}   # pv-grub-hd00_1.04-x86_64.gz
	                  },
	                  'ap-southeast-2': {  # Asia Pacific (Sydney) Region
	                  'hd0':  {'i386':  'aki-cd62fff7',   # pv-grub-hd0_1.04-i386.gz
	                           'amd64': 'aki-c362fff9'},  # pv-grub-hd0_1.04-x86_64.gz
	                  'hd00': {'i386':  'aki-c162fffb',   # pv-grub-hd00_1.04-i386.gz
	                           'amd64': 'aki-3b1d8001'}   # pv-grub-hd00_1.04-x86_64.gz
	                  },
	                  'eu-west-1': {  # EU (Ireland) Region
	                  'hd0':  {'i386':  'aki-68a3451f',   # pv-grub-hd0_1.04-i386.gz
	                           'amd64': 'aki-52a34525'},  # pv-grub-hd0_1.04-x86_64.gz
	                  'hd00': {'i386':  'aki-5ea34529',   # pv-grub-hd00_1.04-i386.gz
	                           'amd64': 'aki-58a3452f'}   # pv-grub-hd00_1.04-x86_64.gz
	                  },
	                  'sa-east-1': {  # South America (Sao Paulo) Region
	                  'hd0':  {'i386':  'aki-5b53f446',   # pv-grub-hd0_1.04-i386.gz
	                           'amd64': 'aki-5553f448'},  # pv-grub-hd0_1.04-x86_64.gz
	                  'hd00': {'i386':  'aki-5753f44a',   # pv-grub-hd00_1.04-i386.gz
	                           'amd64': 'aki-5153f44c'}   # pv-grub-hd00_1.04-x86_64.gz
	                  },
	                  'us-east-1': {  # US East (Northern Virginia) Region
	                  'hd0':  {'i386':  'aki-8f9dcae6',   # pv-grub-hd0_1.04-i386.gz
	                           'amd64': 'aki-919dcaf8'},  # pv-grub-hd0_1.04-x86_64.gz
	                  'hd00': {'i386':  'aki-659ccb0c',   # pv-grub-hd00_1.04-i386.gz
	                           'amd64': 'aki-499ccb20'}   # pv-grub-hd00_1.04-x86_64.gz
	                  },
	                  'us-gov-west-1': {  # AWS GovCloud (US)
	                  'hd0':  {'i386':  'aki-1fe98d3c',   # pv-grub-hd0_1.04-i386.gz
	                           'amd64': 'aki-1de98d3e'},  # pv-grub-hd0_1.04-x86_64.gz
	                  'hd00': {'i386':  'aki-63e98d40',   # pv-grub-hd00_1.04-i386.gz
	                           'amd64': 'aki-61e98d42'}   # pv-grub-hd00_1.04-x86_64.gz
	                  },
	                  'us-west-1': {  # US West (Northern California) Region
	                  'hd0':  {'i386':  'aki-8e0531cb',   # pv-grub-hd0_1.04-i386.gz
	                           'amd64': 'aki-880531cd'},  # pv-grub-hd0_1.04-x86_64.gz
	                  'hd00': {'i386':  'aki-960531d3',   # pv-grub-hd00_1.04-i386.gz
	                           'amd64': 'aki-920531d7'}   # pv-grub-hd00_1.04-x86_64.gz
	                  },
	                  'us-west-2': {  # US West (Oregon) Region
	                  'hd0':  {'i386':  'aki-f08f11c0',   # pv-grub-hd0_1.04-i386.gz
	                           'amd64': 'aki-fc8f11cc'},  # pv-grub-hd0_1.04-x86_64.gz
	                  'hd00': {'i386':  'aki-e28f11d2',   # pv-grub-hd00_1.04-i386.gz
	                           'amd64': 'aki-e68f11d6'}   # pv-grub-hd00_1.04-x86_64.gz
	                  }}

	def run(self, info):
		if info.manifest.volume['backing'] == 'ebs':
			self.run_ebs(info)
		if info.manifest.volume['backing'] == 's3':
			self.run_s3(info)

	def run_ebs(self, info):
		arch = {'i386': 'i386', 'amd64': 'x86_64'}.get(info.manifest.system['architecture'])

		from base.fs.partitionmaps.none import NoPartitions
		if isinstance(info.volume.partition_map, NoPartitions):
			grub_boot_device = 'hd0'
			root_device_name = '/dev/sda'
		else:
			grub_boot_device = 'hd00'
			root_idx = info.volume.partition_map.root.get_index()
			root_device_name = '/dev/sda{idx}'.format(idx=root_idx)

		kernel_id = (self.kernel_mapping
		             .get(info.host['region'])
		             .get(grub_boot_device)
		             .get(info.manifest.system['architecture']))

		from boto.ec2.blockdevicemapping import BlockDeviceType
		from boto.ec2.blockdevicemapping import BlockDeviceMapping
		block_device = BlockDeviceType(snapshot_id=info.snapshot.id, delete_on_termination=True,
		                               size=info.volume.partition_map.get_total_size()/1024)
		block_device_map = BlockDeviceMapping()
		block_device_map['/dev/sda'] = block_device

		if info.manifest.virtualization == 'pvm':
			virtualization = 'paravirtual'
		else:
			virtualization = 'hvm'

		info.image = info.connection.register_image(name=info.ami_name, description=info.ami_description,
		                                            architecture=arch, kernel_id=kernel_id,
		                                            root_device_name=root_device_name,
		                                            block_device_map=block_device_map,
		                                            virtualization=virtualization)

	def run_s3(self, info):
		arch = {'i386': 'i386', 'amd64': 'x86_64'}.get(info.manifest.system['architecture'])

		kernel_id = (self.kernel_mapping
		             .get(info.host['region'])
		             .get('hd0')
		             .get(info.manifest.system['architecture']))

		image_manifest = ('{bucket}/{ami_name}.manifest.xml'
		                  .format(bucket=info.manifest.image['bucket'],
		                          ami_name=info.ami_name))

		if info.manifest.virtualization == 'pvm':
			virtualization = 'paravirtual'
		else:
			virtualization = 'hvm'

		info.image = info.connection.register_image(name=info.ami_name, description=info.ami_description,
		                                            architecture=arch, kernel_id=kernel_id,
		                                            root_device_name='dev/sda1',
		                                            image_location=image_manifest,
		                                            virtualization=virtualization)
