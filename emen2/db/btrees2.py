import emen2.globalns
g = emen2.globalns.GlobalNamespace('')

import bsddb3
from cPickle import dumps, loads
import cPickle as pickle
import sys
import time
import weakref



dbopenflags=bsddb3.db.DB_CREATE


# Berkeley DB wrapper classes


class BTree(object):
	"""This class uses BerkeleyDB to create an object much like a persistent Python Dictionary,
	keys and data may be arbitrary pickleable types"""

	alltrees=weakref.WeakKeyDictionary()

	def __init__(self, name, filename=None, dbenv=None, nelem=0, keytype=None, cfunc=None):
		#"""This is a persistent dictionary implemented as a BerkeleyDB BTree
		#name is required, and will also be used as a filename if none is
		#specified. If relate is true, then parent/child and cousin relationships
		#between records are also supported. """
		#BTree.alltrees[self] = 1	# we keep a running list of all trees so we can close everything properly

		self.name = name
		self.__setkeytype(keytype)

		cfunc = None
		if self.keytype in ("d", "f"):
			cfunc = self.__num_compare


		#else:
		#	raise Exception, "Invalid keytype %s"%keytype

		if filename == None:
			filename = name+".bdb"

		global globalenv,dbopenflags
		self.txn = None	# current transaction used for all database operations

		if not dbenv:
			dbenv = globalenv

		g.debug("BTree init: %s"%filename)
		self.bdb = bsddb3.db.DB(dbenv)

		if cfunc is not None:
			self.bdb.set_bt_compare(cfunc)

		self.__setweakrefopen()
		self.bdb.open(filename, name, bsddb3.db.DB_BTREE, dbopenflags)


	def __setkeytype(self, keytype):
		self.keytype = keytype

		if self.keytype == "d":
			self.set_typekey(self.__typekey_int)

		elif self.keytype == "f":
			self.set_typekey(self.__typekey_float)

		elif self.keytype == "s":
			self.set_typekey(self.__typekey_unicode)
			self.dumpkey = self.__dumpkey_unicode
			self.loadkey = self.__loadkey_unicode

		elif self.keytype == "ds":
			self.set_typekey(self.__typekey_unicode_int)
			self.dumpkey = self.__dumpkey_unicode_int
			self.loadkey = self.__loadkey_unicode_int


	def __num_compare(self, k1, k2):
		if not k1: k1 = 0
		else: k1 = pickle.loads(k1)

		if not k2: k2 = 0
		else: k2 = pickle.loads(k2)

		return cmp(k1, k2)


	# optional keytypes
	def __typekey_int(self, key):
		if key is None: key = 0
		return int(key)


	def __typekey_float(self, key):
		if key is None: key = 0
		return float(key)


	def __typekey_unicode(self, key):
		if key is None: key = ''
		return unicode(key)


	def __typekey_unicode_int(self, key):
		if key is None: key = 0
		try: return int(key)
		except: return unicode(key)


	# special key dumps
	def __dumpkey_unicode(self, key):
		return key.encode("utf-8")


	def __dumpkey_unicode_int(self, key):
		if isinstance(key, int): return dumps(int(key))
		return dumps(unicode(key).encode("utf-8"))


	# special key loads
	def __loadkey_unicode(self, key):
		return key.decode("utf-8")


	def __loadkey_unicode_int(self, key):
		key = loads(key)
		if isinstance(key,int): return key
		return key.encode("utf-8")


	# enforce key types
	def typekey(self, key):
		return key

	def dumpkey(self, key):
		return dumps(self.typekey(key))

	def loadkey(self, key):
		return loads(key)


	# default keytypes and datatypes
	def typedata(self, data):
		return data

	def dumpdata(self, data):
		return dumps(self.typedata(data))

	def loaddata(self, data):
		return loads(data)



	# change key/data behavior
	def set_typekey(self, func):
		self.typekey = func

	def set_typedata(self, func):
		self.typedata = func




	def __setweakrefopen(self):
		BTree.alltrees[self] = 1


	def __str__(self):
		return "<Database.BTree instance: %s>" % self.name


	def __del__(self):
		self.close()


	def close(self):
		if self.bdb is None:
			return

		if g.DEBUG>2:
			g.debug.msg('LOG_DEBUG', '\nbegin')

		#g.debug.msg('LOG_DEBUG', 'main')
		self.bdb.close()
		#g.debug.msg('LOG_DEBUG', '/main')

		self.bdb=None


	def sync(self):
		self.bdb.sync()


	def set_txn(self,txn):
		"""sets the current transaction. Note that other python threads will not be able to use this
		BTree until it is 'released' by setting the txn back to None"""
		if txn==None:
			self.txn=None
			return
		if self.txn:
			g.debug.msg('LOG_WARNING',"Transaction deadlock %s"%unicode(self))
		counter = 0
		while self.txn:
			time.sleep(.1)
			counter += 1
			g.debug.msg('LOG_INFO', 'thread sleeping on transaction msg #%d' % counter)
		self.txn=txn




	def __len__(self):
		return len(self.bdb)


	def __setitem__(self, key, data):
		if data == None:
			self.__delitem__(self.typekey(key))
		else:
			#self.bdb.put(dumps(self.typekey(key)), dumps(self.typedata(data)), txn=self.txn)
			self.bdb.put(self.dumpkey(key), self.dumpdata(data), txn=self.txn)


	def __getitem__(self, key):
		data = self.bdb.get(self.dumpkey(key), txn=self.txn)
		if data is None:
			#Ed: for Backwards compatibility raise TypeError, should be KeyError
			raise TypeError, 'Key Not Found: %r' % key
			# raise KeyError, 'Key Not Found: %r' % key
		else:
			return self.loaddata(data)


	def __delitem__(self, key):
		self.bdb.delete(self.dumpkey(key), txn=self.txn)


	def __contains__(self, key):
		return self.bdb.has_key(self.dumpkey(key), txn=self.txn)


	def keys(self, txn=None):
		return map(lambda x:self.loadkey(x), self.bdb.keys())


	def values(self, txn=None):
		if not txn: txn=self.txn
		return reduce(set.union, (self.loaddata(x) for x in self.bdb.values()), set()) #txn=txn


	def items(self, txn=None):
		if not txn: txn=self.txn
		return map(lambda x:(self.loadkey(x[0]),self.loaddata(x[1])), self.bdb.items()) #txn=txn


	def has_key(self, key, txn=None):
		if not txn: txn=self.txn
		return self.bdb.has_key(self.dumpkey(key)) #, txn=txn


	def get(self, key, txn=None):
		if not txn: txn=self.txn
		#print "get: key is %s %s -> %s %s -> %s %s"%(type(key), key, type(self.typekey(key)), self.typekey(key), type(self.dumpkey(key)), self.dumpkey(key))
		try:
			return self.loaddata(self.bdb.get(self.dumpkey(key), txn=txn))
		except:
			return None

	def set(self, key, data, txn=None):
		"Alternative to x[key]=val with transaction set"
		if not txn: txn=self.txn
		if data == None:
			return self.bdb.delete(self.dumpkey(key), txn=txn)
		return self.bdb.put(self.dumpkey(key), self.dumpdata(data), txn=txn)


	def update(self, d, txn=None):
		if not txn: txn=self.txn
		d = dict(map(lambda x:self.typekey(x[0]), self.typedata(x[1]), d.items()))
		for i,j in dict.items():
			self.bdb.put(self.dumpkey(i), self.dumpdata(j), txn=txn)
			#self.set(i,j,txn=txn)







