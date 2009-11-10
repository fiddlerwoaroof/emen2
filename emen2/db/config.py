import sys
import optparse
import emen2.globalns
import emen2.subsystems.debug
import yaml

defaultconfig = "config/config.yml"

g = emen2.globalns.GlobalNamespace()


class DBOptions(optparse.OptionParser):
	def __init__(self, *args, **kwargs):
		#super(DBOptions, self).__init__()		
		optparse.OptionParser.__init__(self, *args, **kwargs)
		
		self.add_option('-c', '--configfile', action='append', dest='configfile')
		self.add_option('-t', '--templatedir', action='append', dest='templatedirs')
		self.add_option('-v', '--viewdirs', action='append', dest='viewdirs')
		self.add_option('-p', '--port', action='store', dest='port')
		self.add_option('-l', '--log_level', action='store', dest='log_level')
		self.add_option('--logfile_level', action='store', dest='logfile_level')		

	def parse_args(self, *args, **kwargs):
		self._args = optparse.OptionParser.parse_args(self,  *args, **kwargs)
		self.load_config()
		
		
	def load_config(self):

		print "Loading config files: %s"%(self.values.configfile or [defaultconfig])
		
		map(g.from_yaml, self.values.configfile or [defaultconfig])

		g.TEMPLATEDIRS.extend(self.values.templatedirs or [])
		g.VIEWPATHS.extend(self.values.viewdirs or [])

		if self.values.log_level == None:
			self.values.log_level = 'LOG_INFO'
		if self.values.logfile_level == None:
			self.values.logfile_level = 'LOG_DEBUG'

		try:
			g.LOG_CRITICAL = emen2.subsystems.debug.DebugState.debugstates.LOG_CRITICAL
			g.LOG_ERR = emen2.subsystems.debug.DebugState.debugstates.LOG_ERROR
			g.LOG_WARNING = emen2.subsystems.debug.DebugState.debugstates.LOG_WARNING
			g.LOG_WEB = emen2.subsystems.debug.DebugState.debugstates.LOG_WEB
			g.LOG_INIT = emen2.subsystems.debug.DebugState.debugstates.LOG_INIT
			g.LOG_INFO = emen2.subsystems.debug.DebugState.debugstates.LOG_INFO
			g.LOG_DEBUG = emen2.subsystems.debug.DebugState.debugstates.LOG_DEBUG

			g.log = emen2.subsystems.debug.DebugState(output_level=self.values.log_level,
												logfile=file(g.LOGROOT + '/log.log', 'a', 0),
												get_state=False,
												logfile_state=self.values.logfile_level)

			g.log.add_output(['LOG_WEB'], file(g.LOGROOT + '/access.log', 'a', 0))

		except ImportError:
			raise ImportError, 'Debug not loaded!!!'

		g.refresh()

		print "g:"
		print g

#loader = DBOptions()
#loader.parse_args()