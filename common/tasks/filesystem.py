from base import Task
from common import phases
from common.tools import log_check_call
from bootstrap import Bootstrap
import volume


class Format(Task):
	description = 'Formatting the volume'
	phase = phases.volume_preparation

	def run(self, info):
		for partition in info.volume.partition_map.partitions:
			partition.format()


class TuneVolumeFS(Task):
	description = 'Tuning the bootstrap volume filesystem'
	phase = phases.volume_preparation
	predecessors = [Format]

	def run(self, info):
		import re
		# Disable the time based filesystem check
		for partition in info.volume.partition_map.partitions:
			if re.match('^ext[2-4]$', partition.filesystem) is not None:
				log_check_call(['/sbin/tune2fs', '-i', '0', partition.device_path])


class AddXFSProgs(Task):
	description = 'Adding `xfsprogs\' to the image packages'
	phase = phases.preparation

	def run(self, info):
		include, exclude = info.img_packages
		include.add('xfsprogs')


class CreateMountDir(Task):
	description = 'Creating mountpoint for the root partition'
	phase = phases.volume_mounting

	def run(self, info):
		import os
		info.root = os.path.join(info.workspace, 'root')
		os.makedirs(info.root)


class MountRoot(Task):
	description = 'Mounting the root partition'
	phase = phases.volume_mounting
	predecessors = [CreateMountDir]

	def run(self, info):
		info.volume.partition_map.root.mount(info.root)


class CreateBootMountDir(Task):
	description = 'Creating mountpoint for the boot partition'
	phase = phases.volume_mounting
	predecessors = [MountRoot]

	def run(self, info):
		import os.path
		os.makedirs(os.path.join(info.root, 'boot'))


class MountBoot(Task):
	description = 'Mounting the boot partition'
	phase = phases.volume_mounting
	predecessors = [CreateBootMountDir]

	def run(self, info):
		p_map = info.volume.partition_map
		p_map.root.add_mount(p_map.boot, 'boot')


class MountSpecials(Task):
	description = 'Mounting special block devices'
	phase = phases.os_installation
	predecessors = [Bootstrap]

	def run(self, info):
		root = info.volume.partition_map.root
		root.add_mount('/dev', 'dev', ['--bind'])
		root.add_mount('none', 'proc', ['--types', 'proc'])
		root.add_mount('none', 'sys', ['--types', 'sysfs'])
		root.add_mount('none', 'dev/pts', ['--types', 'devpts'])


class UnmountRoot(Task):
	description = 'Unmounting the bootstrap volume'
	phase = phases.volume_unmounting
	successors = [volume.Detach]

	def run(self, info):
		info.volume.partition_map.root.unmount()


class DeleteMountDir(Task):
	description = 'Deleting mountpoint for the bootstrap volume'
	phase = phases.volume_unmounting
	predecessors = [UnmountRoot]

	def run(self, info):
		import os
		os.rmdir(info.root)
		del info.root


class FStab(Task):
	description = 'Adding partitions to the fstab'
	phase = phases.system_modification

	def run(self, info):
		import os.path
		p_map = info.volume.partition_map
		mount_points = [{'path': '/',
			               'partition': p_map.root,
			               'dump': '1',
			               'pass_num': '1',
			                }]
		if hasattr(p_map, 'boot'):
			mount_points.append({'path': '/boot',
			                     'partition': p_map.boot,
			                     'dump': '1',
			                     'pass_num': '2',
			                     })
		if hasattr(p_map, 'swap'):
			mount_points.append({'path': 'none',
			                     'partition': p_map.swap,
			                     'dump': '1',
			                     'pass_num': '0',
			                     })

		fstab_lines = []
		for mount_point in mount_points:
			partition = mount_point['partition']
			mount_opts = ['defaults']
			fstab_lines.append('UUID={uuid} {mountpoint} {filesystem} {mount_opts} {dump} {pass_num}'
			                   .format(uuid=partition.get_uuid(),
			                           mountpoint=mount_point['path'],
			                           filesystem=partition.filesystem,
			                           mount_opts=','.join(mount_opts),
			                           dump=mount_point['dump'],
			                           pass_num=mount_point['pass_num']))

		fstab_path = os.path.join(info.root, 'etc/fstab')
		with open(fstab_path, 'w') as fstab:
			fstab.write('\n'.join(fstab_lines))
			fstab.write('\n')