class RelateBTree(BTree):
	"""BTree with parent/child/cousin relationships between keys"""


 	def __init__(self, *args, **kwargs):
 		BTree.__init__(self, *args, **kwargs)
		self.relate = 1

		dbenv = kwargs.get("dbenv")
		filename = kwargs.get("filename")
		name = kwargs.get("name")

		# Parent keyed list of children
		self.pcdb = bsddb3.db.DB(dbenv)
		self.pcdb.open(filename+".pc", name, bsddb3.db.DB_BTREE, dbopenflags)

		# Child keyed list of parents
		self.cpdb = bsddb3.db.DB(dbenv)
		self.cpdb.open(filename+".cp", name, bsddb3.db.DB_BTREE, dbopenflags)

		# lateral links between records (nondirectional), 'getcousins'
		self.reldb = bsddb3.db.DB(dbenv)
		self.reldb.open(filename+".rel", name, bsddb3.db.DB_BTREE, dbopenflags)


	def __str__(self):
		return "<Database.RelateBTree instance: %s>" % self.name



	def close(self):
		if self.bdb is None:
			return

		#try:
		self.pcdb.close()
		self.cpdb.close()
		self.reldb.close()
		#except Exception, e:
		#	g.debug('LOG_ERROR', unicode(e))

		self.bdb.close()
		self.bdb = None



	def sync(self):
		#try:
		self.bdb.sync()
		self.pcdb.sync()
		self.cpdb.sync()
		self.reldb.sync()
		#except:
		#	pass


	def __relate(self, db1, db2, method, tag1, tag2, txn=None):

		# key = normal key
		# data = set of keys

		if not self.relate:
			raise Exception,"relate option required in BTree"

		if not txn:	txn = self.txn

		tag1, tag2 = self.typekey(tag1), self.typekey(tag2)

		if tag1 == None or tag2 == None:
			return

		if not self.has_key(tag2, txn=txn) or not self.has_key(tag1, txn=txn):
			raise KeyError,"Nonexistent key in %s <-> %s"%(tag1, tag2)

		try:
			o = loads(db1.get(self.dumpkey(tag1), txn=txn))
		except:
			o = set()

		if (method == "add" and tag2 not in o) or (method == "remove" and tag2 in o):
			getattr(o, method)(tag2)
			db1.put(self.dumpkey(tag1), dumps(o), txn=txn)
		#try:
		#except Exception, inst:
		#	print "Error linking 2... %s"%inst

		try:
			o = loads(db2.get(self.dumpkey(tag2), txn=txn))
		except:
			o = set()

		if (method == "add" and tag1 not in o) or (method == "remove" and tag1 in o):
			getattr(o, method)(tag1)
			db2.put(self.dumpkey(tag2), dumps(o), txn=txn)
		#try:
		#except Exception, inst:
		#	print "Error linking 1... %s"%inst


	def pclink(self, parenttag, childtag, txn=None):
		"""This establishes a parent-child relationship between two tags.
		The relationship may also be named. That is the parent may
		get a list of children only with a specific paramname. Note
		that empty strings and None cannot be used as tags"""
		self.__relate(self.pcdb, self.cpdb, "add", parenttag, childtag, txn=txn)


	def pcunlink(self, parenttag, childtag, txn=None):
		"""Removes a parent-child relationship, returns quietly if relationship did not exist"""
		self.__relate(self.pcdb, self.cpdb, "remove", parenttag, childtag, txn=txn)


	def link(self, tag1, tag2, txn=None):
		"""Establishes a lateral relationship (cousins) between two tags"""
		self.__relate(self.reldb, self.reldb, "add", parenttag, childtag, txn=txn)


	def unlink(self, tag1, tag2, txn=None):
		"""Removes a lateral relationship (cousins) between two tags"""
		self.__relate(self.reldb, self.reldb, "remove", parenttag, childtag, txn=txn)


	def parents(self, tag, txn=None):
		"""Returns a list of the tag's parents"""
		if not self.relate:
			raise Exception,"relate option required"
		if not txn:	txn = self.txn

		try:
			return loads(self.cpdb.get(self.dumpkey(tag), txn=txn))
		except:
			return set()


	def children(self, tag, txn=None):
		"""Returns a list of the tag's children. If paramname is
		omitted, all named and unnamed children will be returned"""
		if not self.relate:
			raise Exception,"relate option required"
		if not txn:	txn = self.txn

		try:
			return loads(self.pcdb.get(self.dumpkey(tag), txn=txn))
			#if paramname :
			#	return set(x[0] for x in c if x[1]==paramname)
			#else: return c
		except:
			return set()


	def cousins(self, tag, txn=None):
		"""Returns a list of tags related to the given tag"""
		if not self.relate:
			raise Exception,"relate option required"
		if not txn:	txn = self.txn

		try:
			return loads(self.reldb.get(self.dumpkey(tag),txn=txn))
		except:
			return set()












