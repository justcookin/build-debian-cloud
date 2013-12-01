

def validate_manifest(data, schema_validate):
	from os import path
	schema_path = path.normpath(path.join(path.dirname(__file__), 'manifest-schema.json'))
	schema_validate(data, schema_path)
	packages = data['plugins']['packages']
	cloud_init_installed = False
	if 'remote' in packages:
		for package in packages['remote']:
			if isinstance(package, basestring):
				name = package
			else:
				name = package['name']
			if name == 'cloud-init':
				cloud_init_installed = True
				break
	if not cloud_init_installed:
		from common.exceptions import ManifestError
		raise ManifestError('The cloud-init package must be installed for the cloud_init plugin to work')


def resolve_tasks(tasklist, manifest):
	from tasks import SetUsername
	from providers.ec2.tasks.initd import AddEC2InitScripts
	from common.tasks import initd
	tasklist.add(SetUsername)
	tasklist.remove(AddEC2InitScripts,
	                initd.AddExpandRoot,
	                initd.AddSSHKeyGeneration)
