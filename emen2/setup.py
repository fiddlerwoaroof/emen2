from distutils.core import setup
setup(
	name='emen2',
	version='2.0',
	py_modules=[
		'emen2.db',
		'emen2.web',
		'emen2.web.resources',
		'emen2.web.views',
		'emen2.skeleton',
		'emen2.clients',
		'emen2.clients.emdash',
		'emen2.clients.emdash.models',
		'emen2.clients.emdash.threads',
		'emen2.clients.emdash.ui'
		],
	package_dir={'':'..'}
	)