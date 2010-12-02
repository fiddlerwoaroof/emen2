# $Id$

# This was getting too difficult to maintain in database.py; it is still experimental and will likely change quickly
import operator
import os
import sys
import time
import collections
import itertools
import random
import datetime

import emen2.db.config
g = emen2.db.config.g()


try:
	import matplotlib.backends.backend_agg
	import matplotlib.dates
	import matplotlib.figure
except ImportError:
	matplotlib = None
	g.log("No matplotlib; plotting will fail")




from emen2.db.vartypes import parse_datetime



# Colors to use in plot..
# based on a set from http://http://colorbrewer2.org
COLORS = [
	'#1F78B4', # light blue
	'#FB9A99', # light red
	'#B2DF8A', # light green
	'#FDBF6F', # light orange
	'#CAB2D6', # light purple
	'#A6CEE3', # dark blue
	'#E31A1C', # dark red
	'#33A02C', # dark green
	'#FF7F00', # dark orange
	'#6A3D9A' # dark purple
]

# Alt scheme:
# 0x8DD3C7; 0xFFFFB3; 0xBEBADA; 0xFB8072; 0x80B1D3; 0xFDB462; 0xB3DE69; 0xFCCDE5; 0xD9D9D9; 0xBC80BD; 



def start(xmin, binw):
	return xmin
	
	

def step(cur, binw):
	return cur + binw



def datestart(xmin, binw):
	# Generate a continuous, binned date range
	if binw == 'day':
		cur = xmin.replace(hour=0, minute=0, second=0, microsecond=0)	
	elif binw == 'month':
		cur = xmin.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
	elif binw == 'year':
		cur = xmin.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
	return cur



def datestep(cur, binw):
	if binw == 'day':
		cur += datetime.timedelta(days=1)
	elif binw == 'month':
		try: cur = cur.replace(month=cur.month+1)
		except ValueError: cur = cur.replace(year=cur.year+1, month=1)
	elif binw == 'year':
		cur = cur.replace(year=cur.year+1)
	return cur



def set_xticklabels(ax, steps):
        ax.set_xticks(range(len(steps)))
        ax.set_xticklabels(steps, size="x-small", rotation=90)



def continuous_set_xticklabels(ax, steps):
	ax.set_xticks(range(len(steps)))
	ax.set_xticklabels(steps)



def date_set_xticklabels(ax, steps):
	ax.set_xticks(range(len(steps)-1))
	ax.set_xticklabels([str(i.date()) for i in steps[:-1]], size="x-small", rotation=45)



def less(x,y):
	if x < y or y == None: return x
	return y



def greater(x,y):
	if x > y or y == None: return x
	return y
	
	

def query_invert(d):
	invert = {}
	for k,v in d.items():
		for v2 in v: invert[v2] = k
	return invert



def getplotfile(prefix=None, suffix=None, ctx=None, txn=None):
	tempfile = "%s-%s-%s.%s"%(ctx.ctxid, prefix, time.strftime("%Y.%m.%d-%H.%M.%S"), suffix)
	return os.path.join(g.paths.TMPPATH, tempfile)

	




