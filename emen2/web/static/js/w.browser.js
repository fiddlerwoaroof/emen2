(function($) {
    $.widget("ui.Browser", {
		options: {
			recid: null,
			cb: function(recid){},
			keytype: "record",
			modal: true,
		},
				
		_create: function() {
			var self=this;
			this.element.click(function() {
				self.show();
			});	
			this.built = 0;
			if (this.options.show) {
				self.show();
			}
		},
	
		show: function() {
			this.build();
			this.dialog.dialog('open');
		},
			
		build: function() {
			if (this.built) {
				return
			}
			this.built = 1;
			
			var self=this;
			this.dialog = $('<div class="browser" title="Browser" />');
			this.tablearea = $('<div class="clearfix"/>');
			this.dialog.append(this.tablearea);

			this.dialog.dialog({
				width:800,
				height:600,
				autoOpen: false,
				modal: this.options.modal
			});			
			this.build_browser(this.options.recid);
		},
		
		build_browser: function(r) {
			var self = this;
			if (r == this.currentid) {
				return
			}
			this.currentid = r;
			this.tablearea.empty();
			this.tablearea.html("Loading...");
			this.tablearea.load(EMEN2WEBROOT+'/db/map/record/'+this.currentid+'/both/', {maxrecurse: 1}, 
				function(response, status, xhr){
					if (status=='error') {
						self.tablearea.append('<p>Error!</p><p>'+xhr.statusText+'</p>');
						return
					}
					self.bind_table()
				}
			);
		},
		
		bind_table: function() {
			var self = this;
			
			this.header = $('<tr><th>Parents</th><th/><th><input type="text" value="'+this.currentid+'" size="6" /><input type="button" value="Select"></th><th/><th>Children</th></tr>');
			$("input:text", this.header).focus(function() {
				$("input:button", self.header).val("Go To");
			});
			$("input:button", this.header).click(function() {
				var val = $("input:text", self.header).val();
				if (val == self.currentid) {
					self.select(val);
				} else {
					self.build_browser(val);
				}
			});
			
			$("tbody", this.tablearea).prepend(this.header);
			$("a.map", this.tablearea).click(function(e){
				e.preventDefault();
				self.build_browser(parseInt($(this).attr("data-recid")));
			})
		},
		
		select: function(val) {
			this.options.cb(val);
			this.dialog.dialog('close');
		},
		
		destroy: function() {
		},
		
		_setOption: function(option, value) {
			$.Widget.prototype._setOption.apply( this, arguments );
		}
	});
	
})(jQuery);