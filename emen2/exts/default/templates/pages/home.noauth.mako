<%inherit file="/page" />

<%namespace name="login" file="/auth/login"  /> 

<h1>Welcome to ${EMEN2DBNAME}</h1>

${render_banner or ''}

${login.login()}
