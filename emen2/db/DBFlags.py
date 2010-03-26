import emen2.globalns
g = emen2.globalns.GlobalNamespace()

import operator
from bsddb3.db import *

envopenflags = [
	DB_CREATE,
	DB_THREAD,
	DB_INIT_MPOOL,
	DB_INIT_TXN,
	DB_INIT_LOCK,
	DB_INIT_LOG,
	DB_REGISTER,
	DB_RECOVER
	]
	

# DB_FAILCHK # ian: todo: doesn't seem to be in bsddb3
	
# these are in DB_CONFIG
# DB_TXN_SNAPSHOT
# DB_MULTIVERSION

	
dbopenflags = [
	DB_CREATE,
	DB_THREAD
]

txnflags = [
	#DB_TXN_SNAPSHOT,
	#DB_MULTIVERSION	
]	
	
rmwflags = [
	DB_RMW
	]


g.ENVOPENFLAGS = reduce(operator.__or__, envopenflags, 0)
g.DBOPENFLAGS = reduce(operator.__or__, dbopenflags, 0)
g.TXNFLAGS = reduce(operator.__or__, txnflags, 0)
g.RMWFLAGS = reduce(operator.__or__, rmwflags, 0)