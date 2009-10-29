import bsddb3

USETXN = True
RECOVER = False

# Berkeley DB Config flags
ENVOPENFLAGS = bsddb3.db.DB_CREATE | bsddb3.db.DB_THREAD | bsddb3.db.DB_INIT_MPOOL 
DBOPENFLAGS = bsddb3.db.DB_THREAD | bsddb3.db.DB_CREATE 
RMWFLAGS = 0

TXNFLAGS = bsddb3.db.DB_TXN_SNAPSHOT | bsddb3.db.DB_INIT_TXN | bsddb3.db.DB_INIT_LOCK | bsddb3.db.DB_MULTIVERSION | bsddb3.db.DB_INIT_LOG
RECOVERFLAGS = bsddb3.db.DB_RECOVER


if USETXN:
	ENVOPENFLAGS |= TXNFLAGS
	DBOPENFLAGS |= bsddb3.db.DB_AUTO_COMMIT
	RMWFLAGS = bsddb3.db.DB_RMW
	
if RECOVER:
	ENVOPENFLAGS |= RECOVERFLAGS