from emen2.web.view import View

@View.register
class Help(View):

    @View.add_matcher(r'^/help/$')
    def main(self, **kwargs):
        self.title = "Help"
        self.template = "/pages/help"
            
