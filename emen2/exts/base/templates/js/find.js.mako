(function($) {

	$.widget('emen2.InfoBox', {
		options: {
			name: null,
			keytype: null,
			time: null,
			title: null,
			body: null,
			autolink: false,
			selectable: false,
			retry: true,
			input: ['radio', '', false],
			show: true,
			// events
			built: function(self) {},
			selected: function(self, e) {}
		},
		
		_create: function() {
			var self = this;
			this.retry = 0;
			this.built = 0;
			if (this.options.show) {
				this.show();
			}
		},
		
		show: function(e) {
			this.build();
		},
		
		build: function() {
			var self = this;
			if (this.built) {return}
			this.built = 1;

			var item = caches[this.options.keytype][this.options.name];
			if (!item) {
				// Can't build for items that don't exist
				if (this.options.name == null) {
					return
				}
				// We aren't going to try, or hit retry limit..
				if (!this.options.retry || this.retry > 1) {
					// console.log("not going to retry:", this.options.name, "attempt:", this.retry);
					return
				}
				// console.log("Retry to get:", this.options.name, "attempt:", this.retry);
				this.retry += 1;
				// console.log("Trying to get:", this.options.keytype, this.options.name);
				$.jsonRPC.call('get', {
					keytype: this.options.keytype,
					names: this.options.name
				}, function(item) {
					if (!item) {return}
					caches[item.keytype][item.name] = item;
					self.build();
				});
				return
			}

			// ian: todo: This could be refactored somewhat
			var title = '';
			var body = '';
			if (this.options.keytype == 'user') {
				title = $.trim(this.options.title || item.displayname) || item.name;
				body = this.options.body || item.email;
			} else if (this.options.keytype == 'group') {
				title = $.trim(item.displayname) || item.name;
				var count = 0;
				for (var i=0;i<item['permissions'].length;i++) {
					count += item['permissions'][i].length;
				}
				body = count+' members'
			} else if (this.options.keytype == 'record') {
				var recname = caches['recnames'][item.name];
				title = $.trim(recname || item.rectype);
				body = item.rectype+', '+item.name+', created: '+item.creationtime.substr(0,10);
				this.element.attr('data-rectype', item.rectype);
			} else if (this.options.keytype == 'binary') {
				title = item.filename;
				if (item.filesize) {
					title = title+' ('+item.filesize+')';
				}
				var user = item.creator;
				body = 'Created by '+user+' on '+item.creationtime;
			} else {
				title = $.trim(item.desc_short) || item.name;
				body = ''
			}
			
			// Create the link
			var link = '';
			if (this.options.autolink) {
				var link = EMEN2WEBROOT+'/'+this.options.keytype+'/'+this.options.name+'/';
			} else if (this.options.keytype == 'binary') {
				var link = EMEN2WEBROOT+'/download/'+item.name+'/'+item.filename;
			}
			
			// Set the box properties
			this.element.addClass('e2-infobox');
			this.element.attr('data-name', this.options.name);
			this.element.attr('data-keytype', this.options.keytype);

			// Box title
			var h4 = $('<h4 />');
			if (link) {
				title = '<a href="'+link+'">'+title+'</a>';
			}
			h4.append(title);
			if (this.options.time) {
				// h4.append(' @ '+this.options.time);
				// <abbr class="timeago" title="2008-07-17T09:24:17Z">July 17, 2008</abbr>
				h4.append('<time class="e2l-float-right" datetime="'+this.options.time+'">'+this.options.time+'</time>');
			}
			
			// Body body
			var p = $('<p class="e2l-small" />');
			p.append(body);
			
			// Images
			var img = $($.e2image('nophoto.png', 'Thumb', 'e2l-thumbnail'));
			if (this.options.keytype == 'user' && item.userrec['person_photo']) {
				img.attr('src', EMEN2WEBROOT+'/download/'+item.userrec['person_photo']+'/?size=thumb')
			} else if (this.options.keytype == 'binary') {
				img.attr('src', EMEN2WEBROOT+'/download/'+item.name+'/'+item.filename+'?size=thumb');
			}
			if (link) {img = $('<a href="'+link+'" />').append(img)}

			// Widget!!
			var input = ''
			if (this.options.selectable && this.options.input) {
				var type = this.options.input[0];
				var name = this.options.input[1];
				var state = this.options.input[2];
				var input = $('<input class="e2-infobox-input" type="'+type+'" name="'+name+'" />');
				input.val(this.options.name);
				input.attr('checked', state);
			}

			// Put it all together..
			this.element.append(img, input, h4, p);
			
			// Select the element
			this.element.click(function(e) {
				self.toggle(e);
				self.options.selected(self, e);
			});
			
			// $('time.e2-timeago', this.element).timeago();
			this.options.built();
		},
		
		toggle: function(e) {
			var input = $('input', this.element);
			if ($(e.target).is('input, a')) {return}
			if (input.attr('checked')) {
				input.attr('checked',null);
			} else {
				input.attr('checked','checked');		
			}
		},
		
		check: function() {
			var input = $('input', this.element);
			input.attr('checked','checked');		
		}
		
	});
	
	// Search for users, groups, parameters, etc..
    $.widget("emen2.FindControl", {
		options: {
			show: false,
			keytype: 'user',
			value: '',
			modal: true,
			vartype: null,
			minimum: 2,
			selected: function(self, value){self.element.val(value)}
		},
				
		_create: function() {
			this.built = 0;
			var self=this;
			
			this.options.keytype = $.checkopt(this, 'keytype');
			this.options.vartype = $.checkopt(this, 'vartype');
			this.options.modal = $.checkopt(this, 'modal');
			this.options.minimum = $.checkopt(this, 'minimum');
			this.options.value = $.checkopt(this, 'value');
						
			this.element.click(function(e){self.show(e)});
			if (this.options.show) {
				this.show();
			}
		},
	
		build: function() {
			if (this.built) {return}
			this.built = 1;

			var self = this;
			this.dialog = $('<div class="e2-find" />');
			if (this.options.keytype == 'user'){
				this.dialog.attr('title', 'Find User');
			} else if (this.options.keytype == 'group') {
				this.dialog.attr('title', 'Find Group');			
			} else if (this.options.keytype == 'paramdef') {
				this.dialog.attr('title', 'Find Parameter');
			} else if (this.options.keytype == 'recorddef') {
				this.dialog.attr('title', 'Find Protocol');
			} else {
				this.dialog.attr('title', 'Find '+this.options.keytype);
			}
		
			this.searchinput = $('<input type="text" />');
			this.searchinput.val(this.options.value);

			// Run a search for every key press
			// ian: todo: event queue so long-running 
			//	searches don't write over short ones
			this.searchinput.keyup(function(e) {
				var v = self.searchinput.val();
				// Enter should check for an exact match and return
				if (e.keyCode == '13') { 
					e.preventDefault();
					var check = $('[data-name='+v+']');
					if (check.length) {
						self.select(v);
					}
				}
				self.search(v);
			});

			this.statusmsg = $('<span class="e2l-float-right">No Results</span>');
			var searchbox = $('<div class="e2-find-searchbox">Search: </div>');
			searchbox.append(this.searchinput, this.statusmsg); //,this.searchbutton
			this.resultsarea = $('<div>Results</div>');
		
			this.dialog.append(searchbox, this.resultsarea);
			this.dialog.dialog({
				modal: this.options.modal,
				autoOpen: false,
				width: 750,
				height: 600
			});
			
			$('.ui-dialog-titlebar', this.dialog.dialog('widget')).append($.e2spinner());		
		},
	
		show: function(e) {
			this.build();		
			if (this.element.val() != "+") {
				// this.searchinput.val(this.element.val());
				// this.options.value = this.searchinput.val();
			}
			this.dialog.dialog('open');
			this.search(this.options.value);		
			this.searchinput.focus();
		},

		select: function(name) {
			//this.elem.val(name);
			this.options.selected(this, name);
			this.dialog.dialog('close');		
		},
	
		add: function(item) {
			var self = this;
			caches[item.keytype][item.name] = item;
			var d = $('<div />');
			d.InfoBox({
				keytype: this.options.keytype,
				name: item.name
			});
			d.click(function(e){
				self.select(item.name);
				});
			this.resultsarea.append(d);
		},
	
		search: function(q) {
			var self=this;
			if (q.length < this.options.minimum) {
				self.resultsarea.empty();
				self.statusmsg.text('Minimum '+this.options.minimum+' characters');
				return
			}
			
			$('.e2l-spinner', this.dialog.dialog('widget')).show();
			
			var query = {}
			query['query'] = q;
			if (this.options.vartype) {
				query['vartype'] = this.options.vartype;
			}
			
			// Abort any open requests
			if (this.request) {
				if (this.request.readyState != 4) {
					this.request.abort();
					this.request = null;
				}
			}
			
			// New request
			this.request = $.jsonRPC.call('find'+this.options.keytype, query, function(items) {
				$('.e2l-spinner', self.dialog.dialog('widget')).hide();				
				self.resultsarea.empty();
				var l = items.length;
				if (l==0) {
					self.statusmsg.text('No results');
					return
				}
				if (l>50) {
					self.statusmsg.text(items.length + ' results; showing 1-50');
				} else {
					self.statusmsg.text(items.length + ' results');				
				}
				items = items.slice(0,50);
				$.each(items, function() {
					self.add(this)			
				});
			})
		}
	});
	
})(jQuery);

<%!
public = True
headers = {
	'Content-Type': 'application/javascript',
	'Cache-Control': 'max-age=86400'
}
%>
