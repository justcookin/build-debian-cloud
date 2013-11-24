from base import Task
from common import phases
import os
from common.tasks.packages import ImagePackages
from common.tasks.host import CheckPackages
from common.tasks.filesystem import MountRoot


class AddUserPackages(Task):
	description = 'Adding user defined packages to the image packages'
	phase = phases.preparation
	predecessors = [ImagePackages]
	successors = [CheckPackages]

	def run(self, info):
		for pkg in info.manifest.plugins['user_packages']['repo']:
			info.img_packages[0].add(pkg)


class AddLocalUserPackages(Task):
	description = 'Adding user local packages to the image packages'
	phase = phases.system_modification
	predecessors = [MountRoot]

	def run(self, info):
		import stat
		rwxr_xr_x = (stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR |
		             stat.S_IRGRP                | stat.S_IXGRP |
		             stat.S_IROTH                | stat.S_IXOTH)

		from shutil import copy
		from common.tools import log_check_call

		for pkg in info.manifest.plugins['user_packages']['local']:
			script_src = os.path.normpath(pkg)
			script_dst = os.path.join(info.root, 'tmp/'+os.path.basename(script_src))
			copy(script_src, script_dst)
			os.chmod(script_dst, rwxr_xr_x)

			log_check_call(['/usr/sbin/chroot', info.root,
			                '/usr/bin/dpkg', '--install', '/tmp/'+os.path.basename(script_src)])
