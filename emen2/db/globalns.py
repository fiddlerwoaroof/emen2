# $Id$
##########################################################
from __future__ import with_statement

import itertools
import collections
def dict_merge(dct1, dct2):
	commonkeys = set(dct1) & set(dct2)
	newkeys = set(dct2) - commonkeys

	for key in commonkeys:
		olditem = dct1[key]
		newitem = dct2[key]
		if hasattr(newitem, 'items') and hasattr(olditem, 'items'):
			dict_merge(olditem, newitem)
		#elif hasattr(olditem, 'update') and hasattr(newitem, '__iter__'):
		#	olditem.update(newitem)
		#elif hasattr(olditem, 'extend') and hasattr(newitem, '__iter__'):
		#	olditem.extend(newitem)
		else:
			dct1[key] = dct2[key]
	dct1.update( (k,dct2[k]) for k in newkeys )
	return dct1


class _Null: pass
class Hier(collections.MutableMapping):
	####################
	# Class Attributes #
	####################

	hier = {}

	@classmethod
	def from_dict(cls, dct):
		#cls.init()
		dict_merge(cls.hier, dct)
		return cls()

	#######################
	# Instance Attributes #
	#######################

	def to_dict(self):
		return self._values

	def __init__(self, name=''):
		self._values = self.hier
		self._create = False

		self._name = name

		for segment in self._name.split('.'):
			item = self._values.get(segment)
			if hasattr(item, 'items'):
				#print item
				self._values = item
			elif name != '':
				raise ValueError('no such item: %r' % self._name)

	def __repr__(self):
		return '%s().from_dict(%r)' % (self.__class__.__name__, self._values)

	def __getattribute__(self, name):
		result = _Null
		try:
			result = object.__getattribute__(self, name)
		except AttributeError:
			if name.startswith('_'): raise
			else:
				result = self.getattr(name, default=_Null, prefix=self._name)
				if isinstance(result, self.__class__):
					result._create = self._create

		if result is _Null:
			if self._create:
				self.setattr(name, {})
			else:
				raise
		return result

	def __setattr__(self, name, value):
		res = getattr(self.__class__, name, None)
		if name.startswith('_') or hasattr(res, '__set__'):
			object.__setattr__(self, name, value)
		else:
			self.setattr(name, value)

	def getattr(self, name, default=None, prefix=''):
		result = self._values.get(name, _Null)
		if result is _Null and default is not _Null:
			result = default
		elif hasattr(result, 'items'):
			if prefix == '': result = self.__class__(name)
			else: result = self.__class__('%s.%s' % (prefix, name))
		return result

	def __getitem__(self, name):
		result = self.getattr(name, default=_Null)
		if result is _Null:
			raise KeyError('Item %r not found' % name)
		return result

	def setattr(self, name, value, options=None):
		name = name.split('.')

		values = self._values
		for seg in name[:-1]:
			values = values.setdefault(seg, {})
		values[name[-1]] = value

	def __setitem__(self, name, value):
		self._values[name] = value

	def __delitem__(self, name):
		del self._values[name]

	def __iter__(self): return iter(self._values)
	def __len__(self): return len(self._values)



##########################################################


'''NOTE: locking is unnecessary when accessing globals, as they will automatically lock when necessary

NOTE: access globals this way:
import emen2.globalns
g = emen2.globalns.GlobalNamespace('')
g.<varname> accesses the variable
g.<varname> = <value> sets a variable in a threadsafe manner.
'''

import re
import collections
import threading
import os
import os.path
import UserDict
import time
import os.path

try: import yaml
except ImportError:
	try: import syck as yaml
	except ImportError:
		yaml = False

try: import json
except ImportError:
	try: import simplejson as json
	except ImportError:
		json = False

import emen2.util.datastructures
from emen2.db import debug
import jsonrpc.jsonutil

class LoggerStub(debug.DebugState):
	def __init__(self, *args):
		debug.DebugState.__init__(self, output_level='DEBUG', logfile=None, get_state=False, logfile_state=None, just_print=True)
	def swapstdout(self): pass
	def capturestdout(self):
		print 'cannot capture stdout'
	def closestdout(self): pass
	def msg(self, sn, *args, **k):
		sn = self.debugstates.get_name(self.debugstates[sn])
		print u'   %s:%s :: %s' % (time.strftime('[%Y-%m-%d %H:%M:%S]'), sn, self.print_list(args))

log = LoggerStub()

