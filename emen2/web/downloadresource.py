import re
import os
import pickle
import traceback
import time
import random
import cStringIO


# Twisted Imports
from twisted.internet import threads
from twisted.python import failure, filepath
from twisted.internet import threads
from twisted.internet import defer
from twisted.web.resource import Resource
from twisted.web.static import *
import emen2.util.db_manipulation

import emen2.globalns
g = emen2.globalns.GlobalNamespace('')


##########################################
# Download Resource


class DownloadResource(Resource, File):

	isLeaf = True

	contentTypes = loadMimeTypes()

	contentEncodings = {
			".gz" : "gzip",
			".bz2": "bzip2"
			}

	type = None
	defaultType="application/octet-stream"


	def render_GET(self, request):

		host = request.getClientIP()
		args = request.args
		request.postpath = filter(bool, request.postpath)
		ctxid = request.getCookie("ctxid")

		if request.args.get("ctxid"):
			ctxid = request.args.get("ctxid",[None])[0]


		g.debug.msg("LOG_INFO", "====== downloadresource action: %s host=%s ctxid=%s"%(request.postpath, host, ctxid))

		d = threads.deferToThread(self._action, request.postpath, request.args, ctxid, host)
		d.addCallback(self._cbRender, request)
		d.addErrback(self._ebRender, request)

		return server.NOT_DONE_YET



	def _action(self, path, args, ctxid, host, db=None):
		"""thread worker to get file paths from db; hand back to resource to send """

		bids = path[0].split(",")

		db._starttxn()
		db._setcontext(ctxid,host)

		try:
			bdos = db.getbinary(bids)
		except Exception, e:
			db._aborttxn()
			raise
		else:
			db._committxn()

		return bdos, db




	def _cbRender(self, result, request):
		"""You know what you doing."""

		# ian: todo: implement working archive Producer...
		bdos = result[0]

		first_bdo = bdos.values()[0]
		bname = first_bdo[0]

		self.path = first_bdo[1]
		self.type, self.encoding = getTypeAndEncoding(bname, self.contentTypes,	self.contentEncodings, self.defaultType)
		self.alwaysCreate = False

		f = self.open()
		fsize = size = os.stat(self.path).st_size

		if self.type:
			request.setHeader('content-type', self.type)
		if self.encoding:
			request.setHeader('content-encoding', self.encoding)
		if fsize:
			request.setHeader('content-length', str(fsize))

		if request.method == 'HEAD':
			return ''

		FileTransfer(f, size, request)



	def _ebRender(self,failure,request):

		errmsg = "Unspecified Error"
		errcode = 500

		try:
			failure.raiseException()
		except IOError,e:
			errcode = 404
			errmsg = "File Not Found"
		except Exception,e:
			errmsg = str(e)


		data = g.templates.render_template("/errors/simple_error",context={"EMEN2WEBROOT":g.EMEN2WEBROOT, "errmsg":errmsg,"def_title":"Error: %s"%errcode}).encode('utf-8')
		#data = errmsg

		request.setResponseCode(errcode)
		request.setHeader("content-type", "text/html; charset=utf-8")
		request.setHeader('content-length',len(data))
		request.write(data)

		request.finish()