class Plotter(object):

	def __init__(self, xparam=None, yparam=None, groupby="rectype", c=None, groupshow=None, grouporder=None, groupcolors=None, binw=None, binc=None, formats=None, xmin=None, xmax=None, ymin=None, ymax=None, width=1000, plotmode='scatter', cutoff=1, title=None, xlabel=None, ylabel=None, ctx=None, txn=None, db=None, **kwargs):
				
		# Run all the arguments through query..
		c = c or []
		cparams = [i[0] for i in c]
		if xparam not in cparams:
			c.append([xparam, "any", ""])
		if yparam != None and yparam not in cparams:
			c.append([yparam, "any", ""])
		if groupby not in cparams:
			c.append([groupby, "any", ""])


		self.q = db.query(c=c, ctx=ctx, txn=txn, **kwargs)
		if not self.q["groups"].get(groupby):
			groupby = "rectype"
			self.q["groups"][groupby] = db.groupbyrecorddef(self.q["recids"], ctx=ctx, txn=txn)

		if not formats:
			formats = ["png"]

		width = int(width)

		# Args from DB -- this is not called from a proxy, so pass ctx/txn to any new DB calls
		self.ctx = ctx
		self.txn = txn
		self.db = db
		self.kwargs = kwargs
		
		# Basic plot controls
		self.c = c
		self.xparam = xparam
		self.yparam = yparam
		self.groupby = groupby
		self.formats = formats
		self.xmin = xmin
		self.ymin = ymin
		self.xmax = xmax
		self.ymax = ymax
		self.width = width
		self.plotmode = plotmode
		self.title = ''
		self.xlabel = ''
		self.ylabel = ''
		self.binw = binw
		self.binc = binc		

		# Set group names and colors
		self.cutoff = cutoff
		
		# These will all need to be str-based due to JavaScript
		self.grouporder = grouporder or [i[0] for i in sorted(self.q['groups'][groupby].items(), reverse=True, key=lambda x:len(x[1]))]
		self.groupshow = groupshow or self.grouporder
		self.grouporder = map(str, self.grouporder)
		self.groupshow = map(str, self.groupshow)
		self.groupcolors = groupcolors or {}
		self.groupnames = {}
		self.groupcount = {}
		
		# Process groupshow, and restrict recids to this set
		newrecids = set()
		# This is less elegant than it could be due to JavaScript limitations (dict keys are strings)
		for nextcolor, (group, v) in enumerate(self.q['groups'][groupby].items()):
			# group here is the native datatype -- convert to string to check for groupshow memberships
			group = str(group)
			self.groupnames[group] = group
			self.groupcolors[group] = self.groupcolors.get(group, COLORS[nextcolor%len(COLORS)])
			self.groupcount[group] = len(v)
			if group in self.groupshow:
				newrecids |= v
		

		fig = matplotlib.figure.Figure(figsize=(self.width/100.0, self.width/100.0), dpi=100)
		canvas = matplotlib.backends.backend_agg.FigureCanvasAgg(fig)
		ax_size = [0.1, 0.1, 0.8, 0.8]
		self.ax = fig.add_axes(ax_size)


		self.plot()
		labels, handles = self.plot()
		self.labels()

		plots = {}
		if "png" in self.formats:
			pngfile = getplotfile(prefix="plot", suffix="png", ctx=ctx, txn=txn)
			fig.savefig(pngfile)
			plots["png"] = os.path.basename(pngfile)


		# We draw titles, labels, etc. in PDF graphs
		if "pdf" in self.formats:
			self.ax.set_title(self.title)
			self.ax.set_xlabel(self.xlabel)
			self.ax.set_ylabel(self.ylabel)
			fig.legend(handles, labels)
			pdffile = getplotfile(prefix="plot", suffix="pdf", ctx=ctx, txn=txn)
			fig.savefig(pdffile)
			plots["pdf"] = os.path.basename(pdffile)

		
		self.q.update({
			"recids": newrecids,
			"plots": plots,
			"xlabel": self.xlabel,
			"ylabel": self.ylabel,
			"title": self.title,
			"groupcolors": self.groupcolors,
			"groupcount": self.groupcount,
			"grouporder": self.grouporder,
			"groupshow": self.groupshow,
			"groupnames": self.groupnames,
			"formats": self.formats,
			"groupby": self.groupby,
			"xparam": self.xparam,
			"yparam": self.yparam,
			"width": self.width,
			"xmin": self.xmin,
			"xmax": self.xmax,
			"ymin": self.ymin,
			"ymax": self.ymax,
			"cutoff": self.cutoff
		})




	def labels(self):
		# Generate labels
		xpd = self.db.getparamdef(self.xparam, ctx=self.ctx, txn=self.txn)
		ypd = self.db.getparamdef(self.yparam, ctx=self.ctx, txn=self.txn)

		title = 'Test Graph'
		
		xlabel = xpd.desc_short
		if xpd.defaultunits:
			xlabel = '%s (%s)'%(xlabel, xpd.defaultunits)

		ylabel = ypd.desc_short
		if ypd.defaultunits:
			ylabel = '%s (%s)'%(ylabel, ypd.defaultunits)

		self.title = self.title or title
		self.xlabel = self.xlabel or xlabel
		self.ylabel = self.ylabel or ylabel


	def plot(self):
		return [], []
		
		
		
		
