import re
import os
from sets import Set
import pickle
import traceback
#import timing
import time
import random
import atexit

import cStringIO

DEBUG = 1

from emen2 import ts 
from emen2.emen2config import *


from emen2.subsystems import routing, auth

##import emen2.TwistSupport_html.html.login
#import emen2.TwistSupport_html.html.newuser
#import emen2.TwistSupport_html.html.home
##import emen2.TwistSupport_html.html.error

# Sibling Imports
#from twisted.web import server
#from twisted.web import error
#from twisted.web import resource
#from twisted.web.util import redirectTo

# Twisted Imports
from twisted.python import filepath, log, failure
from twisted.internet import defer, reactor, threads

from twisted.web.resource import Resource
from twisted.web.static import *


class UploadBatchResource(Resource):
	isLeaf = True
	
	def render(self, request):
		host=request.getClientIP()
		session=request.getSession()
		args=request.args
		path=request.postpath
		ctxid=None
		
		print "== upload request !! =="
		
		ctxid = request.getCookie("ctxid")

		print "test ctxid: %s"%ctxid

		if hasattr(session,"ctxid"):
			print "Upload ctxid: %s"%session.ctxid
			ctxid=session.ctxid
		else:
			print "No ctxid"
		
		d = threads.deferToThread(self.RenderWorker, request.postpath, request.args, ctxid=ctxid, host=host, session=session)		
		d.addCallback(self._cbRender, request)
		d.addErrback(self._ebRender, request)
		return server.NOT_DONE_YET
		
				
		
	def RenderWorker(self,path,args,ctxid=None,host=None,session=None,db=None):

		pass
			


class UploadResource(Resource):
	isLeaf = True


	def render_POST(self, request):

		# ian: ugly hack around broken twisted.web post form
		if not request.args.has_key("filename"):
			request.content.seek(0)
			content=request.content.read()
			b=re.compile("filename=\"(.+)\"")		
			filename=b.findall(content[:5000])[0]
		else:
			filename=request.args["Filename"][0]
			
		return self.render_PUT(request, filename=filename, filedata=request.args["filedata"][0])
		
			
	def render_PUT(self, request, filename=None, filedata=None):
		
				
		host = request.getClientIP()
		args = request.args
		request.postpath = filter(bool, request.postpath)		
		ctxid = request.getCookie("ctxid") or args.get('ctxid',[None])[0]		
		username = args.get('username',[''])[0]
		pw = args.get('pw',[''])[0]
		authen = auth.Authenticator(db=ts.db, host=host)
		authen.authenticate(username, pw, ctxid, host=host)
		ctxid, un = authen.get_auth_info()
		
		if filename==None:
			if args.has_key("name"):
				filename=args["name"][0].split("/")[-1].split("\\")[-1]
			else:
				filename="No_Filename_Specified"
		
		recid = int(request.postpath[0])
		param = str(args.get("param",["file_binary"])[0]).strip().lower()		
		redirect = args.get("redirect",[0])[0]

		print "\n\n=== upload request === %s, %s, filename=%s, recid=%s, param=%s"%(username, host, filename, recid, param)

		d = threads.deferToThread(self.RenderWorker, recid=recid, param=param, filename=filename, content=request.content, filedata=filedata, redirect=redirect, ctxid=ctxid, host=host)		
		d.addCallback(self._cbRender, request)
		d.addErrback(self._ebRender, request)
		return server.NOT_DONE_YET
		
		
	def RenderWorker(self, recid=None, param=None, filename=None, content=None, filedata=None, redirect=None,ctxid=None,host=None,db=None):

		rec=db.getrecord(recid,ctxid=ctxid,host=host)

		if not rec.commentable():
			raise SecurityError,"Cannot add file to record %s"%recid
		
		pd=db.getparamdef(param,ctxid=ctxid,host=host)

		###################
		# New file
		print "Get binary..."
		# fixme: use basename and splitext
		print filename
		a = db.newbinary(time.strftime("%Y/%m/%d %H:%M:%S"),filename,rec.recid,ctxid=ctxid,host=host)

		print "Writing file... %s"%a[1]

		outputStream = open(a[1], "wb")

		if filedata:
			outputStream.write(filedata)
		else:
			content.seek(0,0)
			chunk=content.read()
			while chunk:
				outputStream.write(chunk)
				chunk=content.read()
		
		outputStream.close()
			
		######################
		# Update record
		print param
		
		if pd.vartype == "binaryimage":
			rec[param] = "bdo:%s"%a[0]

		elif pd.vartype == "binary":
			v=rec.get(param, [])
			if not isinstance(v, list):
				v=[v]
			v.append("bdo:%s"%a[0])
			rec[param]=v


		else:
			raise ValueError,"Param %s does not accept attachments"%param

			
		db.putrecord(rec,ctxid=ctxid,host=host)			
			
		if redirect:
			return """<meta http-equiv="Content-Type" content="text/html; charset=UTF-8"><meta http-equiv="REFRESH" content="0; URL=/db/record/%s">"""%recid

		return str(a[0])		


	def _cbRender(self,result,request):
		request.setHeader("content-length", str(len(result)))
		request.write(result)
		request.finish()
		

	def _ebRender(self,failure,request):
		print failure
		#request.write(emen2.TwistSupport_html.html.error.error(failure))
		request.finish()	

		
	def RenderWorker_OLD(self,path,args,content,ctxid,host,db=None):

		param = "file_binary"
		if args.has_key("param"): 
			param = args["param"][0]

		if args.has_key("name"): 
			name = args["name"][0]
		else:
			user=db.checkcontext(ctxid=ctxid,host=host)[0]
			name = user + " " + time.strftime("%Y/%m/%d %H:%M:%S")


		recid = int(path[0])
		rec = db.getrecord(recid,ctxid=ctxid,host=host)
				
				
		###################################		
		# Append to file, or make new file.
		if args.has_key("append"):
			a = db.getbinary(args["append"][0],ctxid=ctxid,host=host)
			print "Appending to %s..."%a[1]
			outputStream = open(a[1], "ab")

			chunk=content.read()
			while chunk:
				outputStream.write(chunk)
				chunk=content.read()
				
			outputStream.close()
			
			return str(a[0])

		###################
		# New file
		print "Get binary..."
		# fixme: use basename and splitext
		a = db.newbinary(time.strftime("%Y/%m/%d %H:%M:%S"),name.split("/")[-1].split("\\")[-1],rec.recid,ctxid=ctxid,host=host)
		print a

		print "Writing file... %s"%a[1]
		outputStream = open(a[1], "wb")

		content.seek(0,0)
		chunk=content.read()
		while chunk:
			outputStream.write(chunk)
			chunk=content.read()
		outputStream.close()


		######################
		# Update record
		if param == "file_binary_image":
			rec[param] = "bdo:%s"%a[0]
		else:
			if not rec.has_key(param):
				rec[param] = []
			if type(rec[param]) == str:
				rec[param] = [rec[param]]
			rec[param].append("bdo:%s"%a[0])
			
		db.putrecord(rec,ctxid=ctxid,host=host)

		if args.has_key("redirect"):
			return """<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
							<meta http-equiv="REFRESH" content="0; URL=/db/record/%s?notify=3">"""%recid

		return str(a[0])