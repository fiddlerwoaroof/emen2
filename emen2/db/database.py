"""Main database module."""

import os
import re
import sys
import time
import datetime
import dateutil
import collections
import functools
import getpass
import inspect
import traceback
import uuid
import smtplib
import email
import email.mime.text

# Markdown processing
try:
    import markdown
except ImportError:
    markdown = None

# JSON-RPC support
import jsonrpc.jsonutil

# EMEN2 Config
import emen2.db.config
import emen2.db.log

# EMEN2 Exceptions into local namespace
from emen2.db.exceptions import *

# EMEN2 Core
import emen2.db.vartypes
import emen2.db.properties
import emen2.db.macros
import emen2.db.proxy
import emen2.db.load
import emen2.db.handlers

# EMEN2 DBObjects
import emen2.db.dataobject
import emen2.db.record
import emen2.db.binary
import emen2.db.paramdef
import emen2.db.recorddef
import emen2.db.user
import emen2.db.context
import emen2.db.group

# EMEN2 Utilities
import emen2.utils

# Load backend
BACKEND = "bdb"
if BACKEND == "bdb":
    import emen2.db.btrees as backend
else:
    raise ImportError, "Unsupported EMEN2 backend: %s"%backend

# This is just for initial configuration...
# TODO: Handle better.
MINLENGTH = 8

# Versions
# from emen2.clients import __version__
VERSIONS = {
    "API": emen2.__version__,
    None: emen2.__version__
}

# Regular expression to parse Protocol views.
# New style
VIEW_REGEX_P = '''
        (?P<name>[\w\-\?\*]+)
        (?:="(?P<default>.+)")?
        (?P<emptyargs>\(\))?
        (?:\((?P<args>[^\)]+)\))?
'''

VIEW_REGEX_CLASSIC = '''(\$[\$\@\#\!]%s(?P<sep>[\W])?)'''%VIEW_REGEX_P
VIEW_REGEX_M = '''(\{\{[\#\^\/]?%s\}\})'''%VIEW_REGEX_P

# Rate limits!!
# This is a temporary solution.
# Keys are account names. Values are time.time() of 
#   unsuccesful logins.
LOGIN_RATES = {}

##### Conveniences #####
publicmethod = emen2.db.proxy.publicmethod

##### Utility methods #####

def getrandomid():
    """Generate a random string."""
    length = 16
    return os.urandom(length).encode('hex')

def getnewid():
    """Generate an ID (UUID4 string)
    :return: UUID4 string
    """
    return uuid.uuid4().hex

def getctime():
    """Current database time, as float in seconds since the UNIX epoch.
    :return: Time as float in seconds since the UNIX epoch.
    """
    return time.time()

def utcdifference(t1, t2=None):
    t1 = dateutil.parser.parse(t1)
    if not t1.tzinfo:
        t1 = t1.replace(tzinfo=dateutil.tz.tzutc())
    t2 = dateutil.parser.parse(t2 or utcnow())
    return (t2 - t1).total_seconds()

def utcnow():
    """Returns the current database UTC time in ISO 8601 format.
    :return: UTC time in ISO 8601 format.
    """
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat()+'+00:00'

def getpw(pw=None):
    """Prompt for a password.
    :keyword pw: Use this password, or prompt using getpass.getpass()
    :return: Password.
    """
    # TODO: Actually validate password using User rules.
    pw = pw or getpass.getpass("Password: ")
    while len(pw) < MINLENGTH:
        if len(pw) == 0:
            print "Warning! No password!"
            pw = ''
            break
        elif len(pw) < MINLENGTH:
            print "Warning! If you set a password, it needs to be more than %s characters."%MINLENGTH
            pw = getpass.getpass("Password: ")
    return pw

def ol(name, output=True):
    """Decorator function to return a list if function arg 'name' was a list, 
    or return the first element if function arg 'name' was not a list.
    :param name: Argument name to transform to list.
    :keyword output: Transform output.
    """
    # This will be easier in Python 2.7 using inspect.getcallargs.
    def wrap(f):
        olpos = inspect.getargspec(f).args.index(name)

        @functools.wraps(f)
        def wrapped_f(*args, **kwargs):
            if kwargs.has_key(name):
                olreturn, olvalue = emen2.utils.oltolist(kwargs[name])
                kwargs[name] = olvalue
            elif (olpos-1) <= len(args):
                olreturn, olvalue = emen2.utils.oltolist(args[olpos])
                args = list(args)
                args[olpos] = olvalue
            else:
                raise TypeError, 'function %r did not get argument %s' % (f, name)

            result = f(*args, **kwargs)
            if output and olreturn:
                return emen2.utils.first_or_none(result)
            return result
            
        return wrapped_f
    return wrap

def limit_result_length(default=None):
    """Limit the number of items returned."""
    ns = dict(func = None)
    def _inner(*a, **kw):
        func = ns.get('func')
        result = func(*a, **kw)
        limit = kw.pop('limit', default)
        if limit  and hasattr(result, '__len__') and len(result) > limit:
            result = result[:limit]
        return result

    def wrapped_f(f):
        ns['func'] = f
        return functools.wraps(f)(_inner)

    result = wrapped_f
    if callable(default):
        ns['func'] = default
        result = functools.wraps(default)(_inner)

    return result

##### Email #####

# ian: TODO: put this in a separate module
def sendmail(to_addr, subject='', msg='', template=None, ctxt=None):
    """(Internal) Send an email. You can provide either a template or a message subject and body.

    :param to_addr: Email recipient
    :keyword subject: Subject
    :keyword msg: Message text, or
    :keyword template: ... template name  
    :keyword ctxt: Dictionary to pass to template  
    :return: Email recipient, or None if email is not configured.
    :exception: ValueError if no message to send.
    """
    from_addr, smtphost = emen2.db.config.mailconfig()
    if not (from_addr and smtphost):
        # emen2.db.log.warn("EMAIL: No mail configuration!")
        return
    
    ctxt = ctxt or {}
    ctxt["to_addr"] = to_addr
    ctxt["from_addr"] = from_addr
    ctxt["TITLE"] = emen2.db.config.get('customization.title')
    ctxt["uri"] = emen2.db.config.get('web.uri')

    if msg:
        msg = email.mime.text.MIMEText(msg)
        msg['Subject'] = subject
        msg['From'] = from_addr
        msg['To'] = to_addr
        msg = msg.as_string()

    elif template:
        try:
            msg = emen2.db.config.templates.render_template(template, ctxt)
        except Exception, e:
            emen2.db.log.warn('EMAIL: Could not render mail template %s: %s'%(template, e))
            raise ValueError, "Could not render mail template."
    else:
        raise ValueError, "No message to send!"

    # Actually send the message
    s = smtplib.SMTP(smtphost)
    s.set_debuglevel(1)
    s.sendmail(from_addr, [from_addr, to_addr], msg)
    emen2.db.log.info('EMAIL: Mail sent: %s -> %s'%(from_addr, to_addr))
    return to_addr

##### Open or create new database #####

def opendb(name=None, password=None, admin=False, db=None):
    """Open database.

    Returns a DBProxy, with either a user context (name and password
    specified), an administrative context (admin is True), or no context.

    :keyparam name: Username
    :keyparam password: Password
    :keyparam admin: Open DBProxy with an administrative context
    :keyparam db: Use an existing DB instance.
    :return: DBProxy
    """
    
    # Import here to avoid issues with publicmethod.
    db = db or DB()
    
    # Create the proxy and login, as a user or admin.
    proxy = emen2.db.proxy.DBProxy(db=db)
    if name:
        proxy._login(name, password)
    elif admin:
        ctx = emen2.db.context.SpecialRootContext()
        ctx.refresh(db=proxy)
        proxy._ctx = ctx
    return proxy

def setup(db=None, rootpw=None, rootemail='root@localhost'):
    """Create root user, basic groups, and root record.

    :keyword db: DBProxy
    :keyword rootpw: Root Account Password
    :keyword rootemail: Root Account email
    """
    db = db or opendb(db=db, admin=True)

    with db:
        # Initialize the core parameters and recorddefs
        infile = emen2.db.config.get_filename('emen2', 'db/core.json')
        loader = emen2.db.load.Loader(db=db, infile=infile)
        loader.load(keytype='paramdef')
        loader.load(keytype='recorddef')
    
    # Rebuild the paramdef indexes.
    with db:
        db._db.dbenv['paramdef'].rebuild_indexes(ctx=db._ctx, txn=db._txn)    

    with db:
        # Create a root user
        if db.user.get('root'):
           print "Admin account and default groups already exist."
           return

        print "\n=== Setup Admin (root) account ==="
        rootpw = getpw(pw=rootpw)
        root = {'name':'root', 'email':rootemail, 'password':rootpw, 'name_last':'Admin'}
        db.user.put(root)

        # Create default groups
        groups = {}
        groups['admin'] = {'displayname':'Administrators', 'permissions':[[],[],[],['root']]}
        groups['readadmin'] = {'displayname':'Read-only'}
        groups['create'] = {'displayname':'Create records'}
        groups['authenticated'] = {'displayname':'Authenticated users'}
        groups['anon'] = {'displayname':'Anonymous users'}
        for k,v in groups.items():
            v['name'] = k
            db.group.put(v)

        # Create an initial record
        rec = {'name':'root', 'rectype':'root', 'groups':['authenticated']}
        db.record.put(rec)

##### Main Database Class #####

