<%namespace name="buttons" file="/buttons"  />


<%def name="page_title(user, edit)">
	<%
	un = ""
	if user.userrec.get("academic_degrees"):
		un += ", " + ", ".join(user.userrec.get("academic_degrees",[]))
	%>

	${user.displayname}${un}
	## (<a href="${ctxt.reverse('User', name=user.name)}">${user.name}</a>)
	
</%def>




<%def name="page_userrec(user, edit)">

	<form method="post" action="${ctxt.reverse('User/save', name=user.name)}">

	<table class="e2l-kv">
		<tbody>
		% if edit:
			<tr>
				<td>First name:</td>
				<td><input type="text" name="userrec.name_first" value="${user.userrec.get('name_first','')}" /></td>
			</tr>
			<tr>
				<td>Middle name:</td>
				<td><input type="text" name="userrec.name_middle" value="${user.userrec.get('name_middle','')}" /></td>
			</tr>
			<tr>
				<td>Last name:</td>
				<td><input type="text" name="userrec.name_last" value="${user.userrec.get('name_last','')}" /></td>
			</tr>
		% endif

			<tr>
				<td>Department:</td>
				<td>
				% if edit:
					<input type="text" name="userrec.department" value="${user.userrec.get('department','')}" />
				% else:
					${user.userrec.get("department",'')} 
				% endif				
				</td>
			</tr>

			<tr>
				<td>Institution:</td>
				<td>
				% if edit:
					<input type="text" name="userrec.institution" value="${user.userrec.get('institution','')}" />
				% else:
					${user.userrec.get("institution",'')}
				% endif
				</td>
			</tr>
			
			<tr>
				<td>Address:</td>
				<td>
					% if edit:
						<input type="text" name="userrec.address_street" value="${user.userrec.get('address_street','')}" />
					% else:
						${user.userrec.get("address_street")}			
					% endif
					<br />

				% if edit:
					<input type="text" name="userrec.address_street2" value="${user.userrec.get('address_street2','')}" />
				% else:
					${user.userrec.get("address_street2")}
				% endif
				<br />

				% if edit:
					<input type="text" name="userrec.address_city" value="${user.userrec.get('address_city','')}" /> <span class="e2l-small">(City)</span><br />
					<input type="text" name="userrec.address_state" value="${user.userrec.get('address_state','')}" /> <span class="e2l-small">(State)</span><br />
					<input type="text" name="userrec.address_zipcode" value="${user.userrec.get('address_zipcode','')}" /> <span class="e2l-small">(Zip)</span><br />
					<input type="text" name="userrec.country" value="${user.userrec.get('country','')}" /> <span class="e2l-small">(Country)</span>
				% else:
					${user.userrec.get("address_city",'')} ${user.userrec.get("address_state",'')}, ${user.userrec.get("address_zipcode",'')} ${user.userrec.get("country",'')}			
				% endif
				</td>
			</tr>
	
			<tr>
				<td>Email:</td>
				<td>
				<a href="mailto:${user.email}">${user.email}</a>
				% if edit:
					&nbsp;&nbsp;&nbsp;<span class="e2l-small">(Set email below)</span>
				% endif
			</tr>

			<tr>
				<td>Phone:</td>
				<td>
				% if edit:
					<input type="text" name="userrec.phone_voice" value="${user.userrec.get('phone_voice','')}" />			
				% else:
					${user.userrec.get("phone_voice",'')}
				% endif
				</td>
			</tr>
			
			<tr>
				<td>Web:</td>
				<td>
				% if edit:
					<input type="text" name="userrec.uri" value="${user.userrec.get('uri','')}" />
				% else:
					${user.userrec.get('uri','')}		
				% endif
				</td>
			</tr>

		</tbody>
	</table>

	% if edit:
		${buttons.save('Save profile')}
	% endif	

	</form>

</%def>




<%def name="page_email(user, edit)">
	<form method="post" action="${EMEN2WEBROOT}/auth/email/change/">
	
	<input type="hidden" name="name" value="${user.name or ''}" />

	<table class="e2l-kv">
		<tbody>
			<tr>
				<td>Current password:</td>
				<td><input type="password" name="opw" value="" /> <span class="e2l-small">(required to change email)</span></td>
			</tr>
			</tr>
				<td>New email:</td>
				<td><input type="text" name="email" value="${user.get('email','')}" /></td>
			</tr>
		</tbody>
	</table>

	${buttons.save('Change email')}

	</form>