class ScatterPlot(Plotter):	

	def plot(self):
		# Ok, actual plotting is pretty simple...		
		xinvert = query_invert(self.q['groups'][self.xparam])
		yinvert = query_invert(self.q['groups'][self.yparam])

		self.ax.grid(True)
		
		handles = []
		labels = []
		nextcolor = 0
		nr = [None, None, None, None]

		# plot each group		
		for k,v in self.q['groups'][self.groupby].items():
			if not str(k) in self.groupshow:
				continue
			x = map(xinvert.get, v)
			y = map(yinvert.get, v)
			nr = [less(min(x), nr[0]), less(min(y), nr[1]), greater(max(x), nr[2]), greater(max(y), nr[3])]
			handle = self.ax.scatter(x, y, c=self.groupcolors[str(k)])
			handles.append(handle)
			labels.append(str(k))
						
		if self.xmin != None: nr[0] = float(self.xmin)
		if self.ymin != None: nr[1] = float(self.ymin)
		if self.xmax != None: nr[2] = float(self.xmax)
		if self.ymax != None: nr[3] = float(self.ymax)

		# print "ranges: %s"%nr
		self.ax.set_xlim(nr[0], nr[2])
		self.ax.set_ylim(nr[1], nr[3])

		self.xmin = nr[0]
		self.xmax = nr[2]
		self.ymin = nr[1]
		self.ymax = nr[3]

		return labels, handles






class HistPlot(Plotter):
	def labels(self):
		# Generate labels
		xpd = self.db.getparamdef(self.xparam, ctx=self.ctx, txn=self.txn)
		title = 'Test Graph'
		
		xlabel = xpd.desc_short
		if xpd.defaultunits:
			xlabel = '%s (%s)'%(xlabel, xpd.defaultunits)

		ylabel = 'Frequency'

		self.title = self.title or title
		self.xlabel = self.xlabel or xlabel
		self.ylabel = self.ylabel or ylabel

	
	
	def plot(self):
		# For the histogram, we only care about the X value!!
		xinvert = query_invert(self.q['groups'][self.xparam])

		colorcount = len(COLORS)
		handles = []
		labels = []
		nextcolor = 0
		nr = [None, None, None, None]

		# ian: can't do stacked histogram yet...
		handle = self.ax.hist(xinvert.values(), 15, normed=1, facecolor='green', alpha=0.75)

		# for k,v in sorted(self.q['groups'][self.groupby].items()):
		# 	if len(v) <= self.cutoff:
		# 		continue
		# 		
		# 	self.groupnames[k] = k
		# 	self.groupcolors[k] = self.groupcolors.get(k, COLORS[nextcolor%colorcount])
		# 	nextcolor += 1
		# 
		# 	if  (self.groupshow and k not in self.groupshow):
		# 		continue
		# 		
		# 	x = map(xinvert.get, v)
		# 
		# 	# handle = self.ax.scatter(x, y, c=self.groupcolors[k])
		# 	handle = self.ax.hist(x, 15, normed=1, facecolor='green', alpha=0.75)
		# 	handles.append(handle)
		# 	labels.append(k)


		return labels, handles






