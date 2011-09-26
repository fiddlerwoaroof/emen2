<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" version="-//W3C//DTD XHTML 1.1//EN" xml:lang="en">

## Named blocks:
## => title
## => js_include
## => js_inline
## => js_ready
## => css_include
## => css_inline

<head>

	<meta http-equiv="Content-type" content="text/html; charset=utf-8" />
	<meta http-equiv="Content-Language" content="en-us" />

	<title>
		<%block name="title">
			${EMEN2DBNAME}: ${context.get('title','No Title')}
		</%block>
	</title>

	<%block name="css_include">
		<link rel="StyleSheet" type="text/css" href="${EMEN2WEBROOT}/static-${VERSION}/css/custom-theme/jquery-ui-1.8.16.custom.css" />
		<link rel="StyleSheet" type="text/css" href="${EMEN2WEBROOT}/tmpl-${VERSION}/css/base.css" />
		## <link rel="StyleSheet" type="text/css" href="${EMEN2WEBROOT}/tmpl-${VERSION}/css/style.css" />
	</%block>
	
	<style type="text/css">
		<%block name="css_inline" />
	</style>

	<%block name="js_include">
		## EMEN2 Settings
		<script type="text/javascript" src="${EMEN2WEBROOT}/tmpl-${VERSION}/js/settings.js"></script>

		## jQuery, jQuery-UI, and plugins
		<script type="text/javascript" src="${EMEN2WEBROOT}/static-${VERSION}/js/jquery/jquery.js"></script>
		<script type="text/javascript" src="${EMEN2WEBROOT}/static-${VERSION}/js/jquery/jquery-ui.js"></script>
		<script type="text/javascript" src="${EMEN2WEBROOT}/static-${VERSION}/js/jquery/jquery.json.js"></script>
		<script type="text/javascript" src="${EMEN2WEBROOT}/static-${VERSION}/js/jquery/jquery.timeago.js"></script>
		<script type="text/javascript" src="${EMEN2WEBROOT}/static-${VERSION}/js/jquery/jquery.jsonrpc.js"></script>

		## Base EMEN2 widgets
		<script type="text/javascript" src="${EMEN2WEBROOT}/tmpl-${VERSION}/js/comments.js"></script>
		<script type="text/javascript" src="${EMEN2WEBROOT}/tmpl-${VERSION}/js/edit.js"></script>
		<script type="text/javascript" src="${EMEN2WEBROOT}/tmpl-${VERSION}/js/editdefs.js"></script>
		<script type="text/javascript" src="${EMEN2WEBROOT}/tmpl-${VERSION}/js/file.js"></script>
		<script type="text/javascript" src="${EMEN2WEBROOT}/tmpl-${VERSION}/js/find.js"></script>
		<script type="text/javascript" src="${EMEN2WEBROOT}/tmpl-${VERSION}/js/permission.js"></script>
		<script type="text/javascript" src="${EMEN2WEBROOT}/tmpl-${VERSION}/js/relationship.js"></script>
		<script type="text/javascript" src="${EMEN2WEBROOT}/tmpl-${VERSION}/js/table.js"></script>
		<script type="text/javascript" src="${EMEN2WEBROOT}/tmpl-${VERSION}/js/tile.js"></script>
		<script type="text/javascript" src="${EMEN2WEBROOT}/tmpl-${VERSION}/js/calendar.js"></script>
		<script type="text/javascript" src="${EMEN2WEBROOT}/tmpl-${VERSION}/js/util.js"></script>
	</%block>

	<script type="text/javascript">
		// Global cache
		var caches = {};
		caches['user'] = {};
		caches['group'] = {};
		caches['record'] = {};
		caches['paramdef'] = {};
		caches['recorddef'] = {};
		caches['children'] = {};
		caches['parents'] = {};
		caches['displaynames'] = {};
		caches['groupnames'] = {};
		caches['recnames'] = {};	
		<%block name="js_inline" />
		$(document).ready(function() {
			<%block name="js_ready" />
		});		
	</script>

</head>

<body>

${next.body()}

</body></html>
