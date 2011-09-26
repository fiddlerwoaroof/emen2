<%inherit file="/page" />

<%def name="login(location='/')">
	<form action="${EMEN2WEBROOT}/auth/login/" method="post">
	    <input type="hidden" name="location" value="${EMEN2WEBROOT}${location}" />
		<table class="login" cellpadding="0" cellspacing="0">
			<tr>
				<td>Email:</td>
				<td><input tabindex="1" type="text" name="name" value="" /></td>
			</tr>
			<tr>
				<td>Password:</td>
				<td><input tabindex="2" type="password" name="pw" /></td>
			</tr>
			<tr>
				<td />
				<td><input type="submit" value="Login" /> <span class="e2l-small">(<a href="${EMEN2WEBROOT}/auth/password/reset/">Forgot Password?</a>)</span></td>
			</tr>
		</table>
	</form>

</%def>

<h1>Login</h1>

${login()}