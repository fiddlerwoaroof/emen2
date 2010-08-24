"""
primary purpose is to allow more types to be serialized by simplejson
"""

try: import json
except ImportError:
	import simplejson as json

import emen2.db.globalns
from emen2.util.decorators import make_decorator

g = emen2.db.globalns.GlobalNamespace()

@make_decorator(json.dumps)
def encode(obj, *a, **kw):
	if hasattr(obj, 'json_equivalent'): obj = obj.json_equivalent()
	outp = None
	if hasattr(obj, '__iter__'):
		if hasattr(obj, 'items'):
			outd = {}
			for k,v in obj.items():
				outd[encode.func(k)] = encode.func(v)
			outp = outd
		else:
			outl = []
			for i in obj: outl.append(encode.func(i))
			outp = outl
	else: outp = obj
	return outp

decode = json.loads