</%def>



<%def name="page_password(user, edit)">
	<form action="${EMEN2WEBROOT}/auth/password/change/" method="post">

		<input type="hidden" name="location" value="${ctxt.reverse('User/save', name=user.name)}" />
		<input type="hidden" name="name" value="${user.name or ''}" />

		<table class="e2l-kv">
			<tbody>
				<tr>
					<td>Current password:</td>
					<td><input type="password" name="opw" /></td>
				</tr>
				<tr>
					<td>New password:</td>
					<td><input type="password" name="on1" /></td>
				</tr>
				<tr>
					<td>Confirm new password:</td>
					<td><input type="password" name="on2" /></td>
				</tr>
			</tbody>
		</table>

		${buttons.save('Change password')}

	</form>
</%def>





<%def name="page_photo(user, edit)">
	% if edit:
	
		% if user.userrec.get('person_photo'):
			<% pf_url = EMEN2WEBROOT + "/download/" + user.userrec.get('person_photo') + "/" + user.name %>
			<a href="${pf_url}"><img src="${pf_url}.jpg?size=small" alt="profile photo" /></a>
		% else:
			<div>No Photo</div>
		% endif

		<form method="post" enctype="multipart/form-data" action="${EMEN2WEBROOT}/upload/${user.userrec.get('name')}/">

			<input type="hidden" value="${ctxt.reverse('User/save', name=user.name, action='save')}" name="Location" class="e2l-hide" />
			<input type="hidden" value="person_photo" name="param" />


			<table class="e2l-kv">
				<tbody>
					<tr>
						<td>Select a new photo:</td>
						<td><input type="file" name="filedata"/></td>
					</tr>
				</tbody>
			</table>

			${buttons.save('Upload photo')}

		</form>

	% else:
		% if user.userrec.get('person_photo'):

			<% pf_url = EMEN2WEBROOT + "/download/" + user.userrec.get('person_photo') + "/" + user.name %>
			<a href="${pf_url}"><img src="${pf_url}.jpg?size=small" alt="profile photo" /></a>

		% else:

			<div>No Photo</div>

		% endif
	
	% endif
	
</%def>




<%def name="page_groups(user, edit)">
	## Fix me.
</%def>





<%def name="page_history(user, edit)">
	<p>Created: ${user.userrec.get("creationtime")}</p>
	<p>Modified: ${user.userrec.get("modifytime")}</p>
</%def>



<%def name="page_status(user, edit)">
	<form method="post" action="${ctxt.reverse('User/save', name=user.name, action='save')}">
		<input type="radio" name="user.disabled" value="0" ${['checked="checked"',''][user.disabled]}> Enabled <br />
		<input type="radio" name="user.disabled" value="1" ${['','checked="checked"'][user.disabled]}> Disabled
		${buttons.save('Set account status')}
	</form>
</%def>



<%def name="page_privacy(user, edit)">
	Who may view your account information:
			
	<form method="post" action="${ctxt.reverse('User/save', name=user.name, action='save')}">
		<input type="radio" name="user.privacy" value="0" ${['checked="checked"','',''][user.privacy]}> Public <br />
		<input type="radio" name="user.privacy" value="1" ${['','checked="checked"',''][user.privacy]}> Only authenticated users<br />
		<input type="radio" name="user.privacy" value="2" ${['','','checked="checked"'][user.privacy]}> Private<br />
		${buttons.save('Set privacy level')}
	</form>		
</%def>



