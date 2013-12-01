from base import Task
from common import phases
from common.exceptions import TaskError
from common.tools import log_check_call
import os.path


class InstallInitScripts(Task):
	description = 'Installing startup scripts'
	phase = phases.system_modification

	def run(self, info):
		import stat
		rwxr_xr_x = (stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR |
		             stat.S_IRGRP                | stat.S_IXGRP |
		             stat.S_IROTH                | stat.S_IXOTH)
		from shutil import copy
		for name, src in info.initd['install'].iteritems():
			dst = os.path.join(info.root, 'etc/init.d', name)
			copy(src, dst)
			os.chmod(dst, rwxr_xr_x)
			log_check_call(['/usr/sbin/chroot', info.root, '/sbin/insserv', '--default', name])

		for name in info.initd['disable']:
			log_check_call(['/usr/sbin/chroot', info.root, '/sbin/insserv', '--remove', name])


class AddExpandRoot(Task):
	description = 'Adding init scripts to expand the root volume'
	phase = phases.system_modification
	successors = [InstallInitScripts]

	def run(self, info):
		init_scripts_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), '../assets/init.d'))
		info.initd['install']['expand-root'] = os.path.join(init_scripts_dir, 'expand-root')


class AddSSHKeyGeneration(Task):
	description = 'Adding SSH private key generation init scripts'
	phase = phases.system_modification
	successors = [InstallInitScripts]

	def run(self, info):
		init_scripts_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), '../assets/init.d'))
		install = info.initd['install']
		from subprocess import CalledProcessError
		try:
			log_check_call(['/usr/sbin/chroot', info.root,
			                '/usr/bin/dpkg-query', '-W', 'openssh-server'])
			if info.manifest.system['release'] == 'squeeze':
				install['generate-ssh-hostkeys'] = os.path.join(init_scripts_dir, 'squeeze/generate-ssh-hostkeys')
			else:
				install['generate-ssh-hostkeys'] = os.path.join(init_scripts_dir, 'generate-ssh-hostkeys')
		except CalledProcessError:
			pass


class RemoveHWClock(Task):
	description = 'Removing hardware clock init scripts'
	phase = phases.system_modification
	successors = [InstallInitScripts]

	def run(self, info):
		info.initd['disable'].append(['hwclock.sh'])
		if info.manifest.system['release'] == 'squeeze':
			info.initd['disable'].append('hwclockfirst.sh')


class AdjustExpandRootScript(Task):
	description = 'Adjusting the expand-root script'
	phase = phases.system_modification
	predecessors = [InstallInitScripts]

	def run(self, info):
		if 'expand-root' not in info.initd['install']:
			raise TaskError('The expand-root script was not installed')

		from base.fs.partitionmaps.none import NoPartitions
		if not isinstance(info.volume.partition_map, NoPartitions):
			import os.path
			from common.tools import sed_i
			script = os.path.join(info.root, 'etc/init.d.expand-root')
			root_idx = info.volume.partition_map.root.get_index()
			device_path = 'device_path="/dev/xvda{idx}"'.format(idx=root_idx)
			sed_i(script, '^device_path="/dev/xvda$', device_path)