inst = lambda x:x()
class GlobalNamespace(Hier):

	def claim(self, name, default=None, validator=None):
		return Claim(self, name, default, validator)
	def watch(self, name, default=None):
		return Watch(self, name, default)

	_events = collections.defaultdict(list)
	@classmethod
	def register_event(cls, var):
		'''events shouldn't modify the state of the GlobalNamespace!!!'''
		def _inner(cb):
			cls._events[var].append(cb)
			if var in cls.__vardict:
				cb(cls.__vardict[var], read=True)
			return cb
		return _inner

	@classmethod
	def _trigger_event(cls, var, value, read=False, write=False):
		for cb in cls._events.get(var, []):
			cb(value, read=read, write=write)


	@inst
	class paths(object):
		attrs = []
		__root = ['']
		@property
		def root(self): return self.__root[0]
		@root.setter
		def root(self, v): self.__root.insert(0, v)
		def get_roots(self): return self.__root[:]

		def update(self, path): self.root = path

		def __delattr__(self, name):
			try:
				self.attrs.remove(name)
			except ValueError: pass
			object.__delattr__(self, name)

		def __setattr__(self, name, value):
			self.attrs.append(name)
			return object.__setattr__(self, name, value)

		def __getattribute__(self, name):
			value = object.__getattribute__(self, name)
			if name.startswith('_') or name in set(['attrs', 'root']): return value
			else:
				if isinstance(value, (str, unicode)):
					if value.startswith('/'): pass
					else: value = os.path.join(self.root, value)
				elif hasattr(value, '__iter__'):
					if hasattr(value, 'items'): value = dictWrapper(value, self.root)
					else: value = listWrapper(value, self.root)
			if value is _Null:
				raise AttributeError('Attribute %r not found' % name)
			return value


	__yaml_keys = collections.defaultdict(list)
	__yaml_files = collections.defaultdict(list)
	__options = collections.defaultdict(set)
	__all__ = []

	@property
	def EMEN2DBHOME(self):
		return self.__vardict.get('EMEN2DBHOME')
	@EMEN2DBHOME.setter
	def EMEN2DBHOME(self, value):
		self.setattr('EMEN2DBHOME', value)
		self.paths.root = value

	@classmethod
	def check_locked(cls):
		try:
			cls.__locked
			#print 'ns __locked 0', cls.__locked
		except AttributeError: cls.__locked = False
		return cls.__locked
		#print 'ns __locked 1', cls.__locked


	@property
	def _locked(self):
		return self.check_locked()


	@_locked.setter
	def _locked(self, value):
		cls = self.__class__
		if not self.__locked:
			cls.__locked = bool(value)
		elif bool(value) == False:
			raise LockedNamespaceError, 'cannot unlock %s' % cls.__name__

	def __enter__(self):
		self.__tmpdict = emen2.util.datastructures.AttributeDict()
		return self.__tmpdict


	def __exit__(self, exc_type, exc_value, tb):
		newitems = set(self.__tmpdict) - set(self.__vardict)
		if newitems:
			self.__vardict.update(x for x in self.__tmpdict.iteritems() if x[0] in newitems)
			skipped = set(self.__tmpdict) - newitems
			if skipped: self.log.msg('WARNING', 'skipped items: %r' % skipped)
		del self.__tmpdict


	@classmethod
	def __unlock(cls):
		'''unlock namespace (for internal/debug use only)'''
		cls.__locked = False


	hier = dict(
		log = log,
		info = lambda *a, **k: log.msg('INFO', *a, **k),
		init = lambda *a, **k: log.msg('INIT', *a, **k),
		error = lambda *a, **k: log.msg('ERROR', *a, **k),
		warn = lambda *a, **k: log.msg('WARNING', *a, **k),
		debug = lambda *a, **k: log.msg('DEBUG', *a, **k)
	)



	@classmethod
	def load_data(cls, fn, data):
		fn = os.path.abspath(fn)
		if fn and os.access(fn, os.F_OK):
			ext = fn.rpartition('.')[2]
			with open(fn, "r") as f: data = f.read()

			loadfunc = {'json': json.loads}
			try:
				loadfunc['yml'] = yaml.safe_load
			except AttributeError: pass

			def fail(*a): raise NotImplementedError, "No loader for %s files found" % ext.upper()
			loadfunc = loadfunc.get( fn.rpartition('.')[2], fail )

			if ext.lower() == 'json':
				data = json_strip_comments(data)

			data = loadfunc(data)

		elif hasattr(data, 'upper'):
			loadfunc = json.loads
			if yaml: load_func = yaml.safe_load
			data = loadfunc(data)

		return data


	@classmethod
	def from_file(cls, fn=None, data=None):
		'''Alternate constructor which initializes a GlobalNamespace instance from a YAML file'''

		if not (fn or data):
			raise ValueError, 'Either a filename or json/yaml data must be supplied'

		data = cls.load_data(fn, data)

		## load data
		self = cls()

		if data:
			self.log("Loading config: %s"%fn)

			# treat EMEN2DBHOME specially
			self.EMEN2DBHOME = data.pop('EMEN2DBHOME', self.getattr('EMEN2DBHOME', ''))
			self.paths.root = self.EMEN2DBHOME

			for k,v in data.pop('paths', {}).items():
				setattr(self.paths, k, v)

			# process data
			self._create = True
			for key in data:
				b = data[key]
				pref = ''.join(b.pop('prefix',[])) # get the prefix for the current toplevel dictionary
				options = b.pop('options', {})	  # get options for the dictionary
				self.__yaml_files[fn].append(key)

				for key2, value in b.iteritems():
					self.__yaml_keys[key].append(key2)
					#self.setattr('.'.join([key,key2]), value, options)
			self.from_dict(data)

			# load alternate config files
			# for fn in self.paths.CONFIGFILES:
			#	fn = os.path.abspath(fn)
			#	if os.path.exists(fn):
			#		cls.from_file(fn=fn)

		return self


	def to_json(self, keys=None, kg=None, file=None, indent=4, sort_keys=True):
		return json.dumps(self.__dump_prep(keys, kg, file), indent=indent, sort_keys=sort_keys)


	def to_yaml(self, keys=None, kg=None, file=None, fs=0):
		return yaml.safe_dump(self.__dump_prep(keys, kg, file), default_flow_style=fs)

	def __dump_prep(self, keys=None, kg=None, file=None):
		'''store state as YAML'''
		if keys is not None:
			keys = keys
		elif kg is not None:
			keys = dict( (k, self.__yaml_keys[k]) for k in kg)
		elif file is not None:
			keys = dict( (k, self.__yaml_keys[k]) for k in self.__yaml_files[file] )
		else:
			keys = self.__yaml_keys

		_dict = collections.defaultdict(dict)
		for key, value in keys.iteritems():
			for k2 in value:
				value = self.getattr(key).getattr(k2)
				if hasattr(value, 'json_equivalent'): value = value.json_equivalent()
				_dict[key][k2] = value

		for key in self.paths.attrs:
			path = getattr(self.paths, key)
			if hasattr(path, 'json_equivalent'): path = path.json_equivalent()
			_dict['paths'][key] = path
		return dict(_dict)
	def json_equivalent(self):
		return dict(self._values)


	#@classmethod
	#def setattr(self, name, value):
	#	self.__addattr(name, value)


	#def __setattr__(self, name, value):
	#	self._trigger_event(name, value, write=True)
	#	res = getattr(self.__class__, name, None)
	#	if name.startswith('_') or hasattr(res, '__set__'):
	#		object.__setattr__(self, name, value)
	#	else:
	#		self.setattr(name, value)

	def __getitem__(self, name):
		if not hasattr(name, 'split'):
			name = '.'.join(name)
		return self.getattr(name)
	def __setitem__(self, name, value):
		if not hasattr(name, 'split'):
			name = '.'.join(name)
		return self.setattr(name, value)



	#@classmethod
	def setattr(self, name, value, options=None):
		if not name in self.__all__:
			self.__all__.append(name)

		self.check_locked()
		if name.startswith('_') or not self.__locked:
			if options is not None:
				for option in options:
					self.__options[option].add(name)
			Hier.setattr(self, name, value)
		else: raise LockedNamespaceError, 'cannot change locked namespace'



	def getattr(self, name, default=None, *args, **kwargs):
		if name.endswith('___'):
			name = name.partition('___')[-1]
		if self.__options.has_key('private'):
			if name in self.__options['private']:
				return default
		result = Hier.getattr(self, name, default=default, *args, **kwargs)
		self._trigger_event(name, result, read=True)
		return result


	@classmethod
	def keys(cls):
		private = cls.__options['private']
		return [k for k in cls.__vardict.keys() if k not in private]


	@classmethod
	def getprivate(cls, name):
		if name.startswith('___'):
			name = name.partition('___')[-1]
		result = Hier.getattr(self, name)
		return result


	def update(self, dict):
		self.__vardict.update(dict)


	def reset(self):
		self.__class__.__vardict = {}





