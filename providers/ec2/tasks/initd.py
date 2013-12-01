from base import Task
from common import phases
from common.tasks import initd
import os.path


class AddEC2InitScripts(Task):
	description = 'Adding EC2 startup scripts'
	phase = phases.system_modification
	successors = [initd.InstallInitScripts]

	def run(self, info):
		init_scripts = {'ec2-get-credentials': 'ec2-get-credentials',
		                'ec2-run-user-data': 'ec2-run-user-data'}

		init_scripts_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), '../assets/init.d'))
		for name, path in init_scripts.iteritems():
			info.initd['install'][name] = os.path.join(init_scripts_dir, path)
