<%! import jsonrpc.jsonutil %>
<%inherit file="/page" />
<%namespace name="buttons" file="/buttons"  />
<%namespace name="pages_user_util" file="/pages/user"  />

<%block name="js_ready">
	${parent.js_ready()}
	${buttons.tocache(group)}

	var edit = ${jsonrpc.jsonutil.encode(edit)};
	
	$('#group_members').PermissionControl({
		keytype: 'group',
		name: ${jsonrpc.jsonutil.encode(group.name)},
		edit: edit,
		embed: true
	});

	$('input[name=save]').click(function() {
		var g = emen2.caches['group'][${jsonrpc.jsonutil.encode(group.name)}];
		g["permissions"] = $('#group_members').PermissionControl('getusers');
		g["displayname"] = $('input[name=group_displayname]').val();
		g["name"] = $('input[name=group_name]').val();
		emen2.db("putgroup", [g], function(group) {
			window.location = EMEN2WEBROOT+'/group/'+group.name+'/';
		})

	});
</%block>



<h1>

	% if new:
		New Group
	% else:
		${group.get('displayname')} (${group.name})
	% endif

	% if admin and not edit:
		<span class="e2l-label"><a href="${EMEN2WEBROOT}/group/${group.name}/edit/"><img src="${EMEN2WEBROOT}/static/images/edit.png" alt="Edit" /> Edit</a></span>
	% endif

	% if new or edit:
		<div class="e2l-controls" id="ext_save">
			${buttons.spinner(false)}
			<input type="submit" value="Save" name="save">
		</div>
	% endif

</h1>

<%buttons:singlepage label='Group Info'>
	<table>
		<tr>
			<td>Group Name:</td>

			% if new:
				<td><input type="text" name="group_name" value="" /></td>
			% else:
				<td>${group.name}<input type="hidden" name="group_name" value="${group.name}" /></td>
			% endif

		</tr>

		<tr>
			<td>Display Name:</td>

			% if new:
				<td><input type="text" name="group_displayname" value="" /></td>
			% elif edit:
				<td><input type="text" name="group_displayname" value="${group.get('displayname')}" /></td>
			% else:
				<td>${group.get('displayname')}</td>
			% endif

		</tr>

		% if not new:

			<tr>
				<td>Created:</td>
				<td><time datetime="${group.creationtime}">${group.creationtime}</time></td>
			</tr>


			<tr>
				<td>Modified:</td>
				<td><time datetime="${group.modifytime}">${group.modifytime}</time></td>
			</tr>

		% endif


	</table>
</%buttons:singlepage>



<%buttons:singlepage label='Group Members'>
	<div id="group_members"></div>
</%buttons:singlepage>