class FieldBTree(BTree):
	"""This is a specialized version of the BTree class. This version uses type-specific
	keys, and supports efficient key range extraction. The referenced data is a python list
	of 32-bit integers with no repeats allowed. The purpose of this class is to act as an
	efficient index for records. Each FieldBTree will represent the global index for
	one Field within the database. Valid key types are:
	"d" - integer keys
	"f" - float keys (64 bit)
	"s" - string keys
	"""


	def __str__(self):
		return "<Database.FieldBTree instance: %s>" % self.name



	def typedata(self, data):
		return set(map(int, data))


	def removeref(self, key, item, txn=None):
		"""The keyed value must be a list of objects. 'item' will be removed from this list"""
		if not txn: txn=self.txn
		o = self.get(key, txn=txn) or set()
		o.remove(item)
		return self.set(key, o, txn=txn)


	def removerefs(self, key, items, txn=None):
		"""The keyed value must be a list of objects. list of 'items' will be removed from this list"""
		if not txn: txn=self.txn
		o = self.get(key, txn=txn) or set()
		o -= set(items)
		return self.set(key, o, txn=txn)


	def testref(self, key, item, txn=None):
		"""Tests for the presence if item in key'ed index """
		if not txn: txn=self.txn
		o = self.get(key, txn=txn) or set()
		return item in o


	def addref(self, key, item, txn=None):
		"""The keyed value must be a list, and is created if nonexistant. 'item' is added to the list. """
		if not txn: txn=self.txn
		o = self.get(key, txn=txn) or set()
		o.add(item)
		return self.set(key, o, txn=txn)


	def addrefs(self, key, items, txn=None):
		"""The keyed value must be a list, and is created if nonexistant. 'items' is a list to be added to the list. """
		if not txn: txn=self.txn
		o = self.get(key, txn=txn) or set()
		o |= set(items)
		return self.set(key, o, txn=txn)


	def items(self, mink=None, maxk=None, txn=None):
		if mink == None and maxk == None: return self.items()

		if not txn : txn=self.txn
		if mink is None and maxk is None:
			items = super(FieldBTree, self).items()
		else:
			print "cur"
			cur = self.bdb.cursor(txn=txn)
			items = []
			if mink is not None:
				mink=self.typekey(mink)
				entry = cur.set_range(pickle.dumps(mink))
			else:
				entry = cur.first()

			print "entry"

			if maxk is not None:
				maxk=self.typekey(maxk)

			while entry is not None:
				key, value = (pickle.loads(x) for x in entry)
				if maxk is not None and key >= maxk:
					break
				items.append((key,value))
				entry = cur.next()

		return items


	def keys(self,mink=None,maxk=None,txn=None):
		"""Returns a list of valid keys, mink and maxk allow specification of
 		minimum and maximum key values to retrieve"""
		if mink == None and maxk == None: return super(FieldBTree, self).keys()
		return set(x[0] for x in self.items(mink, maxk, txn=txn))


	def values(self,mink=None,maxk=None,txn=None):
		"""Returns a single list containing the concatenation of the lists of,
 		all of the individual keys in the mink to maxk range"""
		if mink == None and maxk == None: return super(FieldBTree, self).values()
		return reduce(set.union, (set(x[1]) for x in self.items(mink, maxk, txn=txn)), set())





