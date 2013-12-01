from base import Task
from common import phases
from common.tasks import apt
import os.path


class BlackListModules(Task):
	description = 'Blacklisting kernel modules'
	phase = phases.system_modification

	def run(self, info):
		blacklist_path = os.path.join(info.root, 'etc/modprobe.d/blacklist.conf')
		with open(blacklist_path, 'a') as blacklist:
			blacklist.write(('# disable pc speaker\n'
			                 'blacklist pcspkr'))


class DisableGetTTYs(Task):
	description = 'Disabling getty processes'
	phase = phases.system_modification

	def run(self, info):
		from common.tools import sed_i
		inittab_path = os.path.join(info.root, 'etc/inittab')
		tty1 = '1:2345:respawn:/sbin/getty 38400 tty1'
		sed_i(inittab_path, '^' + tty1, '#' + tty1)
		ttyx = ':23:respawn:/sbin/getty 38400 tty'
		for i in range(2, 7):
			i = str(i)
			sed_i(inittab_path, '^' + i + ttyx + i, '#' + i + ttyx + i)


class InstallGrub(Task):
	description = 'Installing grub'
	phase = phases.system_modification
	predecessors = [apt.AptUpgrade]

	def run(self, info):
		from common.fs.loopbackvolume import LoopbackVolume
		from common.tools import log_check_call

		boot_dir = os.path.join(info.root, 'boot')
		grub_dir = os.path.join(boot_dir, 'grub')

		from base.fs.partitionmaps.none import NoPartitions
		from base.fs.partitionmaps.gpt import GPTPartitionMap
		from common.fs import remount
		p_map = info.volume.partition_map

		def link_fn():
			info.volume.link_dm_node()
			if isinstance(p_map, NoPartitions):
				p_map.root.device_path = info.volume.device_path

		def unlink_fn():
			info.volume.unlink_dm_node()
			if isinstance(p_map, NoPartitions):
				p_map.root.device_path = info.volume.device_path

		# GRUB cannot deal with installing to loopback devices
		# so we fake a real harddisk with dmsetup.
		# Guide here: http://ebroder.net/2009/08/04/installing-grub-onto-a-disk-image/
		if isinstance(info.volume, LoopbackVolume):
			remount(info.volume, link_fn)
		try:
			[device_path] = log_check_call(['readlink', '-f', info.volume.device_path])
			device_map_path = os.path.join(grub_dir, 'device.map')
			partition_prefix = 'msdos'
			if isinstance(p_map, GPTPartitionMap):
				partition_prefix = 'gpt'
			with open(device_map_path, 'w') as device_map:
				device_map.write('(hd0) {device_path}\n'.format(device_path=device_path))
				if not isinstance(p_map, NoPartitions):
					for idx, partition in enumerate(info.volume.partition_map.partitions):
						[partition_path] = log_check_call(['readlink', '-f', partition.device_path])
						device_map.write('(hd0,{prefix}{idx}) {device_path}\n'
						                 .format(device_path=partition_path, prefix=partition_prefix, idx=idx+1))

			# Install grub
			log_check_call(['/usr/sbin/chroot', info.root,
			                '/usr/sbin/grub-install',
			                # '--root-directory=' + info.root,
			                # '--boot-directory=' + boot_dir,
			                device_path])
			log_check_call(['/usr/sbin/chroot', info.root, '/usr/sbin/update-grub'])
		except Exception as e:
			if isinstance(info.volume, LoopbackVolume):
				remount(info.volume, unlink_fn)
			raise e

		if isinstance(info.volume, LoopbackVolume):
			remount(info.volume, unlink_fn)
