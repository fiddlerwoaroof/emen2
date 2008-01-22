#!/usr/bin/python
# This is the main server program for EMEN2
# ts contains the actual XMLRPC methods
# ts_html contains the HTML methods

import sys
import os
import glob

from emen2.emen2config import *
import g

from TwistSupport_html.public import utils
from emen2 import ts
from twisted.internet import reactor
from twisted.web import static, server
from util import templating

import emen2.TwistSupport_html.downloadresource
import emen2.TwistSupport_html.publicresource
import emen2.TwistSupport_html.uploadresource
import emen2.TwistSupport_html.webresource
import emen2.TwistSupport_html.xmlrpcresource

import TwistSupport_html.public.views
# Change this to a directory for the actual database files
ts.startup(EMEN2DBPATH)

#############################
# Ed's new view system
#############################
g.templates = templating.TemplateFactory('mako', templating.MakoTemplateEngine())
g.templates.register_template_engine('jinja', templating.JinjaTemplateEngine())
g.templates.add_template('default', 'the folder_name is ${rec["folder_name"]}')
g.templates.add_template('test', 'the folder_name is ${rec["folder_name"]}')
g.templates.add_template('test1', 'another test $@recid()')
g.templates.add_template('form','''<html><head></head><body><form action="/pub/form" method="POST">
                                                    <input type="text"  name="expression" />
                                                    <input type="text"  name="test" />
                                                    <input type="submit" /></form>
                                                ${ctxid}</body></html>''')
g.templates.add_template('qweqwe', 'qweqwe ${rec}')
g.templates.add_template('include', '''hello, ${rec['permissions']} I include qweqwe<br />    
                                                     <%include file="qweqwe" /> <br />and call a def in namespace testns<br /> <%namespace name="testns"  file="testns"  /> ${testns.myfunc(3)}''')
templates.add_template('testns', '<%def name="myfunc(x)">this is myfunc, x is ${x}</%def>')
emen2.TwistSupport_html.publicresource.PublicView.register_redirect('^/test','root', recid='2')

TEMPLATEDIR="./TwistSupport_html/templates"
for i in os.walk(TEMPLATEDIR):
	for j in i[2]:
		name,ext=os.path.splitext(os.path.basename(j))
		if ext == ".mako":
			f=open(i[0]+"/"+j)
			data=f.read()
			f.close()
			dir=i[0].replace(TEMPLATEDIR,"")
			templates.add_template("%s/%s"%(dir,name),data)


@emen2.TwistSupport_html.publicresource.PublicView.register_url('testtempl', '^/testtempl/$')
#@debug.debug_func
#@EscapeAndReturnPreformattedString
def testtempl(ctxid=None,host=None,db=None,test=None,**kwargs):
	#from mako.template import Template
	#from mako.lookup import TemplateLookup
	#mylookup = TemplateLookup(directories=['./TwistSupport_html/templates/'])
	result = templates.render_template('/pages/test3', {'title':"ok"})
	#result = Template("""hello world!""", lookup=mylookup).render()
	return result
	#mytemplate = mylookup.get_template('/test2.mako')
	#return mytemplate.render(**{'title':'ok'})
	
	

@emen2.TwistSupport_html.publicresource.PublicView.register_url('root', '^/(?P<recid>\d+)/recinfo/$')
@debug.debug_func
@EscapeAndReturnPreformattedString
def test_func(path, args, ctxid, host, db=None, info=None, recid=0):
        debug.msg(LOG_INIT, 'test_func->args::: ', info, path, args, info)
        debug( args )
        print path
        ctxid=info['ctxid']
        getrecord = partial(db.getrecord, ctxid=ctxid)
        getrecorddef = partial(db.getrecorddef, ctxid=ctxid)
        return str(getrecord(int(recid)))

@emen2.TwistSupport_html.publicresource.PublicView.register_url('root1', '^/(?P<recid>\d+)/$')
@debug.debug_func
@utils.ReturnString
def test_func1(path, args, ctxid, host, recid=0, db=None, info=None, username=None, pw=None):
        debug('pw=<<%s>>' % pw)
        debug.msg(LOG_INIT, path, info)
        getrecord = partial(db.getrecord, ctxid=ctxid)
        getrecorddef = partial(db.getrecorddef, ctxid=ctxid)
        record = debug.note_var(getrecord(int(recid)))
        recdef = getrecorddef(record.rectype)
        params = (Set(record.keys()) | Set(recdef.params.keys()))
        paramdefs = db.getparamdefs(list(params))
        
#        result1 = templates.render_template(record['template_name'] or 'default', {'rec': record})
        result1 = templates.render_template('include', {'rec': record})
        debug('the result is: %s' % result1)
        debug.msg(-1, 'render args: ', repr(record), repr(result1), repr(paramdefs), repr(db), repr(ctxid))
        preparse = renderpreparse(record, result1, paramdefs=paramdefs, db=db, ctxid=ctxid)
        return db.renderview(record,viewdef=preparse,paramdefs=paramdefs,ctxid=ctxid)

@emen2.TwistSupport_html.publicresource.PublicView.register_url('exec', '^/exec/(?P<expression>.+)/$')
@EscapeAndReturnString
def execc(path, args=(), *arg, **kwargs):
		return str(eval(kwargs.get('expression', '')))
        
@emen2.TwistSupport_html.publicresource.PublicView.register_url('exec', '^/form(/(?P<expression>.+))?/?$')
@debug.debug_func
def do_form(path, args, ctxid, host, expression='', db=None, info=None, **ignore):
        if not expression:
            return templates.render_template('form', locals())
        else:
            return str(expression)
            

######################
# End Ed's system
######################


# Setup twist server root Resources
root = static.File(EMEN2ROOT+"/tweb")
root.putChild("db",emen2.TwistSupport_html.webresource.WebResource())
root.putChild("pub",emen2.TwistSupport_html.publicresource.PublicView())
root.putChild("download",emen2.TwistSupport_html.downloadresource.DownloadResource())
root.putChild("upload",emen2.TwistSupport_html.uploadresource.UploadResource())
root.putChild("RPC2",emen2.TwistSupport_html.xmlrpcresource.XMLRPCResource())


import thread
import code
import time

def inp(banner=''):
    if not sys.stdin.closed:
        sys.stderr.write(banner)
    result = sys.stdin.read()
    if result:
        return result
    else:
        thread.interrupt_main()
        time.sleep(10000000)
        
sys.stderr.writelines(['enter statements, end them with Ctrl-D'])
thread.start_new_thread(code.interact, ('',inp,locals()))

# You can set the port to listen on...
reactor.listenTCP(EMEN2PORT, server.Site(root))
reactor.suggestThreadPoolSize(4)
reactor.run()