# 	def __len__(self):
# 		"Number of elements in the database. Warning, this isn't transaction protected..."
# 		return len(self.bdb)
# #		if (self.len<0) : self.keyinit()
# #		return self.len
#
# 	def __setitem__(self,key,val):
# 		key=self.typekey(key)
# 		if (val==None) :
# 			self.__delitem__(key)
# 		else : self.bdb.index_put(key,val,txn=self.txn)
#
# 	def __getitem__(self,key):
# 		key=self.typekey(key)
# 		return self.bdb.index_get(key,txn=self.txn)
#
# 	def __delitem__(self,key):
# 		key=self.typekey(key)
# 		self.bdb.delete(key,txn=self.txn)
#
# 	def __contains__(self,key):
# 		key=self.typekey(key)
# 		return self.bdb.index_has_key(key,txn=self.txn)
#
#
# 	def items(self,mink=None,maxk=None,txn=None):
# 		if not txn : txn=self.txn
# 		mink=self.typekey(mink)
# 		maxk=self.typekey(maxk)
# 		return self.bdb.index_items(mink,maxk,txn=self.txn)
#
# 	def has_key(self,key,txn=None):
# 		if not txn : txn=self.txn
# 		key=self.typekey(key)
# 		return self.bdb.index_has_key(key,txn=txn)
#
# 	def get(self,key,txn=None):
# 		key=self.typekey(key)
# 		return self.bdb.index_get(key,txn=txn)
#
# 	def set(self,key,val,txn=None):
# 		"Alternative to x[key]=val with transaction set"
# 		key=self.typekey(key)
# 		if (val==None) :
# 			self.bdb.delete(key,txn=txn)
# 		else : self.bdb.index_put(key,val,txn=txn)
#
# 	def update(self,dict):
# 		self.bdb.index_update(dict,txn=self.txn)