class BinPlot(Plotter):

	def labels(self):
		xpd = self.db.getparamdef(self.xparam, ctx=self.ctx, txn=self.txn)
		self.title = "Test Graph"
		self.xlabel = xpd.desc_short
		self.ylabel = "Count"



	def plot(self):
		# Bar Options
		self.binw = self.binw or 'month'
		colorcount = len(COLORS)
		handles = []
		labels = []
		nextcolor = 0
		nr = [None, None, None, None]


		# Start
		# q = db.query(c=[['rectype', '==', 'image_capture*'], ['creationtime','>=','2008']])
		group = self.q['groups'].get(self.xparam)
		
		
		continuous = False
		
		_start = start
		_step = step
		_set_xticklabels = set_xticklabels

		# Switch to date mode
		xpd = self.db.getparamdef(self.xparam, ctx=self.ctx, txn=self.txn)
		if xpd.vartype in ['date', 'datetime', 'time']:
			continuous = True
			_start = datestart
			_step = datestep
			_set_xticklabels = date_set_xticklabels
			todt = {}
			for k,v in group.items():
				todt[parse_datetime(k)[0]] = v
			group = todt

		elif xpd.vartype in ["float", "int"]:
			continuous = True
			_set_xticklabels = _continuous_set_xticklabels


		#print self.q
		xk = sorted(group.keys())
		self.xmin = xk[0]
		self.xmax = xk[-1]

		cur = _start(self.xmin, self.binw)
		
		if continuous:
			steps = [cur]
			while cur < self.xmax:
				cur = _step(cur, self.binw)		
				steps.append(cur)

			hist = {}
			cur = xk.pop(0)
			for i in range(len(steps)-1):
				hist[steps[i]] = set()
				while cur != None and steps[i] < cur <= steps[i+1]:
					# print steps[i], steps[i+1], cur
					hist[steps[i]] |= group[cur]
					if xk:
						cur = xk.pop(0)
					else:
						cur = None

		else:
			steps = sorted(group.keys())
			hist = group


		# Take our timeline and break out by group
		groupedlines = collections.defaultdict(dict)
		for k,v in hist.items():
			for kg, vg in self.q['groups'].get(self.groupby).items():
				u = v & vg
				#print "Breaking out", kg, u
				if u:
					groupedlines[kg][k] = u



		# print groupedlines
		x = range(len(steps))
		xh = [0 for i in x]
		handles = []
		labels = []
		width = 1
		nextcolor = 0
		nr = [None, None, None, None]

		for k,v in groupedlines.items():

			self.groupnames[k] = k
			self.groupcolors[k] = self.groupcolors.get(k, COLORS[nextcolor%colorcount])
			nextcolor += 1

			if  (self.groupshow and k not in self.groupshow):
				continue

			nextcolor += 1
			y = [len(v.get(i, [])) for i in steps]
			handle = self.ax.bar(x, y, width, bottom=xh, color=self.groupcolors[k])
			handles.append(handle)
			labels.append(k)

			xh = map(sum, zip(xh, y))


		# self.ax.xticks([i+(width/2) for i in x], [i.date() for i in steps], rotation=90)
		# self.ax.set_xticklabels([i.date() for i in steps], rotation=90, size=small)
		_set_xticklabels(self.ax, steps)
		
		
		return handles, labels









	


		

# def plot_xy(self, x, y, xmin=None, xmax=None, ymin=None, ymax=None, width=600, xlabel=None, ylabel=None, formats=None, buffer=False, style='b', ctx=None, txn=None, **kwargs):
# 
# 	if not formats:
# 		formats = ["png"]
# 
# 	width = int(width)
# 	fig = matplotlib.figure.Figure(figsize=(width/100.0, width/100.0), dpi=100)
# 	canvas = matplotlib.backends.backend_agg.FigureCanvasAgg(fig)
# 
# 	ax_size = [0, 0, 1, 1]
# 	if xlabel or ylabel or buffer:
# 		ax_size = [0.15, 0.15, 0.8, 0.8]
# 
# 	ax = fig.add_axes(ax_size)
# 	ax.grid(True)
# 
# 	handle = ax.plot(x, y, style)
# 
# 	if xmin == None: xmin = min(x)
# 	else: xmax = float(xmax)
# 
# 	if xmax == None: xmax = max(x)
# 	else: xmax = float(xmax)
# 
# 	if ymin == None: ymin = min(y)
# 	else: ymin = float(ymin)
# 
# 	if ymax == None: ymax = max(y)
# 	else: ymax = float(ymax)
# 
# 	ax.set_xlim(xmin, xmax)
# 	ax.set_ylim(ymin, ymax)		
# 
# 	if xlabel: ax.set_xlabel(xlabel)
# 	if ylabel: ax.set_ylabel(ylabel)
# 
# 	plots = {}
# 	if "png" in formats:
# 		pngfile = self.__getplotfile(prefix="plot_xy", suffix="png", ctx=ctx, txn=txn)
# 		fig.savefig(pngfile)
# 		plots["png"] = pngfile
# 
# 
# 	q = {}
# 	q.update({
# 		"plots": plots,
# 		"xlabel": xlabel,
# 		"ylabel": ylabel,
# 		"formats": formats,
# 		"width": width,
# 		"xmin": xmin,
# 		"xmax": xmax,
# 		"ymin": ymin,
# 		"ymax": ymax
# 	})
# 
# 	return q
					
__version__ = "$Revision$".split(":")[1][:-1].strip()