class DB(object):
    """EMEN2 Database."""

    def __init__(self, dbenv=None):
        """(Internal) EMEN2 Database.
        :keyword dbenv: Pass an existing EMEN2DBEnv.
        """
        # Cache for contexts
        self.contexts_cache = {}
        # Open the database
        self.dbenv = dbenv or backend.EMEN2DBEnv()

    ##### Utility methods #####

    def _getcontext(self, ctxid, host, ctx=None, txn=None):
        """(Internal) Get and update user Context.

        :param ctxid: ctxid
        :param host: host
        :return: Context
        :exception: SessionError
        """
        context = None
        if ctxid:
            if ctxid in self.contexts_cache:
                context = self.contexts_cache.get(ctxid)
            try:
                context = self.dbenv._context._get_data(ctxid, txn=txn)
            except KeyError:
                raise SessionError, "Session expired"
        else:
            # If no ctxid was provided, make an Anonymous Context.
            context = emen2.db.context.AnonymousContext(host=host)
            
        # If no ctxid was found, it's an invalid or expired Context.
        if not context:
            raise SessionError, "Session expired"

        # Fetch group memberships.
        grouplevels = {}
        if context.username != 'anonymous':
            groups = self.dbenv['group'].find('permissions', context.username, txn=txn)
            grouplevels = {}
            for group in groups:
                group = self.dbenv["group"]._get_data(group, txn=txn)
                grouplevels[group.name] = group.getlevel(context.username)

        # Sets the database reference, user record, display name, 
        # groups, and updates context access time. 
        # This will raise a SessionError if the host has changed.
        context.refresh(grouplevels=grouplevels, host=host, db=self)
        
        # Cache Context.
        self.contexts_cache[ctxid] = context

        return context

    def _sudo(self, username='root', ctx=None, txn=None):
        """(Internal) Create an admin context for performing actions that require admin privileges.
        :keyword username: Requested username
        :return: New SpecialRootContext, with requested username instead or root
        """
        emen2.db.log.security("Created special root context for %s."%username)
        ctx = emen2.db.context.SpecialRootContext()
        ctx.refresh(db=self, username=username)
        return ctx

    def _mapput(self, keytype, names, method, ctx=None, txn=None, *args, **kwargs):
        """(Internal) Get keytype items, run a method with *args **kwargs, and put updated items.

        This method is used to get a bunch of DBOs, run each instance's
        specified method and commit.

        :param keytype: DBO keytype
        :param names: DBO names
        :param method: DBO method
        :param args: method args
        :param kwargs: method kwargs
        :return: Results of commit/puts
        """
        items = self.dbenv[keytype].gets(names, ctx=ctx, txn=txn)
        for item in items:
            getattr(item, method)(*args, **kwargs)
        return self.dbenv[keytype].puts(items, ctx=ctx, txn=txn)

    def _user_by_email(self, name, ctx=None, txn=None):
        """(Internal) Lookup a user by name or email address.
        
        :param name: Username or email
        :return: User (no bound Context)
        """
        name = unicode(name or '').strip().lower()
        found = self.dbenv['user'].find('email', name, txn=txn)
        if found:
            name = found.pop()
        return self.dbenv["user"]._get_data(name, txn=txn)

    def _find(self, keytype, query=None, defaultparams=None, ctx=None, txn=None, **kwargs):
        query = filter(None, [i.strip() for i in unicode(query or '').split()])
        defaultparams = defaultparams or []
        found = None
        op = "starts"
        cs = []
        for param,term in kwargs.items():
            cs.append([[param, op, term]])
        for term in query:
            c = []
            for param in defaultparams:
                c.append([param, op, term])
            cs.append(c)
        for c in cs:
            r = set()
            for param, op, term in c:
                r |= self.dbenv[keytype].find(param, term, op=op, txn=txn)
            if found is None:
                found = r
            else:
                found &= r
        return self.dbenv[keytype].gets(found or [], ctx=ctx, txn=txn)

    def _view_kv(self, params):
        """(Internal) Create an HTML table for rendering.

        :param params: Use these ParamDef names
        :keyword paramdefs: ParamDef cache
        :return: View template
        """
        dt = ["""<table class="e2l-kv e2l-shaded">
                <thead><th>Parameter</th><th>Value</th></thead>
                <tbody>"""]
        for i in params:
            dt.append("\t\t<tr><td>{{%s?}}</td><td>{{%s}}</td></tr>"%(i,i))
        dt.append("\t<thead>\n</table>")
        return "\n".join(dt)                

    ######################################
    ###### Begin Public API          #####
    ######################################

    ##### Time #####

    @publicmethod()
    def time_difference(self, t1, t2=None, ctx=None, txn=None):
        """Returns the difference between two ISO8601 format timestamps, in seconds.
        
        Examples:
        
        >>> db.time.difference('2013-05-01')
        7861667.0
        
        >>> db.time.difference('1990')
        725932042.0

        
        :param t1: The first time.
        :keyword t2: The second time; defaults to now.
        :return: Time difference, in seconds.
        """
        return utcdifference(t1, t2)
        
    @publicmethod()
    def time_now(self, ctx=None, txn=None):
        """Return current UTC time in ISO8601 format.

        Examples:

        >>> db.time()
        2011-10-10T14:23:11+00:00

        :return: Current UTC time in ISO8601 format.
        """
        return utcnow()

    ###### Version ######

    @publicmethod()
    def version(self, program="API", ctx=None, txn=None):
        """Returns current version of API or specified program.

        Examples:

        >>> db.version()
        2.2.9

        :keyword program: Check version for this program (API, emen2client, etc.)
        :return: Version string
        """
        return VERSIONS.get(program)

    ##### Utilities #####

    @publicmethod()
    def ping(self, ctx=None, txn=None):
        """Simple ping response.

        Examples:

        >>> db.ping()
        'pong'

        :return: Ping? 'pong'
        """
        return 'pong'

    ##### Login and Context Management #####

    def _auth_login_addrate(self, name):
        attempts = LOGIN_RATES.get(name, [])
        attempts.append(time.time())
        LOGIN_RATES[name] = attempts

    def _auth_login_checkrate(self, name):
        # Check login rate limits.
        # Ok, this is an initial implementation. Hopefully, to be improved.
        now = time.time()
        rate = emen2.db.config.get('security.login_rate') # 180
        tries = emen2.db.config.get('security.login_attempts') # 5
        block = emen2.db.config.get('security.login_block') # 900
        attempts = LOGIN_RATES.get(name, [])
        # print "rate/tries/block/attempts", rate, tries, block, attempts
        if len(attempts) >= tries:
            # Blocked until 900 seconds elapsed from last attempt.
            if now > (max(attempts) + block):
                # Clear attempts.
                LOGIN_RATES[name] = []
                return True
            else:
                # Keep block
                return False

        # We haven't hit 5 attempts in 180 seconds.
        # Let older attempts fall off.
        LOGIN_RATES[name] = [i for i in attempts if i >= (now - rate)]
        return True

    @publicmethod(write=True, compat="login")
    def auth_login(self, username, password, host=None, ctx=None, txn=None):
        """Login.

        Returns auth token (ctxid), or fails with AuthenticationError.

        Examples:

        >>> db.auth.login(username='example@example.com', password='foobar')
        654067667525479cba8eb2940a3cf745de3ce608

        >>> db.auth.login(username='ian@example.com', password='foobar')
        AuthenticationError, "Invalid username, email, or password"

        :keyword username: Account name or email address
        :keyword password: Account password
        :keyword host: Bind auth token to this host. This is set by the proxy class.
        :return: Auth token (ctxid)
        :exception AuthenticationError: Invalid user username, email, or password
        """
        # Strip the attempted login name.
        username = unicode(username).lower().strip()

        # Note: error message to user is the same regardless of missing key,
        # bad username, or bad password.. so they cannot fish for accounts.

        # Check login rates.
        if not self._auth_login_checkrate(username):
            raise TooManyAttempts

        # Get the user. This can be the user name or email.
        try:
            user = self._user_by_email(username, txn=txn)
        except KeyError, e:
            emen2.db.log.security("Login failed: No such user: %s"%(username))
            self._auth_login_addrate(username)              
            raise AuthenticationError

        # Now that we have a user name, get the events log.
        try:
            events = self.dbenv._user_history._get_data(user.name, txn=txn)
        except KeyError:
            events = self.dbenv._user_history.new(name=user.name, txn=txn)
            
        # Check the password and expiration.
        try:
            user.login(password, events=events)
        except DisabledUserError, e:
            emen2.db.log.security("Login failed: Disabled user: %s"%(user.name))
            raise DisabledUserError
        except InactiveAccount, e:
            emen2.db.log.security("Login failed: Inactive user: %s"%(user.name))
            raise InactiveAccount
        except AuthenticationError, e:
            emen2.db.log.security("Login failed: Bad password: %s"%(user.name))                
            # Block based on the attempted login name, not user.name;
            #   prevents cross-checking of user name and email.
            self._auth_login_addrate(username)
            raise AuthenticationError

        # Create the Context for this user/host
        newcontext = emen2.db.context.Context(username=user.name, host=host)

        # Put the Context.
        self.dbenv._context._put_data(newcontext.name, newcontext, txn=txn)
        
        # Add the last login to the user's history.
        events.prunehistory(param='context', limit=1)
        events.addhistory(utcnow(), user.name, 'context', newcontext.name)
        self.dbenv._user_history._put_data(events.name, events, txn=txn)

        emen2.db.log.security("Login succeeded: %s -> %s" % (newcontext.username, newcontext.name))
        return newcontext.name

    @publicmethod(write=True, compat="logout")
    def auth_logout(self, ctx=None, txn=None):
        """Delete context and logout.

        Examples:

        >>> db.auth.logout()
        None        
        """
        if ctx.name in self.contexts_cache:
            self.contexts_cache.pop(ctx.name, None)
        if self.dbenv._context.bdb.exists(ctx.name, txn=txn):
            self.dbenv._context.bdb.delete(ctx.name, txn=txn)
        else:
            raise SessionError, "Session expired"
        emen2.db.log.security("Logout succeeded: %s" % (ctx.name))

    @publicmethod(compat="checkcontext")
    def auth_check_context(self, ctx=None, txn=None):
        """Return basic information about the current Context.

        Examples:

        >>> db.auth.check.context()
        (ian, set(['admin', 'authenticated']))

        :return: (Context User name, set of Context groups)
        """
        return ctx.username, ctx.groups

    @publicmethod(compat="checkadmin")
    def auth_check_admin(self, ctx=None, txn=None):
        """Checks if the user has global write access.

        Examples:

        >>> db.auth.check.admin()
        True

        :return: True if user is an administrator.
        """
        return ctx.checkadmin()

    @publicmethod(compat="checkreadadmin")
    def auth_check_readadmin(self, ctx=None, txn=None):
        """Checks if the user has global read access.

        Examples:

        >>> db.auth.check.readadmin()
        True

        :return: True if user is a read administrator.
        """
        return ctx.checkreadadmin()

    @publicmethod(compat="checkcreate")
    def auth_check_create(self, ctx=None, txn=None):
        """Check for permission to create records.

        Examples:

        >>> db.auth.check.create()
        True

        :return: True if the user can create records.
        """
        return ctx.checkcreate()

    ##### Generic methods #####
        
    @publicmethod()
    def exists(self, name, keytype='record', ctx=None, txn=None):
        """Check for the existence of an item.
        
        This method is the same as:
            db.<keytype>.exists(name)

        See these methods (e.g. record.exists) for additional details.    
        """
        return self.dbenv[keytype].exists(name, txn=txn)

    @publicmethod()
    @ol('names')
    def get(self, names, keytype='record', filt=True, ctx=None, txn=None):
        """Get item(s).

        This method is the same as:
            db.<keytype>.get(items)
            
        See these methods (e.g. record.get) for additional details.    
        """
        return getattr(self, '%s_get'%(keytype))(names, filt=filt, ctx=ctx, txn=txn)

    @publicmethod()
    def new(self, *args, **kwargs):
        """Construct a new item.

        This method is the same as:
            db.<keytype>.new(*args, **kwargs)
            
        See these methods (e.g. record.new) for additional details.
        """
        keytype = kwargs.pop('keytype', 'record')
        return getattr(self, '%s_new'%(keytype))(*args, **kwargs)

    @publicmethod(write=True)
    @ol('items')
    def put(self, items, keytype='record', ctx=None, txn=None):
        """Put item(s).

        This method is the same as:
            db.<keytype>.put(items)

        See these methods (e.g. record.put) for additional details.
        """
        return getattr(self, '%s_put'%(keytype))(items, ctx=ctx, txn=txn)

    # @publicmethod(write=True)
    # def delete(self, names, keytype='record', ctx=None, txn=None):
    #     """Delete item(s)."""
    #     keytype = kwargs.pop('keytype', 'record')
    #     return getattr(self, '%s_delete'%(keytype))(ctx=ctx, txn=txn)
    
    # @publicmethod()
    # def find(self, keytype='record', ctx=None, txn=None):
    #     """A simple query."""
    #     keytype = kwargs.pop('keytype', 'record')
    #     return getattr(self, '%s_find'%(keytype))(ctx=ctx, txn=txn)

    # def _query2(self, *c, **kwargs):
    #     """Experimental."""
    #     keytype = kwargs.pop('keytype','record')
    #     ctx = kwargs.pop('ctx')
    #     txn = kwargs.pop('txn')
    #     c = list(c)
    #     for k,v in kwargs.items():
    #         c.append([k, 'is', v])
    #     return self.query(c, keytype=keytype, ctx=ctx, txn=txn)['names']

    @publicmethod()
    def query(self, c=None, mode='AND', sortkey='name', pos=0, count=0, reverse=None, subset=None, keytype="record", ctx=None, txn=None, **kwargs):
        """General query.

        Constraints are provided in the following format:
            [param, operator, value]

        Operation and value are optional for each constraint.

        Operators:
            is        or      ==
            not       or      !=
            gt        or      >
            lt        or      <
            gte       or      >=
            lte       or      <=
            any
            none
            starts
            noop
            name

        Examples constraints:
            ['creator', 'is', 'ian']
            ['rectype', 'is', 'image_capture*']
            [['modifytime', '>=', '2011'], ['name_pi', 'starts', 'steve']]

        For record names, parameter names, and protocol names, a '*' can be used to also match children, e.g:
            [['children', 'name', '136*'], ['rectype', '==', 'image_capture*']]
        Will match all children of record 136, recursively, for any child protocol of image_capture.

        The result will be a dictionary containing all the original query arguments, plus:
            names:    Names of records found
            stats:    Query statistics
                length   Number of records found
                time     Execution time

        Examples:

        >>> db.query()
        {'names':['1','2', ...], 'stats': {'time': 0.001, 'length':1234}, 'c': [], ...}

        >>> db.query([['creator', 'is', 'ian']])
        {'names':['1','2','3'], 'stats': {'time': 0.002, 'length':3}, 'c': [['creator', 'is', 'ian]], ...}

        >>> db.query([['creator', 'is', 'ian']], sortkey='creationtime', reverse=True)
        {'names':['3','2','1'], 'stats': {'time': 0.002, 'length':3}, 'c': [['creator', 'is', 'ian]], 'sortkey': 'creationtime' ...}

        :keyparam c: Constraints
        :keyparam mode: AND / OR on constraints
        :keyparam sortkey: Sort returned records by this param
        :keyparam pos: Return results starting from position
        :keyparam count: Return a limited number of results
        :keyparam reverse: Reverse sorting
        :keyparam subset: Restrict to names
        :keyparam keytype: Key type
        :return: A dictionary containing the original query arguments, and the result in the 'names' key
        :exception KeyError:
        :exception ValidationError:
        :exception PermissionsError:
        """
        count, pos = int(count), int(pos) # check
        c = c or []
        ret = dict(
            c=c[:], #copy
            mode=mode,
            sortkey=sortkey,
            pos=pos,
            count=count,
            reverse=reverse,
            stats={},
            keytype=keytype,
            subset=subset,
        )
        # Run the query
        q = self.dbenv[keytype].query(c=c, mode=mode, subset=subset, ctx=ctx, txn=txn)
        q.run()
        ret['names'] = q.sort(sortkey=sortkey, pos=pos, count=count, reverse=reverse)
        ret['stats']['length'] = len(q.result)
        ret['stats']['time'] = q.time
        return ret

    @publicmethod()
    def table(self, c=None, mode='AND', sortkey='name', pos=0, count=100, reverse=None, subset=None, checkbox=False, viewdef=None, keytype="record", view=None, ctx=None, txn=None, **kwargs):
        """Query results in table format.
        
        This method extends query() to include rendered values in the results.
        These are available in the 'rendered' key in the return value. Key is
        the item name, value is a list of the values for each column. The
        headers for each column are in the 'keys_desc' key.

        The maximum number of items returned in the table is 1000.
        
        Examples:
        
        >>> db.table([['creator', '==', 'ian']])
        {   'names':['3','2','1'], 
            'stats': {'time': 0.002, 'length':3}, 
            'c': [['creator', 'is', 'ian]], 
            'sortkey': 'creationtime',
            'rendered': {
                '1': {'recname()': 'Folder 1', 'rectype': 'folder', 'creator': 'ian', ...},
                '2': {'recname()': 'Folder 2', 'rectype': 'folder', 'creator': 'ian', ...},
                '3': {'recname()': 'Folder 3', 'rectype': 'folder', 'creator': 'ian', ...}
            },
            'keys_desc': {'recname()': 'recname: ', 'creator': 'Created by', 'creationtime': 'Creation time', 'rectype': 'Protocol', 'name': 'ID'}
            ...
        }
        
        :keyparam c: Constraints
        :keyparam mode: AND / OR on constraints
        :keyparam sortkey: Sort returned records by param
        :keyparam pos: Return results starting from position
        :keyparam count: Return a limited number of results
        :keyparam reverse: Reverse sorting
        :keyparam subset: Restrict to names
        :keyparam keytype: Key type
        :keyparam view: View template
        """
        options = {}
        options['lnf'] = True
        options['time_precision'] = 3
        
        # Limit tables to 1000 items per page.
        count, pos = int(count), int(pos) # check        
        if count < 1 or count > 1000:
            count = 1000

        # Records are shown newest-first by default...
        if keytype == "record" and sortkey in ['name', 'creationtime'] and reverse is None:
            reverse = True

        c = c or []
        ret = dict(
            c=c[:], # copy
            mode=mode,
            sortkey=sortkey,
            pos=pos,
            count=count,
            reverse=reverse,
            stats={},
            keytype=keytype,
            subset=subset,
            checkbox=checkbox,
        )

        # Run the query
        q = self.dbenv[keytype].query(c=c, mode=mode, subset=subset, ctx=ctx, txn=txn)
        q.run()
        names = q.sort(sortkey=sortkey, pos=pos, count=count, reverse=reverse, rendered=True)

        # Additional time
        t = time.time()

        # Build the view
        defaultview = "{{recname()}} {{rectype}} {{name}}"
        rectypes = set(q.cache[i].get('rectype') for i in q.result)
        rectypes -= set([None])

        if not view and not rectypes:
            view = defaultview
        elif not view:
            # Check which views we need to fetch
            toget = []
            for i in q.result:
                if not q.cache[i].get('rectype'):
                    toget.append(i)

            if toget:
                rt = self.record_groupbyrectype(toget, ctx=ctx, txn=txn)
                for k,v in rt.items():
                    for name in v:
                        q.cache[name]['rectype'] = k

            # Update
            rectypes = set(q.cache[i].get('rectype') for i in q.result)
            rectypes -= set([None])

            # Get the view
            if len(rectypes) == 1:
                rd = self.dbenv["recorddef"].get(rectypes.pop(), ctx=ctx, txn=txn)
                view = rd.views.get('tabularview', defaultview)
            else:
                try:
                    rd = self.dbenv["recorddef"].get("root", filt=False, ctx=ctx, txn=txn)
                except (KeyError, PermissionsError):
                    view = defaultview
                else:
                    view = rd.views.get('tabularview', defaultview)

        # Render the table
        view = self._view_convert(view or '{{name}}')
        for i in emen2.db.config.get('customization.table_add_columns'):
            view = '%s {{%s}}'%(view.replace('{{%s}}'%i, ''), i)
        keys = self._view_keys(view)

        table = self.render(names, keys=keys, options=options, keytype=keytype, ctx=ctx, txn=txn)

        # Header labels
        header_desc = {}
        for pd in self.dbenv['paramdef'].gets(keys, ctx=ctx, txn=txn):
            header_desc[pd.name] = pd.desc_short
        # Quick fix :(
        for i in keys:
            if i not in header_desc and i.endswith(')'):
                header_desc[i] = i.replace('(', ': ').replace(')','')

        # Return format
        ret['view'] = view
        ret['keys'] = keys
        ret['keys_desc'] = header_desc    
        ret['rendered'] = table
        ret['names'] = names
        ret['stats']['length'] = len(q.result)
        ret['stats']['time'] = q.time + (time.time()-t)
        return ret

    @publicmethod()
    def plot(self, c=None, mode='AND', sortkey='name', pos=0, count=0, reverse=None, subset=None, keytype="record", x=None, y=None, z=None, ctx=None, txn=None, **kwargs):
        """Query results suitable for plotting.

        This method extends query() to help generate a plot. The results are
        not sorted; the sortkey, pos, count, and reverse keyword arguments
        are ignored.

        Provide dictionaries for the x, y, and z keywords. These may have the
        following keys:
            key:    Parameter name for this axis.
            bin:    Number of bins, or date width for time parameters.
            min:    Minimum
            max:    Maximum

        Currently only the 'key' from x, y, z argument is used to make
        sure it is part of the query that runs.

        The matching values for each constraint are available in the "items"
        key in the return value. This is a list of stub items.
        
        Examples:
        
        >>> db.plot(x={'key':'ctf_bfactor'}, y={'key':'ctf_defocus_set'})
        {   
            'names':['6','5','4'], 
            'stats': {'time': 0.002, 'length':3}, 
            'c': [],
            'y': {'key': 'ctf_defocus_set'}, 
            'x': {'key': 'ctf_bfactor'}, 
            'z': {},
            'recs': [
                {'ctf_defocus_set': 1.1, 'ctf_bfactor': 188.406, 'name': u'6'},
                {'ctf_defocus_set': 1.2, 'ctf_bfactor': 148.551, 'name': u'5'},
                {'ctf_defocus_set': 1.3, 'ctf_bfactor': 142.121, 'name': u'4'}
            ]
            ...
        }        

        :keyparam c: Constraints
        :keyparam mode: AND / OR on constraints
        :keyparam x: X arguments
        :keyparam y: Y arguments
        :keyparam z: Z arguments
        :keyparam subset: Restrict to names        
        :keyparam keytype: Key type
        """
        count, pos = int(count), int(pos) # check        
        x = x or {}
        y = y or {}
        z = z or {}
        c = c or []
        ret = dict(
            c=c[:],
            x=x,
            y=y,
            z=z,
            mode=mode,
            stats={},
            keytype=keytype,
            subset=subset,
        )

        qparams = [i[0] for i in c]
        qparams.append('name')
        for axis in [x.get('key'), y.get('key'), z.get('key')]:
            if axis and axis not in qparams:
                c.append([axis, 'any', None])
                
        # Run the query
        q = self.dbenv[keytype].query(c=c, mode=mode, subset=subset, ctx=ctx, txn=txn)
        q.run()

        ret['names'] = q.sort(sortkey=sortkey, pos=pos, count=count, reverse=reverse)
        ret['stats']['length'] = len(q.result)
        ret['stats']['time'] = q.time
        ret['recs'] = q.cache.values()
        return ret
    
    # @publicmethod()
    # def groupby(self, c=None, mode='AND', sortkey='name', pos=0, count=0, reverse=None, subset=None, keytype="record", ctx=None, txn=None, **kwargs):
    #   pass

    @publicmethod()
    @ol('names')
    def render(self, names, keys=None, keytype='record', options=None, ctx=None, txn=None):
        """Render keys.

        Examples:

        >>> db.render('0')
        {'name': u'0', 'creator': u'Admin', u'name_folder': u'EMEN2', ...}

        >>> db.render(['0', '1'])
        {
            u'0': {'name': u'0', 'creator': u'Admin', u'name_folder': u'EMEN2', ...}
            u'1': {'name': u'1', 'creator': u'Admin', 'recname': u'Microscopes', ...}
        }

        >>> db.render('0', keys=['name_folder'], options={'output':'form'})
        {u'name_folder': Markup(u'<span class="e2-edit" data-paramdef="name_folder" 
            data-vartype="string"><input type="text" name="name_folder" value="EMEN2" /></span>'), ...}

        :param names:
        :keyword keys: Render these keys; otherwise, render most keys.
        :keyword keytype: Key type
        :keyword options: Dictionary of options to control rendering, may include keys 'output', 'tz', 'lnf', etc.
        :return: Either the single rendered view, or a dictionary of names and rendered views.
        """
        # Some rendering options
        options = options or {}

        # Get Record instances from names argument.
        names, recs, newrecs, other = emen2.utils.typepartition(names, basestring, emen2.db.dataobject.BaseDBObject, dict)
        names.extend(other)
        recs.extend(self.dbenv[keytype].gets(names, ctx=ctx, txn=txn))

        # If input is a dict, make DBO.
        for newrec in newrecs:
            rec = self.dbenv[keytype].new(ctx=ctx, txn=txn, **newrec) 
            rec.update(newrec)
            recs.append(rec)
        
        # If no keys specified, render almost everything...
        if keys is None:
            keys = set()
            for i in recs:
                keys |= set(i.keys())
            # Except these keys...
            keys -= set(['permissions', 'history', 'comments'])
        
        # Process keys.
        regex_k = re.compile(VIEW_REGEX_P, re.VERBOSE)
        params = set()
        macros = set()
        descs = set()
        for key in keys:
            match = regex_k.search(key)
            m = match.group('name')
            if m.endswith('?'):
                descs.add(m[:-1])
            elif match.group('args') or match.group('emptyargs'):
                macros.add((key, m, match.group('args') or ''))
            else:
                params.add(m)
                
        # Process parameters and descriptions.
        pds = emen2.utils.dictbykey(self.dbenv["paramdef"].gets(params | descs, ctx=ctx, txn=txn), 'name')
        found = set(pds.keys())
        missed = (params - found) | (descs - found)
        params -= missed
        descs -= missed

        # Process macros.
        for key, macro, args in macros:
            macro = emen2.db.macros.Macro.get_macro(macro, db=ctx.db, cache=ctx.cache)
            macro.preprocess(args, recs)

        # Render.
        ret = {}
        for rec in recs:
            r = {}
            for key in params:
                pd = pds[key]
                vt = emen2.db.vartypes.Vartype.get_vartype(pd.vartype, pd=pd, db=ctx.db, cache=ctx.cache, options=options)
                r[key] = vt.render(rec.get(key))
            for key in descs:
                r[key+'?'] = pds[key].desc_short
            for key,macro,args in macros:
                macro = emen2.db.macros.Macro.get_macro(macro, db=ctx.db, cache=ctx.cache)
                r[key] = macro.render(args, rec)
            ret[rec.name] = r
        return ret
        
    def _view_convert(self, view):
        """(Internal) Convert old view to {{newstyle}}."""
        regex_classic = re.compile(VIEW_REGEX_CLASSIC, re.VERBOSE)
        ret = view
        for match in regex_classic.finditer(view):
            m = match.groups()[0]
            key = match.group('name')
            if match.group('args') or match.group('emptyargs'):
                key = '%s(%s)'%(match.group('name'), match.group('args') or '')
            if m.startswith('$#'):
                key = '%s?'%key
            ret = ret.replace(m, '{{%s}}%s'%(key, match.group('sep') or ''))
        return ret
        
    def _view_keys(self, view):
        """(Internal) Parse {{newstyle}} for keys."""
        regex_m = re.compile(VIEW_REGEX_M, re.VERBOSE)
        keys = [] # needs to be ordered, not a set
        for match in regex_m.finditer(view):
            key = match.group('name')
            if match.group('args') or match.group('emptyargs'):
                key = '%s(%s)'%(match.group('name'), match.group('args') or '')
            keys.append(key)
        return keys
    
    def _view_render(self, view, recs):
        """(Internal) Render view. 
        View is a {{newstyle}} view
        recs is the result of self.render(), a dict containing rendered record dicts.
        """
        # Copy the view
        ret = {}
        for name in recs:
            ret[name] = view
        # Process the view
        regex_m = re.compile(VIEW_REGEX_M, re.VERBOSE)
        for match in regex_m.finditer(view):
            key = match.group('name')
            if match.group('args'):
                key = '%s(%s)'%(match.group('name'), match.group('args') or '')
            # Replace the values.
            for name, rec in recs.items():
                ret[name] = ret[name].replace(match.groups()[0], rec.get(key, ''))
        return ret

    @publicmethod()
    @ol('names')
    def view(self, names, view=None, viewname='recname', keytype='record', options=None, ctx=None, txn=None):
        """Render a view template.
        
        Examples:
        
        >>> db.view('136')
        'NCMI Group'
    
        >>> db.view('136', view='{{name_group}} created by {{creator}}')
        'NCMI Group created by Administrator'
    
        >>> db.view(['0', '1'])
        {'0':'Record 0 view', '1': 'Record 1 view'}
    
        >>> db.view('0', options={'output':'form'})
        '<span class="e2-edit"><input type="text" name="name_folder" />.....'
            
        :param names: Item(s) to render
        :keyparam view: A view template
        :keyparam viewname: A view template from the item's RecordDef views.
        :keyparam keytype: Key type
        :keyparam options: A dictionary containing rendering options, may include 'output', 'tz', 'lnf', etc., keys.    
        """
        options = options or {}
        ret = {}
        views = collections.defaultdict(set)
        default = "{{rectype}} created by {{creator}} on {{creationtime}}"
        
        # Just show date for most views.
        if view or viewname != 'recname':
            options['time_precision'] = 0
        else:
            options['time_precision'] = 3

        # Get Record instances from names argument.
        names, recs, newrecs, other = emen2.utils.typepartition(names, basestring, emen2.db.dataobject.BaseDBObject, dict)
        names.extend(other)
        recs.extend(self.dbenv[keytype].gets(names, ctx=ctx, txn=txn))
        for newrec in newrecs:
            rec = self.dbenv[keytype].new(ctx=ctx, txn=txn, **newrec)
            rec.update(newrec)
            recs.append(rec)

        if view:
            views[view] = recs
        elif keytype == 'record':
            # Get a view by name using the item's recorddef.
            byrt = collections.defaultdict(set)
            for rec in recs:
                byrt[rec.rectype].add(rec)
            for recdef in self.dbenv['recorddef'].gets(byrt.keys(), ctx=ctx, txn=txn):
                if viewname == 'mainview':
                    v = recdef.mainview
                elif viewname == 'kv':
                    v = self._view_kv(rec.keys())
                else:
                    v = recdef.views.get(viewname) or recdef.views.get('recname') or default
                views[v] = byrt[recdef.name]
        else:
            views["{{name}}"] = recs
        
        # Optional: Apply MarkDown formatting to view before inserting values.
        if options.get('markdown'):
            views2 = {}
            for k,v in views.items():
                k = k.replace('\n','  \n') # test..
                views2[markdown.markdown(k)] = v
            views = views2
            
        # Render.
        for view, recs in views.items():
            view = view or '{{name}}'
            view = self._view_convert(view)
            keys = self._view_keys(view)
            recs = self.render(recs, keys=keys, ctx=ctx, txn=txn, options=options)
            ret.update(self._view_render(view, recs))
        return ret

    ##### Relationships #####

    @publicmethod()
    @ol('names', output=False)
    def rel_find(self, names, keytype='record', ctx=None, txn=None, **kwargs):
        recs = self.dbenv['record'].gets(names, ctx=ctx, txn=txn, filt=None)
        found = set()
        allparams = set()
        for rec in recs:
            allparams |= set(rec.keys())

        if keytype == 'paramdef':
            found = allparams
        else:
            params = self.dbenv['paramdef'].gets(allparams, ctx=ctx, txn=txn)
            params = [param for param in params if param.vartype == keytype]
            for param in params:
                for rec in recs:
                    value = rec.get(param.name)
                    # print "->", param, rec, value
                    if value is None:
                        continue
                    if param.iter:
                        for i in value:
                            found.add(i)
                    else:
                        found.add(value)

        if kwargs:
            second = self._find(keytype, ctx=ctx, txn=txn, **kwargs)
            second = set([i.name for i in second])
            found &= second

        return found

    @publicmethod(write=True, compat="pclink")
    def rel_pclink(self, parent, child, keytype='record', ctx=None, txn=None):
        """Link a parent object with a child

        Examples:

        >>> db.rel.pclink('0', '46604')
        None

        >>> db.rel.pclink('physical_property', 'temperature', keytype='paramdef')
        None

        :param parent: Parent name
        :param child: Child name
        :keyword keytype: Item type
        :keyword filt: Ignore failures
        :return:
        :exception KeyError:
        :exception PermissionsError:
        """
        return self.dbenv[keytype].pclink(parent, child, ctx=ctx, txn=txn)

    @publicmethod(write=True, compat="pcunlink")
    def rel_pcunlink(self, parent, child, keytype='record', ctx=None, txn=None):
        """Remove a parent-child link

        Examples:

        >>> db.rel.pcunlink('0', '46604')
        None

        >>> db.rel.pcunlink('physical_property', 'temperature', keytype='paramdef')
        None

        :param parent: Parent name
        :param child: Child name
        :keyword keytype: Item type
        :keyword filt: Ignore failures
        :return:
        :exception KeyError:
        :exception PermissionsError:
        """
        return self.dbenv[keytype].pcunlink(parent, child, ctx=ctx, txn=txn)

    @publicmethod(write=True)
    def rel_relink(self, removerels=None, addrels=None, keytype='record', ctx=None, txn=None):
        """Add and remove a number of parent-child relationships at once.

        Examples:

        >>> db.rel.relink({"0":"136"}, {"100":"136"})
        None

        :keyword removerels: Dictionary of relationships to remove.
        :keyword addrels: Dictionary of relationships to add.
        :keyword keytype: Item keytype
        :keyword filt: Ignore failures
        :return:
        :exception KeyError:
        :exception PermissionsError:
        """
        return self.dbenv[keytype].relink(removerels, addrels, ctx=ctx, txn=txn)

    @publicmethod(compat="getsiblings")
    def rel_siblings(self, name, keytype="record", ctx=None, txn=None):
        """Get the siblings of the object as a tree.

        Siblings are any items that share a common parent.

        Examples:

        >>> db.rel.siblings('136')
        set(['136', '358307'])

        >>> db.rel.siblings('creationtime', keytype='paramdef')
        set([u'website', u'date_start', u'name_first', u'observed_by', ...])

        >>> db.rel.siblings('ccd', keytype='recorddef')
        set([u'ccd', u'micrograph', u'ddd', u'stack', u'scan'])

        :param names: Item name(s)
        :keyword rectype: Filter by RecordDef. Can be single RecordDef or list.
        :keyword filt: Ignore failures
        :return: All items that share a common parent
        :exception KeyError:
        :exception PermissionsError:
        """
        return self.dbenv[keytype].siblings(name, ctx=ctx, txn=txn)

    @publicmethod(compat="getparents")
    @ol('names')
    def rel_parents(self, names, recurse=1, keytype='record', ctx=None, txn=None):
        """Get the parents of an object

        This method is the same as as db.rel(..., rel='parents', tree=False)

        Examples:

        >>> db.rel.parents('0')
        set([])

        >>> db.rel.parents('46604', recurse=-1)
        set(['136', '0'])

        >>> db.rel.parents('ccd', recurse=-1, keytype='recorddef')
        set([u'image_capture', u'experiments', u'root', u'tem'])

        :param names: Item name(s)
        :keyword recurse: Recursion depth
        :keyword param keytype: Item keytype
        :keyword filt: Ignore failures
        :return:
        :exception KeyError:
        :exception PermissionsError:
        """
        return self.dbenv[keytype].rel(names, recurse=recurse, rel='parents', ctx=ctx, txn=txn)

    @publicmethod(compat="getchildren")
    @ol('names')
    def rel_children(self, names, recurse=1, keytype='record', ctx=None, txn=None):
        """Get the children of an object.

        This method is the same as db.rel(..., rel='children', tree=False)

        >>> db.rel.children('0')
        set(['136', '358307', '270940'])

        >>> db.rel.children('0', recurse=2)
        set(['2', '4', '268295', '260104', ...])

        >>> db.rel.children('root', keytype='paramdef')
        set([u'core', u'descriptive_information', ...])

        :param names: Item name(s)
        :keyword recurse: Recursion depth
        :keyword keytype: Item keytype
        :keyword filt: Ignore failures
        :return:
        :exception KeyError:
        :exception PermissionsError:
        """
        return self.dbenv[keytype].rel(names, recurse=recurse, rel='children', ctx=ctx, txn=txn)

    @publicmethod()
    @ol('names', output=False)
    def rel_tree(self, names, recurse=1, keytype="record", rel="children", ctx=None, txn=None):        
        return self.dbenv[keytype].rel(names, recurse=recurse, rel=rel, tree=True, ctx=ctx, txn=txn)

    @publicmethod()
    @ol('names')
    def rel_rel(self, names, recurse=1, tree=False, rel='children', keytype="record", ctx=None, txn=None):
        return self.dbenv[keytype].rel(names, recurse=recurse, tree=tree, rel=rel, ctx=ctx, txn=txn)

    ##### ParamDef #####

    @publicmethod(compat="getparamdef")
    @ol('names')
    def paramdef_get(self, names, filt=True, ctx=None, txn=None):
        return self.dbenv["paramdef"].gets(names, filt=filt, ctx=ctx, txn=txn)
        
    @publicmethod(compat="newparamdef")
    def paramdef_new(self, *args, **kwargs):
        return self.dbenv["paramdef"].new(*args, **kwargs)
                
    @publicmethod(write=True, compat="putparamdef")
    @ol('items')
    def paramdef_put(self, items, ctx=None, txn=None):
        return self.dbenv["paramdef"].puts(items, ctx=ctx, txn=txn)

    @publicmethod(compat="getparamdefnames")
    def paramdef_filter(self, names=None, ctx=None, txn=None):
        return self.dbenv["paramdef"].filter(names, ctx=ctx, txn=txn)
        
    @publicmethod(compat="findparamdef")
    def paramdef_find(self, query, count=100, ctx=None, txn=None, **kwargs):
        """Find a ParamDef, by general search string, or by searching attributes.

        Examples:

        >>> db.paramdef.find('temperature')
        [<ParamDef temperature>, <ParamDef temperature_ambient>, <ParamDef temperature_cryoholder>, ...]

        :param query: Contained in any item below
        :keyword desc_short: ... in short description
        :keyword desc_long: ... in long description
        :keyword vartype: ... is of vartype(s)
        :keyword count: Limit number of results
        :return: RecordDefs
        """
        defaultparams = ['desc_short', 'desc_long', 'vartype']
        return self._find('paramdef', query, defaultparams=defaultparams, ctx=ctx, txn=txn, **kwargs)
        
    @publicmethod(compat="getpropertynames")
    def paramdef_properties(self, ctx=None, txn=None):
        """Get all supported physical properties.

        A number of physical properties are included by default.
        Extensions may extend this by subclassing emen2.db.properties.Property()
        and using the registration decorator. See that module for details.

        >>> db.paramdef.properties()
        set(['transmittance', 'force', 'bytes', 'energy', 'resistance', ...])

        :return: Set of all available properties.
        """
        return set(emen2.db.properties.Property.registered.keys())

    @publicmethod(compat="getpropertyunits")
    def paramdef_units(self, name, ctx=None, txn=None):
        """Returns a list of recommended units for a particular property.
        Other units may be used if they can be converted to the property's
        default units.

        Examples:

        >>> db.paramdef.units('volume')
        set(['nL', 'mL', 'L', 'uL', 'gallon', 'm^3'])

        >>> db.paramdef.units('length')
        set([u'\xc5', 'nm', 'mm', 'm', 'km', 'um'])

        :param name: Property name
        :return: Set of recommended units for property.
        :exception KeyError:
        """
        if not name:
            return set()
        prop = emen2.db.properties.Property.get_property(name)
        return set(prop.units)

    @publicmethod(compat="getvartypenames")
    def paramdef_vartypes(self, ctx=None, txn=None):
        """Get all supported datatypes.

        A number of parameter data types (vartypes) are included by default.
        Extensions may add extend this by subclassing emen2.db.vartypes.Vartype()
        and using the registration decorator. See that module for details.

        Examples:

        >>> db.paramdef.vartypes()
        set(['text', 'string', 'binary', 'user', ...])

        :return: Set of all available datatypes.
        """
        return set(emen2.db.vartypes.Vartype.registered.keys())

    ##### User #####

    @publicmethod(compat="getuser")
    @ol('names')
    def user_get(self, names, filt=True, ctx=None, txn=None):
        return self.dbenv["user"].gets(names, filt=filt, ctx=ctx, txn=txn)

    @publicmethod()
    def user_new(self, *args, **kwargs):
        raise NotImplementedError, "Use newuser.request() to create new users."
    
    @publicmethod(write=True, compat="putuser")
    @ol('items')
    def user_put(self, items, ctx=None, txn=None):
        return self.dbenv["user"].puts(items, ctx=ctx, txn=txn)

    @publicmethod(compat="getusernames")
    def user_filter(self, names=None, ctx=None, txn=None):
        return self.dbenv["user"].filter(names, ctx=ctx, txn=txn)

    @publicmethod(compat="finduser")
    def user_find(self, query=None, count=100, ctx=None, txn=None, **kwargs):
        """Find a user, by general search string, or by name_first/name_middle/name_last/email/name.

        Keywords can be combined.

        Examples:

        >>> db.user.find('rees')
        [<User ian>, <User kay>, ...]

        :keyword query: Contained in name_first, name_middle, name_last, or email
        :keyword name_first:
        :keyword name_middle:
        :keyword name_last:
        :keyword email:
        :keyword count: Limit number of results
        :return: Users
        """
        defaultparams = ['name_first', 'name_middle', 'name_last', 'email']
        return self._find('user', query, defaultparams=defaultparams, ctx=ctx, txn=txn, **kwargs)
        # # Find users referenced in a record
        # if record:
        #     f = self._findbyvartype(emen2.utils.check_iterable(record), ['user', 'acl', 'comments', 'history'], ctx=ctx, txn=txn)
        #     if foundusers is None:
        #         foundusers = f
        #     else:
        #         foundusers &= f
        
    @publicmethod(write=True, admin=True, compat="disableuser")
    @ol('names')
    def user_disable(self, names, filt=True, ctx=None, txn=None):
        """(Admin Only) Disable a User.

        Examples:

        >>> db.user.disable('steve')
        <User steve>

        >>> db.user.disable(['wah', 'steve'])
        [<User wah>, <User steve>]

        :param names: User name(s)
        :keyword filt: Ignore failures
        :return: Updated user(s)
        :exception KeyError:
        :exception PermissionsError:
        """
        return self._mapput('user', names, 'disable', ctx=ctx, txn=txn)

    @publicmethod(write=True, admin=True, compat="enableuser")
    @ol('names')
    def user_enable(self, names, filt=True, ctx=None, txn=None):
        """(Admin Only) Re-enable a User.

        Examples:

        >>> db.user.enable('steve')
        <User steve>

        >>> db.user.enable(['wah', 'steve'])
        [<User wah>, <User steve>]

        :param names: User name(s)
        :keyword filt: Ignore failures
        :return: Updated user(s)
        :exception KeyError:
        :exception PermissionsError:
        """
        return self._mapput('user', names, 'enable', ctx=ctx, txn=txn)

    @publicmethod(write=True, compat="setprivacy")
    @ol('names')
    def user_setprivacy(self, names, state, ctx=None, txn=None):
        """Set privacy level.

        Examples:

        >>> db.user.setprivacy('ian', 2)
        <User ian>

        >>> db.user.setprivacy(names=['ian', 'wah'], state=2)
        [<User ian>, <User wah>]

        :param state: 0, 1, or 2, in increasing level of privacy.
        :keyword names: User name(s). Default is the current context user.
        :return: Updated user(s)
        :exception KeyError:
        :exception PermissionsError:
        :exception ValidationError:
        """
        return self._mapput('user', names, 'setprivacy', ctx, txn, state)

    # These methods sometimes use put instead of put because they need to modify
    # the user's secret auth token.
    @publicmethod(write=True, compat="setemail")
    def user_setemail(self, name, email, secret=None, password=None, ctx=None, txn=None):
        """Change a User's email address.

        If a mail server is configured, this will require you to verify that
        you own the account by responding with an auth token sent to the new
        email address. Use the received auth token to sign the call using the
        'secret' keyword.
    
        Note: This method only takes a single User name.

        Note: An Admin can change a user's email without the user's password or auth token.

        Examples:

        >>> db.user.setemail('ian', 'ian@example.com', password='foobar')
        <User ian>

        >>> db.user.setemail('ian', 'ian@example.com', secret='654067667525479cba8eb2940a3cf745de3ce608')
        <User ian>

        :param str email: New email address
        :param str secret: Auth token to verify email address is owned by user.
        :param str password: Current User password
        :param str name: User name. Default is current context user.
        :return: Updated user
        :exception KeyError:
        :exception: :py:class:`PermissionsError <PermissionsError>` if the password and/or auth token are wrong
        :exception ValidationError:
        """
        # Verify the email address is owned by the user requesting change.
        # 1. User authenticates they *really* own the account
        #     by providing the acct password
        # 2. An email will be sent to the new account specified,
        #     containing an auth token
        # 3. The user comes back and calls the method with this token
        # 4. Email address is updated
        
        # Check that no other user is currently using this email.
        if self.dbenv['user'].find('email', email, txn=txn):
            time.sleep(2)
            raise ExistingKeyError("The email address %s is already in use"%(email))

        # Do not use get; it will strip out the secret.
        user = self.dbenv["user"]._get_data(name, txn=txn)
        user_secret = getattr(user, 'secret', None)
        user.setContext(ctx)
        if user_secret:
            user.data['secret'] = user_secret
        
        # Try and change user email.
        oldemail = user.email
        try:
            user.setemail(email, secret=secret, password=password)
            user_secret = getattr(user, 'secret', None)
        except SecurityError, e:
            emen2.db.log.security('Failed to change email for %s: %s'%(user.name, e))
            raise e

        # If there is no mail server configured, go ahead and set email.
        from_addr, smtphost = emen2.db.config.mailconfig()
        if user_secret and not (from_addr and smtphost):
            user.setemail(email, secret=user_secret[2], password=password)
        
        ctxt = {}
        ctxt['name'] = user.name
        ctxt['email'] = email
        ctxt['oldemail'] = oldemail

        # Send out confirmation or verification email.
        if user.email == oldemail:
            # Need to verify email address change by receiving secret.
            emen2.db.log.security("Sending email verification for user %s to %s"%(user.name, email))
            self.dbenv["user"]._put(user, ctx=ctx, txn=txn)

            # Send the verify email containing the auth token
            ctxt['secret'] = user_secret[2]
            self.dbenv.txncb(txn, 'email', kwargs={'to_addr':email, 'template':'/email/email.verify', 'ctxt':ctxt})

        else:
            # Verified with secret.
            emen2.db.log.security("Changing email for user %s to %s"%(user.name, user.email))
            self.dbenv['user']._put(user, ctx=ctx, txn=txn)
            # Send the user an email to acknowledge the change
            self.dbenv.txncb(txn, 'email', kwargs={'to_addr':user.email, 'template':'/email/email.verified', 'ctxt':ctxt})

        return self.dbenv["user"].get(user.name, ctx=ctx, txn=txn)

    @publicmethod(write=True, admin=True)
    def user_expirepassword(self, name, ctx=None, txn=None):
        if not ctx.checkadmin():
            raise PermissionsError("Only an administrator may perform this action.")
        # Get the user, and we'll clear their password history.
        # This will force them to set a new password upon logging in.
        user = self._user_by_email(name, ctx=ctx, txn=txn)
        try:
            events = self.dbenv._user_history._get_data(user.name, txn=txn)
        except KeyError:
            events = self.dbenv._user_history.new(name=user.name, txn=txn)    

        h = events.gethistory(param='password')
        events.prunehistory(param='password')
        # for i in h:
        events.addhistory('1900-01-01T00:00:00Z+00:00', 'password', user.name, user.password)

        emen2.db.log.security("Expiring password for %s"%user.name)
        self.dbenv["user"]._put(user, ctx=ctx, txn=txn)
        self.dbenv._user_history._put_data(user.name, events, txn=txn)

    @publicmethod(write=True, compat="setpassword")
    def user_setpassword(self, name, newpassword, password=None, secret=None, ctx=None, txn=None):
        """Change password.

        Note: This method only takes a single User name.

        The 'secret' keyword can be used for 'password reset' auth tokens. See db.resetpassword().

        Examples:

        >>> db.user.setpassword('ian', 'barfoo', password='barfoo')
        <User ian>

        >>> db.user.setpassword('ian', 'barfoo', secret=654067667525479cba8eb2940a3cf745de3ce608)
        <User ian>

        :param newpassword: New password.
        :param password: Old password.
        :keyword secret: Auth token for resetting password.
        :keyword name: User name. Default is the current context user.
        :return: Updated user
        :exception KeyError:
        :exception PermissionsError:
        :exception ValidationError:
        """
        # Try to authenticate using either the password OR the secret!
        # Get the user directly; .get() strips out password in most cases.
        user = self._user_by_email(name, ctx=ctx, txn=txn)
        # if not secret:
        if ctx and ctx.username != 'anonymous':
            user.setContext(ctx)

        # Get the user's events.
        try:
            events = self.dbenv._user_history._get_data(user.name, txn=txn)
        except KeyError:
            events = self.dbenv._user_history.new(name=user.name, txn=txn)

        # Check that we can actually set the password.
        # This will raise a SecurityError if failed.
        try:
            user.setpassword(newpassword, password=password, secret=secret, events=events)
        except SecurityError, e:
            emen2.db.log.security('Failed to change password for %s: %s'%(user.name, e))
            raise e

        # Save the user. Don't use regular .put(), it will fail on setting pw.
        emen2.db.log.security("Changing password for %s"%user.name)
        self.dbenv["user"]._put(user, ctx=ctx, txn=txn)

        # Save the user events.
        recycle = emen2.db.config.get('security.password_recycle') or 0
        events.prunehistory(param='password', limit=recycle)
        events.addhistory(utcnow(), ctx.username, 'password', user.password)
        self.dbenv._user_history._put_data(user.name, events, txn=txn)

        # Send an email on successful commit.
        self.dbenv.txncb(txn, 'email', kwargs={'to_addr':user.email, 'template':'/email/password.changed'})
        return self.dbenv["user"].get(user.name, ctx=ctx, txn=txn)

    @publicmethod(write=True, compat="resetpassword")
    def user_resetpassword(self, name, ctx=None, txn=None):
        """Reset User password.

        This is accomplished by sending a password reset auth token to the
        User's currently registered email address. Use this auth token
        to sign a call to db.setpassword() using the 'secret' keyword.

        Note: This method only takes a single User name.

        Examples:

        >>> db.user.resetpassword()
        <User ian>

        :keyword name: User name. Default is the current context user.
        :return: Updated user
        :exception KeyError:
        :exception PermissionsError:
        """
        
        from_addr, smtphost = emen2.db.config.mailconfig()
        if not (from_addr and smtphost):
            raise emen2.db.exceptions.EmailError, "Mail server is not configured; contact the administrator for help resetting a password."
        
        user = self._user_by_email(name, ctx=ctx, txn=txn)
        user.resetpassword()

        # Use direct put to preserve the secret
        self.dbenv["user"]._put(user, ctx=ctx, txn=txn)

        # Absolutely never reveal the secret via any mechanism
        # but email to registered address
        ctxt = {}
        ctxt['secret'] =  user.secret[2]
        ctxt['name'] = user.name
        self.dbenv.txncb(txn, 'email', kwargs={'to_addr':user.email, 'template':'/email/password.reset', 'ctxt':ctxt})
        emen2.db.log.security("Setting resetpassword secret for %s"%user.name)        
        return self.dbenv["user"].get(user.name, ctx=ctx, txn=txn)

    ##### New Users #####

    @publicmethod(admin=True, compat="getqueueduser")
    @ol('names')
    def newuser_get(self, names, filt=True, ctx=None, txn=None):
        if not ctx.checkadmin():
            raise PermissionsError("Only an administrator may perform this action.")
        return self.dbenv["newuser"].gets(names, filt=filt, ctx=ctx, txn=txn)

    @publicmethod()
    def newuser_new(self, *args, **kwargs):
        # raise NotImplementedError, "Use newuser.request() to create new users."
        return self.dbenv["newuser"].new(*args, **kwargs)

    @publicmethod(write=True)
    @ol('items')
    def newuser_put(self, items, ctx=None, txn=None):
        raise NotImplementedError, "Use newuser.request() to create new users."

    @publicmethod(write=True)
    @ol('items')
    def newuser_request(self, items, ctx=None, txn=None):
        """Request a new user account.

        Note: This only adds the user to the new user queue. The
        account must be processed by an administrator before it
        becomes active.

        Examples:

        >>> db.newuser.request(<NewUser kay>)
        <NewUser kay>

        >>> db.newuser.request({'name':'kay', 'password':'foobar', 'email':'kay@example.com'})
        <NewUser kay>

        :param items: New user(s).
        :return: New user(s)
        :exception KeyError:
        :exception ExistingKeyError:
        :exception PermissionsError:
        :exception ValidationError:
        """
        items = self.dbenv["newuser"].puts(items, ctx=ctx, txn=txn)
        autoapprove = emen2.db.config.get('users.auto_approve')
        if autoapprove:
            rootctx = self._sudo()
            rootctx.db._txn = txn
            self.newuser_approve([user.name for user in items], ctx=rootctx, txn=txn)
        else:
            # Send account request email
            for user in items:
                self.dbenv.txncb(txn, 'email', kwargs={'to_addr':user.email, 'template':'/email/adduser.signup'})
        return items
        
    @publicmethod(admin=True, compat="getuserqueue")
    def newuser_filter(self, names=None, ctx=None, txn=None):
        if not ctx.checkadmin():
            raise PermissionsError("Only an administrator may perform this action.")
        return self.dbenv["newuser"].filter(names, ctx=ctx, txn=txn)
        
    @publicmethod(admin=True)
    def newuser_find(self, query=None, count=100, ctx=None, txn=None, **kwargs):
        if not ctx.checkadmin():
            raise PermissionsError("Only an administrator may perform this action.")
        defaultparams = ['name_first', 'name_middle', 'name_last', 'email']
        return self._find('user', query, defaultparams=defaultparams, ctx=ctx, txn=txn, **kwargs)
        # return self.dbenv["newuser"].filter(names, ctx=ctx, txn=txn)
        
    @publicmethod(write=True, admin=True, compat="approveuser")
    @ol('names')
    def newuser_approve(self, names, secret=None, ctx=None, txn=None):
        """(Admin Only) Approve account in user queue.

        Examples:

        >>> db.newuser.approve('kay')
        <User kay>

        >>> db.newuser.approve(['kay', 'matt'])
        [<User kay>, <User matt>]

        >>> db.newuser.approve('kay', secret='654067667525479cba8eb2940a3cf745de3ce608')
        <User kay>

        :param names: New user queue name(s)
        :keyword secret: User secret for self-approval
        :return: Approved User(s)
        :exception ExistingKeyError:
        :exception KeyError:
        :exception PermissionsError:
        :exception ValidationError:
        """
        if not ctx.checkadmin():
            raise PermissionsError("Only an administrator may perform this action.")
        group_defaults = emen2.db.config.get('users.group_defaults')
        autoapprove = emen2.db.config.get('users.auto_approve')

        # Get users from the new user approval queue
        newusers = self.dbenv["newuser"].gets(names, ctx=ctx, txn=txn)
        cusers = []

        # Approve the users.
        for newuser in newusers:
            emen2.db.log.security('Approving new user: %s, %s'%(newuser.name, newuser.email))

            # Delete the pending user
            self.dbenv["newuser"].delete(newuser.name, ctx=ctx, txn=txn)

            # Create the new user. This checks for uniqueness of the email address.
            # TODO: Just check the uniqueness of the email <here>.
            user = self.dbenv["user"].new(name=newuser.name, email=newuser.email, ctx=ctx, txn=txn)
            # Update the new user
            for i in ['name_first', 'name_middle', 'name_last']:
                user[i] = newuser.get(i)
            # Manually copy the password hash.
            user.data['password'] = newuser.password
            user = self.dbenv["user"]._put(user, ctx=ctx, txn=txn)

            # Create a user profile record.
            if newuser.signupinfo:            
                # TODO: This is an open security question...
                # Create the "Record" for this user
                rec = self.dbenv["record"].new(rectype='person', ctx=ctx, txn=txn)
                # Are there any child records specified...
                childrecs = newuser.signupinfo.pop('childrecs', None)
                # This gets updated with the user's signup info
                rec.update(newuser.signupinfo)
                rec.adduser(user.name, level=2)
                rec.addgroup("authenticated")
                rec = self.dbenv["record"].put(rec, ctx=ctx, txn=txn)

                # Update the User with the Record name and put again
                user.record = rec.name
                user = self.dbenv["user"].put(user, ctx=ctx, txn=txn)
                
                # Any additional profile records...
                for childrec in childrecs:
                    crec = self.record_new(rectype=childrec.get('rectype'), ctx=ctx, txn=txn)
                    crec.update(childrec)
                    crec.adduser(user.name, level=3)
                    crec = self.dbenv["record"].put(crec, ctx=ctx, txn=txn)
                    self.dbenv['record'].pclink(rec.name, crec.name, ctx=ctx, txn=txn)
                    
            cusers.append(user)

        # Send the 'account approved' emails
        for user in cusers:
            ctxt = {'name':user.name, 'displayname':user.getdisplayname()}
            template = '/email/adduser.approved'
            if autoapprove:
                template = '/email/adduser.autoapproved'
            self.dbenv.txncb(txn, 'email', kwargs={'to_addr':user.email, 'template':template, 'ctxt':ctxt})

        return self.dbenv["user"].gets(set([i.name for i in cusers]), ctx=ctx, txn=txn)

    @publicmethod(write=True, admin=True, compat="rejectuser")
    @ol('names')
    def newuser_reject(self, names, ctx=None, txn=None):
        """(Admin Only) Remove a user from the new user queue.

        Examples:

        >>> db.newuser.reject('spambot')
        set(['spambot'])

        >>> db.newuser.reject(['kay', 'spambot'])
        set(['kay', 'spambot'])

        :param names: New queue name(s) to reject
        :return: Rejected user name(s)
        :exception KeyError:
        :exception PermissionsError:
        """
        if not ctx.checkadmin():
            raise PermissionsError("Only an administrator may perform this action.")
        emails = {}
        users = self.dbenv["newuser"].gets(names, ctx=ctx, txn=txn)
        for user in users:
            emails[user.name] = user.email

        for user in users:
            emen2.db.log.security('Rejecting new user: %s, %s'%(user.name, user.email))
            self.dbenv["newuser"].delete(user.name, ctx=ctx, txn=txn)

        # Send the emails
        for name, email in emails.items():
            ctxt = {'name':name}
            self.dbenv.txncb(txn, 'email', kwargs={'to_addr':email, 'template':'/email/adduser.rejected', 'ctxt':ctxt})

        return set(emails.keys())

    ##### Group #####

    @publicmethod(compat="getgroup")
    @ol('names')
    def group_get(self, names, filt=True, ctx=None, txn=None):
        return self.dbenv["group"].gets(names, filt=filt, ctx=ctx, txn=txn)

    @publicmethod(compat="newgroup")
    def group_new(self, *args, **kwargs):
        return self.dbenv["group"].new(*args, **kwargs)

    @publicmethod(write=True, admin=True, compat="putgroup")
    @ol('items')
    def group_put(self, items, ctx=None, txn=None):
        if not ctx.checkadmin():
            raise PermissionsError("Only an administrator may perform this action.")
        return self.dbenv["group"].puts(items, ctx=ctx, txn=txn)

    @publicmethod(compat="getgroupnames")
    def group_filter(self, names=None, ctx=None, txn=None):
        return self.dbenv["group"].filter(names, ctx=ctx, txn=txn)

    @publicmethod(compat="findgroup")
    def group_find(self, query=None, count=100, ctx=None, txn=None):
        """Find a group.

        Examples:

        >>> db.group.find('admin')
        [<Group admin>, <Group readonlyadmin>]

        :keyword query: Find in Group's displayname
        :keyword count: Limit number of results
        :return: Groups
        """
        defaultparams = ['displayname']
        return self._find('group', query, defaultparams=defaultparams, ctx=ctx, txn=txn)

    ##### RecordDef #####

    @publicmethod(compat="getrecorddef")
    @ol('names')
    def recorddef_get(self, names, filt=True, ctx=None, txn=None):
        return self.dbenv["recorddef"].gets(names, filt=filt, ctx=ctx, txn=txn)
        
    @publicmethod(compat="newrecorddef")
    def recorddef_new(self, *args, **kwargs):
        return self.dbenv["recorddef"].new(*args, **kwargs)

    @publicmethod(write=True, compat="putrecorddef")
    @ol('items')
    def recorddef_put(self, items, ctx=None, txn=None):
        return self.dbenv["recorddef"].puts(items, ctx=ctx, txn=txn)

    @publicmethod(compat="getrecorddefnames")
    def recorddef_filter(self, names=None, ctx=None, txn=None):
        return self.dbenv["recorddef"].filter(names, ctx=ctx, txn=txn)

    @publicmethod(compat="findrecorddef")
    def recorddef_find(self, query=None, count=100, ctx=None, txn=None, **kwargs):
        """Find a RecordDef, by general search string, or by searching attributes.

        Examples:

        >>> db.recorddef.find('CCD')
        [<RecordDef ccd>, <RecordDef image_capture>]

        >>> db.recorddef.find(mainview='freezing apparatus')
        [<RecordDef freezing], <RecordDef vitrobot>, <RecordDef gatan_cp3>, ...]

        :keyword query: Matches any of the following:
        :keyword desc_short: ... contained in short description
        :keyword desc_long: ... contained in long description
        :keyword mainview: ... contained in mainview
        :keyword count: Limit number of results
        :return: RecordDefs
        """
        defaultparams = ['desc_short', 'desc_long', 'mainview']
        return self._find('recorddef', query, defaultparams=defaultparams, ctx=ctx, txn=txn, **kwargs)

    ##### Records #####

    @publicmethod(compat="getrecord")
    @ol('names')
    def record_get(self, names, filt=True, ctx=None, txn=None):
        return self.dbenv["record"].gets(names, filt=filt, ctx=ctx, txn=txn)

    @publicmethod(compat="newrecord")
    def record_new(self, *args, **kwargs):
        return self.dbenv["record"].new(*args, **kwargs)

    @publicmethod(write=True, compat="putrecord")
    @ol('items')
    def record_put(self, items, ctx=None, txn=None):
        return self.dbenv["record"].puts(items, ctx=ctx, txn=txn)

    @publicmethod()
    def record_filter(self, names=None, ctx=None, txn=None):
        return self.dbenv["record"].filter(names, ctx=ctx, txn=txn)

    @publicmethod()
    def record_find(self, **kwargs):
        defaultparams = ['rectype']
        return self._find('record', query, defaultparams=defaultparams, ctx=ctx, txn=txn, **kwargs)

    @publicmethod(write=True, compat="hiderecord")
    @ol('names')
    def record_hide(self, names, childaction=None, filt=True, ctx=None, txn=None):
        """Unlink and hide a record; it is still accessible to owner.
        Records are never truly deleted, just hidden.

        Examples:

        >>> db.record.hide('136')
        <Record 136, group>

        >>> db.record.hide(['136', '137'])
        [<Record 136, group>]

        >>> db.record.hide(['136', '137'], filt=False)
        PermissionsError

        >>> db.record.hide('12345', filt=False)
        KeyError

        :param name: Record name(s) to delete
        :keyword filt: Ignore failures
        :return: Hidden Record(s)
        :exception KeyError:
        :exception PermissionsError:
        """
        names = set(names)

        if childaction == 'orphaned':
            names |= self.record_findorphans(names, ctx=ctx, txn=txn)
        elif childaction == 'all':
            c = self.rel_children(names, ctx=ctx, txn=txn)
            for k,v in c.items():
                names |= v
                names.add(k)

        # self.dbenv["record"].hide(names, ctx=ctx, txn=txn)
        recs = self.dbenv["record"].gets(names, ctx=ctx, txn=txn)
        crecs = []
        for rec in recs:
            rec.setpermissions([[],[],[],[]])
            rec.setgroups([])
            children = self.dbenv['record'].children([rec.name], ctx=ctx, txn=txn)[rec.name]
            parents = self.dbenv['record'].parents([rec.name], ctx=ctx, txn=txn)[rec.name]
            if parents and children:
                rec["comments"] = "Record hidden by unlinking from parents %s and children %s"%(", ".join([unicode(x) for x in parents]), ", ".join([unicode(x) for x in children]))
            elif parents:
                rec["comments"] = "Record hidden by unlinking from parents %s"%", ".join([unicode(x) for x in parents])
            elif children:
                rec["comments"] = "Record hidden by unlinking from children %s"%", ".join([unicode(x) for x in children])
            else:
                rec["comments"] = "Record hidden"

            rec.hidden = True
            crecs.append(rec)
            print "parents/children", parents, children
            for i in children:
                self.dbenv['record'].pcunlink(rec.name, i, ctx=ctx, txn=txn)
            for i in parents:
                self.dbenv['record'].pcunlink(i, rec.name, ctx=ctx, txn=txn)

        ret = self.dbenv["record"].puts(crecs, ctx=ctx, txn=txn)

    @publicmethod(write=True, compat="putrecordvalues")
    @ol('names')
    def record_update(self, names, update, ctx=None, txn=None):
        """Convenience method to update Records.

        Examples:

        >>> db.record.update(['0','136'], {'performed_by':'ian'})
        [<Record 0, folder>, <Record 136, group>]

        >>> db.record.update(['0','136', '137'], {'performed_by':'ian'}, filt=False)
        PermissionsError

        :param names: Record name(s)
        :param update: Update Records with this dictionary
        :return: Updated Record(s)
        :exception KeyError:
        :exception PermissionsError:
        :exception ValidationError:
        """
        return self._mapput('record', names, 'update', ctx, txn, update)

    @publicmethod(compat="validaterecord")
    @ol('items')
    def record_validate(self, items, ctx=None, txn=None):
        """Check that a record will validate before committing.

        Examples:

        >>> db.record.validate([{'rectype':'folder', 'name_folder':'Test folder'}, {'rectype':'folder', 'name_folder':'Another folder'}])
        [<Record None, folder>, <Record None, folder>]

        >>> db.record.validate([<Record 499177, folder>, <Record 499178, folder>])
        [<Record 499177, folder>, <Record 499178, folder>]

        >>> db.record.validate({'rectype':'folder', 'performed_by':'unknown_user'})
        ValidationError

        >>> db.record.validate({'name':'136', 'name_folder':'No permission to edit.'})
        PermissionsError

        >>> db.record.validate({'name':'12345', 'name_folder':'Unknown record'})
        KeyError

        :param items: Record(s)
        :return: Validated Record(s)
        :exception KeyError:
        :exception PermissionsError:
        :exception ValidationError:
        """
        return self.dbenv["record"].validate(items, ctx=ctx, txn=txn)

    # These map to the normal Record methods
    @publicmethod(write=True, compat="addpermission")
    @ol('names')
    def record_adduser(self, names, users, level=0, ctx=None, txn=None):
        """Add users to a Record's permissions.

        >>> db.record.adduser('0', 'ian')
        <Record 0, folder>

        >>> db.record.adduser(['0', '136'], ['ian', 'steve'])
        [<Record 0, folder>, <Record 136, group>]

        >>> db.record.adduser(['0', '136'], ['ian', 'steve'], filt=False)
        PermissionsError

        :param names: Record name(s)
        :param users: User name(s) to add
        :keyword filt: Ignore failures
        :keyword level: Permissions level; 0=read, 1=comment, 2=write, 3=owner
        :return: Updated Record(s)
        :exception KeyError:
        :exception PermissionsError:
        :exception ValidationError:
        """
        return self._mapput('record', names, 'adduser', ctx, txn, users, level)

    @publicmethod(write=True, compat="removepermission")
    @ol('names')
    def record_removeuser(self, names, users, ctx=None, txn=None):
        """Remove users from a Record's permissions.

        Examples:

        >>> db.record.removeuser('0', 'ian')
        <Record 0, folder>

        >>> db.record.removeuser(['0', '136'], ['ian', 'steve'])
        [<Record 0, folder>, <Record 136, group>]

        >>> db.record.removeuser(['0', '136'], ['ian', 'steve'], filt=False)
        PermissionsError

        :param names: Record name(s)
        :param users: User name(s) to remove
        :keyword filt: Ignore failures
        :return: Updated Record(s)
        :exception KeyError:
        :exception PermissionsError:
        :exception ValidationError:
        """
        return self._mapput('record', names, 'removeuser', ctx, txn, users)

    @publicmethod(write=True, compat="addgroup")
    @ol('names')
    def record_addgroup(self, names, groups, ctx=None, txn=None):
        """Add groups to a Record's permissions.

        Examples:

        >>> db.record.addgroup('0', 'authenticated')
        <Record 0, folder>

        >>> db.record.addgroup(['0', '136'], 'authenticated')
        [<Record 0, folder>, <Record 136, group>]

        >>> db.record.addgroup(['0', '136'], ['anon', 'authenticated'])
        [<Record 0, folder>, <Record 136, group>]

        >>> db.record.addgroup(['0', '136'], 'authenticated', filt=False)
        PermissionsError

        :param names: Record name(s)
        :param groups: Group name(s) to add
        :keyword filt: Ignore failures
        :return: Updated Record(s)
        :exception KeyError:
        :exception PermissionsError:
        :exception ValidationError:
        """
        return self._mapput('record', names, 'addgroup', ctx, txn, groups)

    @publicmethod(write=True, compat="removegroup")
    @ol('names')
    def record_removegroup(self, names, groups, ctx=None, txn=None):
        """Remove groups from a Record's permissions.

        Examples:

        >>> db.user.removegroup('0', 'authenticated')
        <Record 0, folder>

        >>> db.user.removegroup(['0', '136'], 'authenticated')
        [<Record 0, folder>, <Record 136, group>]

        >>> db.user.removegroup(['0', '136'], ['anon', 'authenticated'])
        [<Record 0, folder>, <Record 136, group>]

        >>> db.user.removegroup(['0', '136'], 'authenticated', filt=False)
        PermissionsError

        :param names: Record name(s)
        :param groups: Group name(s)
        :keyword filt: Ignore failures
        :return: Updated Record(s)
        :exception KeyError:
        :exception PermissionsError:
        :exception ValidationError:
        """
        return self._mapput('record', names, 'removegroup', ctx, txn, groups)

    # This method is for compatibility with the web interface widget..
    @publicmethod(write=True, compat="setpermissions")
    @ol('names')
    def record_setpermissionscompat(self, names, addumask=None, addgroups=None, removeusers=None, removegroups=None, recurse=None, overwrite_users=False, overwrite_groups=False, filt=True, ctx=None, txn=None):
        """Update a Record's permissions. This method is for backwards compatibility.

        Examples:

        >>> db.record.setpermissionscompat(names=['137', '138'], addumask=[['ian'], [], [], []])

        >>> db.record.setpermissionscompat(names=['137'], recurse=-1, addumask=[['ian', 'steve'], [], [], ['wah']])

        >>> db.record.setpermissionscompat(names=['137'], recurse=-1, removegroups=['anon'], addgroups=['authenticated])

        >>> db.record.setpermissionscompat(names=['137'], recurse=-1, addgroups=['authenticated'], overwrite_groups=True)

        >>> db.record.setpermissionscompat(names=['137'], recurse=-1, addgroups=['authenticated'], overwrite_groups=True, filt=False)
        PermissionsError

        :param names: Record name(s)
        :keyword addumask: Add this permissions mask to the record's current permissions.
        :keyword addgroups: Add these groups to the records' current groups.
        :keyword removeusers: Remove these users from each record.
        :keyword removegroups: Remove these groups from each record.
        :keyword recurse: Recursion depth
        :keyword overwrite_users: Overwrite the permissions of each record to the value of addumask.
        :keyword overwrite_groups: Overwrite the groups of each record to the value of addgroups.
        :keyword filt: Ignore failures
        :return:
        :exception KeyError:
        :exception PermissionsError:
        :exception ValidationError:
        """
        recs = self.dbenv["record"].gets(names, ctx=ctx, txn=txn)
        crecs = []

        for rec in recs:
            # Get the record and children
            children = [rec]
            if recurse:
                c = self.dbenv["record"].rel([rec.name], recurse=recurse, ctx=ctx, txn=txn).get(rec.name, set())
                c = self.dbenv["record"].gets(c, ctx=ctx, txn=txn)
                children.extend(c)

            # Apply the operations
            for crec in children:
                # Filter out items we can't edit..
                if not crec.isowner() and filt:
                    continue

                if removeusers:
                    crec.removeuser(removeusers)

                if removegroups:
                    crec.removegroup(removegroups)

                if overwrite_users:
                    crec['permissions'] = addumask
                elif addumask:
                    crec.addumask(addumask)

                if overwrite_groups:
                    crec['groups'] = addgroups
                elif addgroups:
                    crec.addgroup(addgroups)

                crecs.append(crec)

        return self.dbenv["record"].puts(crecs, ctx=ctx, txn=txn)

    @publicmethod(write=True, compat="addcomment")
    @ol('names')
    def record_addcomment(self, names, comment, filt=True, ctx=None, txn=None):
        """Add comment to a record.

        Requires comment permissions on that Record.

        Examples:

        >>> db.record.addcomment('136', 'Test comment')
        <Record 136, group>

        >>> db.record.addcomment('137', 'No comment permissions!?')
        PermissionsError

        >>> db.record.addcomment('12345', 'Record does not exist')
        KeyError

        :param name: Record name(s)
        :param comment: Comment text
        :keyparam filt: Ignore failures
        :return: Updated Record(s)
        :exception KeyError:
        :exception PermissionsError:
        :exception ValidationError:
        """
        return self._mapput('record', names, 'addcomment', ctx, txn, comment)

    @publicmethod(compat="findorphans")
    def record_findorphans(self, names, root=0, keytype='record', ctx=None, txn=None):
        """Find orphaned items that would occur if names were hidden.
        
        @param name Return orphans that would result from deletion of these items
        @return Orphaned items
        """
        names = set(names)

        children = self.rel_rel(names, rel='children', tree=True, recurse=-1, ctx=ctx, txn=txn)
        allchildren = set()
        allchildren |= names
        for k,v in children.items():
            allchildren.add(k)
            allchildren |= v

        parents = self.rel_rel(allchildren, rel="parents", tree=True, ctx=ctx, txn=txn)

        # Find a path back to root for each child
        orphaned = set()
        for child in allchildren:
            visited = set()
            stack = set() | parents.get(child, set())
            while stack:
                cur = stack.pop()
                visited.add(cur)
                stack |= (parents.get(cur, set()) - names)
            if root not in visited:
                orphaned.add(child)

        return orphaned - names
        
    @publicmethod(compat="getcomments")
    @ol('names', output=False)
    def record_findcomments(self, names, filt=True, ctx=None, txn=None):
        """Get comments from Records.

        Note: This method always returns a list of items, even if only one record
            is specified, or only one comment is found.

        Examples:

        >>> db.record.findcomments('1')
        [['1', u'root', u'2010/07/19 14:43:03', u'Record marked for deletion and unlinked from parents: 270940']]

        >>> db.record.findcomments(['1', '138'])
        [['1', u'root', u'2010/07/19 14:43:03', u'Record marked...'], ['138', u'ianrees', u'2011/10/01 02:28:51', u'New comment']]

        :param names: Record name(s)
        :keyword filt: Ignore failures
        :return: A list of comments, with the Record ID as the first item@[[record name, username, time, comment], ...]
        :exception KeyError:
        :exception PermissionsError:
        """
        recs = self.dbenv["record"].gets(names, filt=filt, ctx=ctx, txn=txn)

        ret = []
        # This filters out a couple "history" types of comments
        for rec in recs:
            cp = rec.get("comments")
            if not cp:
                continue
            cp = filter(lambda x:"LOG: " not in x[2], cp)
            cp = filter(lambda x:"Validation error: " not in x[2], cp)
            for c in cp:
                ret.append([rec.name]+list(c))

        return sorted(ret, key=lambda x:x[2])
        
    @publicmethod(compat="getindexbyrectype")
    @ol('names', output=False)
    def record_findbyrectype(self, names, ctx=None, txn=None):
        """Get Record names by RecordDef.

        Note: Not currently filtered for permissions. This is not
        considered sensitive information.

        Examples:

        >>> db.record.findbyrectype('ccd')
        set(['4180', '4513', '4514', ...])

        >>> db.record.findbyrectype('image_capture*')
        set(['141', '142', '4180', ...])

        >>> db.record.findbyrectype(['scan','micrograph'])
        set(['141', '142', '262153', ...])

        :param names: RecordDef name(s)
        :keyword filt: Ignore failures
        :return: Set of Record names
        :exception KeyError: No such RecordDef
        :exception PermissionsError: Unable to access RecordDef
        """
        rds = self.dbenv['recorddef'].expand(names, ctx=ctx, txn=txn)
        ret = set()
        for i in rds:
            ret |= self.dbenv['record'].find('rectype', i, txn=txn)
        return ret

    @publicmethod(compat="findvalue")
    def record_findbyvalue(self, param, query='', choices=True, count=100, ctx=None, txn=None):
        """Find values for a parameter.

        This is mostly used for interactive UI elements: autocomplete.
        More detailed results can be returned by using db.query directly.

        Examples:

        >>> db.record.findbyvalue('name_pi')
        [['wah', 124], ['steve', 89], ['ian', 43]], ...]

        >>> db.record.findbyvalue('ccd_id', count=2)
        [['Gatan 4k', 182845], ['Gatan 10k', 48181]]

        >>> db.record.findbyvalue('tem_magnification', choices=True, count=10)
        [[10, ...], [20, ...], [60, ...], [100, ...], ...]

        :param param: Parameter to search
        :keyword query: Value to match
        :keyword choices: Include any parameter-defined choices. These will preceede other results.
        :keyword count: Limit number of results
        :return: [[matching value, count], ...]
        :exception KeyError: No such ParamDef
        """

        # Use db.plot because it returns the matched values.
        c = [[param, 'starts', query]]
        q = self.plot(c=c, ctx=ctx, txn=txn)

        # Group the values by items.
        inverted = collections.defaultdict(set)
        for rec in q['recs']:
            inverted[rec.get(param)].add(rec.get('name'))

        # Include the ParamDef choices if choices=True.
        pd = self.dbenv["paramdef"].get(param, ctx=ctx, txn=txn)
        if pd and choices:
            choices = pd.get('choices') or []
        else:
            choices = []

        # Sort by the number of items.
        keys = sorted(inverted, key=lambda x:len(inverted[x]), reverse=True)
        keys = filter(lambda x:x not in choices, keys)

        ret = []
        for key in choices + keys:
            ret.append([key, len(inverted[key])])

        if count:
            ret = ret[:count]

        return ret

    @publicmethod(compat="groupbyrectype")
    @ol('names')
    def record_groupbyrectype(self, names, filt=True, rectypes=None, ctx=None, txn=None):
        """Group Record(s) by RecordDef.

        Examples:

        >>> db.record.groupbyrectype(['136','137','138'])
        {u'project': set(['137']), u'subproject': set(['138']), u'group': set(['136'])}

        >>> db.record.groupbyrectype([<Record instance 1>, <Record instance 2>])
        {u'all_microscopes': set(['1']), u'folder': set(['2'])}

        :param names: Record name(s) or Record(s)
        :keyword filt: Ignore failures
        :keyword rectype: Filter by a list of RecordDefs (incl., recorddef*)
        :return: Dictionary of Record names by RecordDef
        :exception KeyError:
        :exception PermissionsError:
        """
        if not names:
            return {}
        names = set(names)

        # Enable filtering on rectypes
        if rectypes:
            rectypes = self.dbenv['recorddef'].expand(rectypes, ctx=ctx, txn=txn)
            
        # Allow either Record(s) or Record name(s) as input
        ret = collections.defaultdict(set)
        recnames, recs, other = emen2.utils.typepartition(names, basestring, emen2.db.dataobject.BaseDBObject)

        if len(recnames) < 1000:
            # Get the records directly
            recs.extend(self.dbenv["record"].gets(recnames, ctx=ctx, txn=txn))
        elif rectypes:
            for i in rectypes:
                ret[i] = self.dbenv['record'].find('rectype', i, txn=txn) & names
        else:
            # Filter permissions
            names = self.dbenv["record"].filter(recnames, ctx=ctx, txn=txn)
            while names:
                # get a random record's rectype
                rid = names.pop()
                rec = self.dbenv["record"]._get_data(rid, txn=txn)
                # get the set of all records with this recorddef
                ret[rec.rectype] = self.dbenv['record'].find('rectype', rec.rectype, txn=txn) & names
                # remove the results from our list since we have now classified them
                names -= ret[rec.rectype]
                # add back the initial record to the set
                ret[rec.rectype].add(rid)

        # Filter recs by rectype
        if rectypes:
            recs = [i for i in recs if i.rectype in rectypes]
        for i in recs:
            ret[i.rectype].add(i.name)

        return ret

    @publicmethod()
    def record_renderchildren(self, name, recurse=3, rectypes=None, ctx=None, txn=None):
        """(Deprecated) Convenience method used by some clients to render trees.
    
        Examples:
    
        >>> db.record.renderchildren('0', recurse=1, rectypes=["group"])
        (
            {'0': u'EMEN2', '136': u'NCMI', '358307': u'Visitors'},
            {'0': set(['136', '358307'])}
        )
    
        :param name: Record name
        :keyword recurse: Recursion depth
        :keyword rectypes: Filter by RecordDef. Can be single RecordDef or list, and use '*'
        :keyword filt: Ignore failures
        :return: (Dictionary of rendered views {Record.name:view}, Child tree dictionary)
        :exception PermissionsError:
        :exception KeyError:
        """
        recnames, paths, roots = self.record_findpaths([], root_rectypes=['group'], leaf_rectypes=['project*'], ctx=ctx, txn=txn)
        paths[name] = roots
        return recnames, paths
    
    @publicmethod()
    def record_findpaths(self, names=None, root_rectypes=None, leaf_rectypes=None, ctx=None, txn=None):
        """This is a replacement for record_renderchildren. It's still under development.
        
        Examples:
        >>> db.record_findpaths([], root_rectypes=['group'], leaf_rectypes=['project'])
        
        :keyword names: Root nodes, or ...
        :keyword root_rectypes: RecordDefs to use as root nodes
        :keyword leaf_rectypes: RecordDefs to use as leaves
        :return: recnames, paths between root nodes and leaves, root nodes
        """
        # This isn't the most efficient method, but it fulfills a needed function.
        root_rectypes = root_rectypes or ['root']
        leaf_rectypes = leaf_rectypes or []
        names = names or set()
        all_leaves = set()
        all_nodes = set()
        paths = collections.defaultdict(set)
        recnames = {}        

        if root_rectypes:
            names |= self.record_findbyrectype(root_rectypes, ctx=ctx, txn=txn)
            # filter by permissions
            names = self.dbenv['record'].filter(names, ctx=ctx, txn=txn)

        if leaf_rectypes:
            # Find all the leaf rectypes, and find all their parents.
            all_leaves = self.record_findbyrectype(leaf_rectypes, ctx=ctx, txn=txn)
            parents = self.dbenv['record'].rel(all_leaves, rel='parents', recurse=-1, ctx=ctx, txn=txn)
            parents_paths = collections.defaultdict(set)
            for k,v in parents.items():
                for i in v & names:
                    parents_paths[i].add(k)

            # All the leaves that have allowed roots
            all_leaves_found = set()
            for k,v in parents_paths.items():
                all_leaves_found |= v
            # Filter by permissions
            all_leaves_found = self.dbenv['record'].filter(all_leaves_found, ctx=ctx, txn=txn)

            # Now, reverse.
            parents2 = self.dbenv['record'].rel(all_leaves_found, rel='parents', recurse=-1, tree=True, ctx=ctx, txn=txn)
            for k,v in parents2.items():
                for v2 in v:
                    paths[v2].add(k)

        else:
            paths = self.dbenv['record'].rel(names, rel='children', recurse=-1, tree=True, ctx=ctx, txn=txn)

        for k,v in paths.items():
            all_nodes.add(k)
            all_nodes |= v                
        recnames = self.view(all_nodes, ctx=ctx, txn=txn)            

        return recnames, paths, names

    ##### Binaries #####

    @publicmethod(compat="getbinary")
    @ol('names')
    def binary_get(self, names, filt=True, ctx=None, txn=None):
        return self.dbenv["binary"].gets(names, filt=filt, ctx=ctx, txn=txn)

    @publicmethod()
    def binary_new(self, *args, **kwargs):
        return self.dbenv["binary"].new(*args, **kwargs)

    @publicmethod(write=True)
    @ol('items')
    def binary_put(self, items, ctx=None, txn=None):
        return self.dbenv["binary"].puts(items, ctx=ctx, txn=txn)

    @publicmethod(write=True)
    @ol('items')
    def binary_upload(self, items, ctx=None, txn=None):
        """Alternate binary.put() that includes a file.

        The contents of a Binary cannot be changed after uploading. The file
        size and md5 checksum will be calculated as the file is written. 
        Any attempt to change the contents raise a
        PermissionsError. Not even admin users may override this.
    
        Examples:
    
        >>> db.binary.upload({'filename':'hello.txt', 'filedata':'Hello, world', 'record':'0'})
        <Binary bdo:2011101000000>
    
        >>> db.binary.upoad({'name':'bdo:2011101000000', 'filename':'newfilename.txt'})
        <Binary bdo:2011101000000>
    
        >>> db.binary.upload({'name':'bdo:2011101000000', 'filedata':'Goodbye'})
        PermissionsError
    
        >>> db.binary.upload({'filename':'test.txt', 'fileobj':open("test.txt")})
    
        :param items: Binary(s) or Handler(s) or similar.
        :exception PermissionsError:
        :exception ValidationError:
        """
        bdos = []
        actions = []
        for item in items:
            # Get the details from the item
            newfile = False
            filedata = item.get('filedata')
            fileobj = item.get('fileobj')
            filename = item.get('filename')
            record = item.get('record')

            # Write out to temporary storage.
            # Create a new BDO if necessary.
            # if fileobj or filedata:
            if not item.get('name'):
                filesize, md5sum, newfile = emen2.db.binary.writetmp(filedata=filedata, fileobj=fileobj)
                bdo = self.dbenv["binary"].new(filename=filename, filesize=filesize, md5=md5sum, record=record, ctx=ctx, txn=txn)
                bdo = self.dbenv["binary"].put(bdo, ctx=ctx, txn=txn)
                # Make sure the filepath gets updated...
                bdo = self.dbenv["binary"].get(bdo.name, ctx=ctx, txn=txn)
                bdos.append(bdo)

            if newfile:
                actions.append([bdo, newfile, bdo.filepath])
            
        # Rename the file at the end of the txn.
        for bdo, newfile, filepath in actions:
            self.dbenv.txncb(txn, 'rename', [newfile, filepath])
            self.dbenv.txncb(txn, 'thumbnail', [bdo])
            
        return bdos

    @publicmethod()
    def binary_filter(self, names=None, ctx=None, txn=None):
        return self.dbenv["binary"].filter(names, ctx=ctx, txn=txn)

    # Warning: This can be SLOW!
    @publicmethod(compat="findbinary")
    def binary_find(self, query=None, count=100, ctx=None, txn=None, **kwargs):
        """Find a binary by filename.

        Keywords can be combined.

        Examples:

        >>> db.binary.find(filename='dm3')
        [<Binary 2011... test.dm3.gz>, <Binary 2011... test2.dm3.gz>]

        >>> db.binary.find(record='136')
        [<Binary 2011... presentation.ppt>, <Binary 2011... retreat_photo.jpg>, ...]

        :keyword query: Contained in filename, md5
        :keyword filename:
        :keyword md5:
        :keyword count: Limit number of results
        :return: Binaries
        """
        defaultparams = ['filename', 'md5']
        return self._find('binary', query, defaultparams=defaultparams, ctx=ctx, txn=txn, **kwargs)
        
    @publicmethod(write=True, compat="binaryaddreference")
    def binary_addreference(self, record, param, name, ctx=None, txn=None):
        bdo = self.dbenv["binary"].get(name, ctx=ctx, txn=txn)        
        rec = self.dbenv["record"].get(record, ctx=ctx, txn=txn)
        pd = self.dbenv["paramdef"].get(param, ctx=ctx, txn=txn)

        if pd.vartype != 'binary':
            raise KeyError, "ParamDef %s does not accept binary references"%pd.name

        if pd.iter:
            v = rec.get(pd.name) or []
            v.append(bdo.name)
        else:
            v = bdo.name

        rec[pd.name] = v
        bdo.record = rec.name

        # Commit the record
        self.dbenv["record"].put(rec, ctx=ctx, txn=txn)
        self.dbenv["binary"].put(bdo, ctx=ctx, txn=txn)

