from emen2.web.view import View

@View.register
class Auth(View):

    @View.add_matcher(r'^/auth/login/$')
    def login(self, username=None, password=None, msg='', errmsg='', redirect=None, **kwargs):
        self.template = '/auth/login'
        self.title = 'Login'
        self.ctxt["username"] = username
        redirect = redirect or self.ctxt.root
        if 'auth/' in redirect:
            redirect = self.ctxt.root
        if username != None:
            ctxid = self.db.auth.login(username, password, host=self.request_host)
            self.notify('Successfully logged in.')
            self.set_header('X-Ctxid', ctxid)
            self.redirect(redirect)

    @View.add_matcher(r'^/auth/logout/$')
    def logout(self, msg='', **kwargs):
        self.template = '/auth/login'
        self.title = 'Logout'
        self.db.auth.logout()
        self.set_header('X-Ctxid', '')
        self.redirect(self.ctxt.root, content='Successfully logged out.')

    @View.add_matcher(r'^/auth/password/change/$', name='setpassword')
    def setpassword(self, **kwargs):
        self.template = '/auth/password.change'
        self.title = "Password change"
        name = kwargs.pop('name', None)
        if not name:
            try:
                name = self.db.auth.check.context()[0]
            except:
                self.notify("No name specified!", error=True)
                return

        opw = kwargs.pop("opw",None)
        on1 = kwargs.pop("on1",None)
        on2 = kwargs.pop("on2",None)
        self.ctxt['name'] = name
        if not on1 and not on2:
            pass
        elif on1 != on2:
            self.notify("New passwords did not match", error=True)
        else:
            try:
                self.db.user.setpassword(name, on1, password=opw)
                self.redirect(content="Password changed successfully.", auto=False)
            except Exception, errmsg:
                self.notify(errmsg, error=True)

    @View.add_matcher(r'^/auth/password/reset/$', name='password/reset')
    @View.add_matcher(r'^/auth/password/reset/(?P<name>[^/]*)/(?P<secret>\w+)/$', name='password/reset/confirm')
    def resetpassword(self, email=None, name=None, secret=None, newpassword=None, message=None, **kwargs):
        self.template = '/auth/password.reset'
        self.title = "Password reset"
        self.ctxt['name'] = name
        self.ctxt['email'] = email
        self.ctxt['secret'] = secret
        self.ctxt['newpassword'] = ''
        self.ctxt['message'] = message
        if name and secret and newpassword:
            try:
                self.db.user.setpassword(name, newpassword, password=None, secret=secret)
                self.redirect(content='The password for your account has been changed.', auto=False)
            except Exception, errmsg:
                self.notify(errmsg, error=True)

        elif email:
            try:
                self.db.user.resetpassword(email)
                self.redirect(content='Instructions for resetting your password have been sent to %s.'%email, auto=False)
            except Exception, errmsg:
                self.notify(errmsg, error=True)

    @View.add_matcher(r'^/auth/email/change/$', name='email/change')
    def setemail(self, **kwargs):
        self.template = '/auth/email.change'
        self.title = "Change email"

        name = kwargs.get("name") or self.db.auth.check.context()[0]
        opw = kwargs.get('opw', '')
        email = kwargs.get('email', '')

        self.ctxt['email'] = email

        if email:
            try:
                user = self.db.user.setemail(name=name, email=email, password=opw)
                if email == user.email:
                    self.redirect(content='Email address successfully updated to %s.'%user.email, auto=False)
                else:
                    self.redirect(content='A verification email has been sent to %s.'%email, auto=False)
            except Exception, errmsg:
                self.notify(errmsg, error=True)

    @View.add_matcher(r'^/auth/email/verify/(?P<name>[^/]*)/(?P<email>[^/]*)/(?P<secret>\w+)/$', name='email/verify')
    def verifyemail(self, name=None, email=None, secret=None, **kwargs):
        self.template = '/auth/email.verify'
        self.title = "Verify email"

        if name and secret:
            try:
                user = self.db.user.setemail(name=name, email=email, secret=secret)
                self.redirect(content="The email address for your account has been changed to %s"%user.email, auto=False)
            except Exception, errmsg:
                self.notify(errmsg, error=True)