<%def name="userqueue(queue,abridge)">

		<%
		sorted_users = sorted(queue.keys())
		if abridge:
			sorted_users = sorted_users[:10]
		%>

		% if not abridge:
			<p><span id="admin_userqueue_count">${len(queue)}</span> Users in Queue</p>
		% endif

		% if abridge:
			% if len(queue) > 10:
				<p>Showing 1-10 of ${len(queue)} unapproved users. <a href="${EMEN2WEBROOT}/approveuser/">Show All</a></p>
			% else:
				## <p><a href="${EMEN2WEBROOT}/approveuser/">View full form</a></p>
				
			% endif
		% endif

		<form method="post" action="javascript:return false">




		<table class="admin_userqueue_table" cellspacing="0" cellpadding="0" width="100%" >
			<tr>
				<th>Yes</th>
				<th>No</th>
				<th>Account Name</th>
				<th>Display Name</th>
				<th>Email</th>
				<th>Phone</th>
			</tr>
			
			% for sh,i in enumerate(sorted_users):
			
				<%
					if sh%2: sh='s'
					else:	sh=""
					if not hasattr(queue[i],"signupinfo"):
						queue[i].signupinfo={}
				%>
			
				<tr class="userqueue_${i} ${sh}">
					<td><input type="radio" value="true" name="${i}" /></td>
					<td><input type="radio" value="false" name="${i}" /></td>
					<td><a href="">${i}</a></td>
					<td>${queue[i].signupinfo.get("name_first","")} ${queue[i].signupinfo.get("name_middle","")} ${queue[i].signupinfo.get("name_last","")}</td>
					<td>${queue[i]["email"]}</td>
					<td>${queue[i].signupinfo.get("phone_voice")}</td>
				</tr>

				<tr class="userqueue_${i} ${sh}">
					<td />
					<td />
					<td />
					<td colspan="3">
						Info: 
						% for key in set(queue[i].signupinfo.keys()) - set(["name_first","name_middle","name_last","email","phone_voice","comments"]):
							% if queue[i].signupinfo.get(key) != None:
								${queue[i].signupinfo.get(key)}, 
							% endif
						% endfor

						<br />
						Reason: ${queue[i].signupinfo.get("comments",'')}
						
					</td>

				</tr>



			% endfor
			
		</table>
		
		<div class="e2l-controls" id="ext_save">
			${buttons.spinner(false)}
			<input type="button" value="Accept / Reject Users" onclick="javascript:admin_approveuser_form(this);return false" />
		</div>	



		</form>

</%def>


<% import jsonrpc.jsonutil %>

<%def name="userlist(users, sortby='name_last', reverse=False, admin=False)">

<%
if sortby == "name":
	sortkey = lambda x:x.name
elif sortby == "email":
	sortkey = lambda x:x.email
elif sortby == "domain":
	sortkey = lambda x:x.get('email','').partition("@")[2]
else:	
	sortkey = lambda x:x.userrec.get(sortby,'').lower()

users_sorted = sorted(users, key=sortkey, reverse=reverse)
%>

	<form name="form_admin_userlist">

	<table cellpadding="0" cellspacing="0" class="admin_userlist" width="100%" >

	<tr>

		% if admin:
			<th><a href="${EMEN2WEBROOT}/admin/users/?sortby=disabled">Active</a></th>
			<th><a href="${EMEN2WEBROOT}/admin/users/?sortby=disabled&reverse=1">Disabled</a></th>
		% endif
		
		<th><a href="${EMEN2WEBROOT}/admin/users/?sortby=name">Account Name</a></th>
		<th><a href="${EMEN2WEBROOT}/admin/users/?sortby=name_last">Name</a></th>
		<th><a href="${EMEN2WEBROOT}/admin/users/?sortby=email">Email</a> (<a href="${EMEN2WEBROOT}/admin/users/?sortby=domain">sort by domain</a>)</th>
		<th><a href="${EMEN2WEBROOT}/admin/users/?sortby=phone_voice">Phone<a></th>
	</tr>

	% for sh, user in enumerate(users_sorted):
		
		<tr ${['','class="s"'][sh%2]}>

			% if admin:
				% if not user.disabled:
					<td><input type="radio" name="${user.name}" checked="1" value="0" /></td>
					<td><input type="radio" name="${user.name}" value="1" /></td>			
				% else:
					<td><input type="radio" name="${user.name}" value="0" /></td>
					<td><input type="radio" name="${user.name}" checked="1" value="1" /></td>			
				% endif
			% endif

			<td><a href="${EMEN2WEBROOT}/user/${user.name}/edit/">${user.name}</a></td>
			<td>${user.displayname}</td>
			<td>${user.userrec.get('email','')}</td>
			<td>${user.userrec.get('phone_voice','')}</td>

		</tr>
	% endfor
	
	</table>
	
	<input type="button" value="Change Enabled/Disabled State" onclick="javascript:admin_userstate_form(this);return false" />
	
	</form>

</%def>