#import <module>
import unittest

class TestSequenceFunctions(unittest.TestCase):

	def setUp(self):
		self.a = GlobalNamespace('one instance')
		self.b = GlobalNamespace('two instance')
		self.a.a = 1


	def test_attributenotfound(self):
		self.assertRaises(lambda: self.a.not_found, AttributeError)

	def test_setattribute(self):
		#test 1 attribute access
		self.assertEqual(self.a.a, 1)
		self.assertTrue(hasattr(self.b, 'a'))
		self.assertEqual(self.a.a, self.b.a)

	def test_reset(self):
		self.a.reset()
		self.assertRaises(lambda: self.a.a, AttributeError)

	def test_update(self):
		tempdict = dict(a=1, b=2, c=3)
		self.a.update(tempdict)
		self.assertEqual(self.a.a, tempdict['a'])
		self.assertEqual(self.b.a, tempdict['a'])
		self.assertEqual(self.a.___a, tempdict['a'])
		print "test 3 passed"
		a.reset()


if __name__ == '__main__':
	pass
	#unittest.main()

class dictWrapper(object, UserDict.DictMixin):
	def __init__(self, dict_, prefix):
		self.__dict = dict_
		self.__prefix = prefix
	def __repr__(self):
		return '<dictWrapper dict: %r>' % self.__dict
	def keys(self): return self.__dict.keys()
	def __getitem__(self, name):
		v = self.__dict[name]
		if not v.startswith('/'):
			v = os.path.join(self.__prefix, v)
		return v
	def __setitem__(self, name, value):
		if isinstance(value, (str, unicode)):
			if value.startswith(self.__prefix):
				del value[len(self.__prefix)+1:]
		self.__dict[name] = value
	def __delitem__(self, name):
		del self.__dict[name]
	def json_equivalent(self): return dict(self)

