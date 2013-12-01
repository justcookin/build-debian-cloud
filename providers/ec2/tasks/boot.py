from base import Task
from common import phases
import os


class ConfigurePVGrub(Task):
	description = 'Creating grub config files for PVGrub'
	phase = phases.system_modification

	def run(self, info):
		import stat
		rwxr_xr_x = (stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR |
		             stat.S_IRGRP                | stat.S_IXGRP |
		             stat.S_IROTH                | stat.S_IXOTH)
		x_all = stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH

		grubd = os.path.join(info.root, 'etc/grub.d')
		for cfg in [os.path.join(grubd, f) for f in os.listdir(grubd)]:
			os.chmod(cfg, os.stat(cfg).st_mode & ~ x_all)

		from shutil import copy
		script_src = os.path.normpath(os.path.join(os.path.dirname(__file__), '../assets/grub.d/40_custom'))
		script_dst = os.path.join(info.root, 'etc/grub.d/40_custom')
		copy(script_src, script_dst)
		os.chmod(script_dst, rwxr_xr_x)

		from base.fs.partitionmaps.none import NoPartitions
		if not isinstance(info.volume.partition_map, NoPartitions):
			from common.tools import sed_i
			root_idx = info.volume.partition_map.root.get_index()
			grub_device = 'GRUB_DEVICE=/dev/xvda{idx}'.format(idx=root_idx)
			sed_i(script_dst, '^GRUB_DEVICE=/dev/xvda$', grub_device)
			grub_root = '\troot (hd0,{idx})'.format(idx=root_idx-1)
			sed_i(script_dst, '^\troot \(hd0\)$', grub_root)

		if info.manifest.volume['backing'] == 's3':
			from common.tools import sed_i
			sed_i(script_dst, '^GRUB_DEVICE=/dev/xvda$', 'GRUB_DEVICE=/dev/xvda1')

		from common.tools import sed_i
		grub_def = os.path.join(info.root, 'etc/default/grub')
		sed_i(grub_def, '^GRUB_TIMEOUT=[0-9]+', 'GRUB_TIMEOUT=0\n'
		                                        'GRUB_HIDDEN_TIMEOUT=true')

		from common.tools import log_check_call
		log_check_call(['/usr/sbin/chroot', info.root, '/usr/sbin/update-grub'])
		log_check_call(['/usr/sbin/chroot', info.root,
		                '/bin/ln', '--symbolic', '/boot/grub/grub.cfg', '/boot/grub/menu.lst'])