class listWrapper(object):
	def __init__(self, list_, prefix):
		self.__list = list_
		self.__prefix = prefix
	def __repr__(self):
		return '<listWrapper list: %r>' % self.__list
	def check_item(self, item):
		if isinstance(item, (str, unicode)):
			item = os.path.join(self.__prefix, item)
		return item
	def __iter__(self):
		for item in self.__list:
			yield self.check_item(item)
	def __getitem__(self, k):
		return self.check_item(self.__list[k])
	def chopitem(self, item):
		if isinstance(item, (str, unicode)):
			if item.startswith(self.__prefix):
				item = item[len(self.__prefix)+1:]
		return item
	def __setitem__(self, key, value):
		value = self.chopitem(value)
		self.__list[key] = value
	def __delitem__(self, idx):
		del self.__list[idx]
	def append(self, item):
		item = self.chopitem(item)
		self.__list.append(item)
	def extend(self, items):
		self.__list.extend(self.chopitem(item) for item in items)
	def pop(self, idx):
		res = self[idx]
		del self[idx]
		return res
	def count(self, item):
		return self.__list.count(self.chopitem(item))
	def insert(self, idx, item):
		self.__list.insert(idx, self.chopitem(item))
	def __len__(self): return len(self.__list)
	def json_equivalent(self): return list(self)



class Watch(object):
	def __init__(self, ns, name, default, validator=None):
		self.ns = ns
		self.name = name.split('.')
		self.default = default

	def __get__(self, instance, owner):
		return self.get()

	def get(self):
		result = getattr(self.ns, self.name[0], self.default)
		for n in self.name[1:]:
			result = getattr(result, n, self.default)

		return result

class Claim(Watch):
	claimed_attributes = set()
	def __init__(self, ns, name, default, validator=None):
		if name in self.claimed_attributes:
			raise ValueError, 'attribute %s already claimed, use GlobalNamespace.watch() instead' % name
		else:
			self.claimed_attributes.add(name)

		if not hasattr(ns, name):
			ns.setattr(name, default),

		self.validator = validator
		self._validate(default)


		Watch.__init__(self, ns, name, default, validator)

	def _validate(self, value):
		if self.validator is not None:
				is_valid = self.validator(value)
				if not is_valid:
					res_repr = repr(value)
					if len(res_repr) > 30: res_repr = res_repr[:27] + '...'
					raise ValueError, 'Configuration value %r has invalid value %s' % (self.name, res_repr)

	def __set__(self, instance, value):
		self.set(value)

	def set(self, value):
		self._validate(value)

		ns = self.ns
		for name in self.name[:-1]:
			ns = getattr(ns, name)

		setattr(ns, self.name[-1], value)
		return self



def json_strip_comments(data):
	r = re.compile('/\\*.*\\*/', flags=re.M|re.S)
	data = r.sub("", data)
	data = re.sub("\s//.*\n", "", data)
	return data
class LockedNamespaceError(TypeError): pass


__version__ = "$Revision$".split(":")[1][:-1].strip()
