///////////////// Parameter Editor /////////////////////


(function($) {
    $.widget("ui.ParamDefEditor", {
		options: {
			new: null,
			parents: null,
			ext_save: null,
		},
				
		_create: function() {
			this.pd = {};
			this.build();
		},

		build: function() {
			this.bindall();
		},

		connect_buttons: function() {
			var self=this;
			$('input[name=save]', this.options.ext_save).bind("click",function(e){self.event_save(e)});
		},

		bindall: function() {
			var self=this;
			this.connect_buttons();		
		},

		event_save: function(e) {
			this.save();
		},	

		save: function() {
			var self = this;
			this.pd = this.getvalues();
			$('.spinner', this.options.ext_save).show();
			
			var args = [this.pd];
			if (this.options.new) {
				args = [this.pd, this.options.parents];
			}

			$.jsonRPC("putparamdef", args, function(data){
				$('.spinner', self.options.ext_save).hide();
				notify_post(EMEN2WEBROOT+'/paramdef/'+self.pd.name+'/', ["Changes Saved"])
			});


		},

		getvalues: function() {
			pd={}
			pd["name"] = $("input[name='name']", this.element).val();
			pd["desc_short"] = $("input[name='desc_short']",this.element).val();
			pd["desc_long"] = $("textarea[name='desc_long']",this.element).val();
			pd["vartype"] = $("select[name='vartype']",this.element).val();
			pd["property"] = $("select[name='property']",this.element).val();
			pd["defaultunits"] = $("select[name='defaultunits']",this.element).val();
			pd["choices"] = [];

			$("input[name=choices]",this.element).each(function(){
				if ($(this).val()) {
					pd["choices"].push($(this).val());
				}
			});
			return pd
		},
							
		destroy: function() {
		},
		
		_setOption: function(option, value) {
			$.Widget.prototype._setOption.apply( this, arguments );
		}
	});
})(jQuery);



 
///////////////// Protocol Editor /////////////////////



(function($) {
    $.widget("ui.RecordDefEditor", {
		options: {
			new: null,
			parents: null,
			ext_save: null
		},
				
		_create: function() {
			this.build();
			this.rd = {};
			this.counter_new = 0;
		},
	
		
		build: function() {
			this.bindall();
			this.refreshall();
			this.getvalues();
		},
	
		connect_buttons: function() {
			var self=this;
			$('input[name=save]', this.options.ext_save).bind("click",function(e){self.event_save(e)});
		},
	
		bindall: function() {
			var self=this;
	
			this.connect_buttons();
		
			$("#button_recdefviews_new", this.element).bind("click",function(e){self.event_addview(e)});
		
			$('.page[data-tabgroup="recdefviews"]', this.element).each(function() {
				var t=$(this).attr("data-tabname");
				self.bindview(t,$(this));
			});
			
			$('input[name=typicalchld]', this.element).FindControl({mode: 'findrecorddef'});			
		
		},
	
		bindview: function(t,r) {
			var self=this;

			var oname=$('input[data-t="'+t+'"]',r);
			oname.bind("change",function(e){self.event_namechange(e)});

			var ocopy=$('select[data-t="'+t+'"]',r);
			ocopy.bind("refreshlist",self.event_copy_refresh);
			ocopy.bind("change",function(e){self.event_copy_copy(e,oname.val())});
		
			var oremove=$('.recdef_edit_action_remove[data-t="'+t+'"]',r);
			oremove.bind("click",function(e){self.event_removeview(e)});
		
			r.attr("data-t",t);
		
			var obutton=$('.button[data-tabname="'+t+'"]');
			obutton.attr("data-t",t);

		},
	
		event_namechange: function(e) {
			var t=$(e.target).attr("data-t");
			var v=$(e.target).val();

			$('.button_recdefviews[data-t="'+t+'"]').html("New View: "+v);
		
			$('[data-t="'+t+'"]').each(function(){
				$(this).attr("data-t",v);
			});
			this.refreshall();
		
		},	
	
		event_addview: function(e) {
			this.addview();
		},
	
		event_removeview: function(e) {
			var t=$(e.target).attr("data-t");
			this.removeview(t);
		},
	
		event_save: function(e) {
			this.save();
		},
	
		event_copy_refresh: function(e) {
			var t=$(e.target);
			t.empty();
			t.append('<option />');
			$("input[name^='viewkey']", this.element).each(function(){
				t.append('<option>'+$(this).val()+'</option>');
			});
		},

		event_copy_copy: function(e,d) {
			var t=$(e.target);
			this.copyview(t.val(),d);
		},	
	
	
		save: function() {
			this.rd=this.getvalues();

			var self=this;
			var args = [this.rd];
			if (this.options.new) {
				args = [this.rd, this.options.parents];
			}

			$('.spinner').show();
			$.jsonRPC("putrecorddef", args,function(data){
				$('.spinner').hide();
				notify_post(EMEN2WEBROOT+'/recorddef/'+self.rd.name+'/', ["Changes Saved"])
			});

		},	
	
		refreshall: function(e) {
			$("select[name^='viewcopy']", this.element).each(function(){$(this).trigger("refreshlist");});
		},
	
		addview: function() {

			this.counter_new+=1;
			var t='new'+this.counter_new;
			var self=this;
		
			var ol=$('<li id="button_recdefviews_'+t+'" data-t="'+t+'" class="button button_recdefviews" data-tabgroup="recdefviews" data-tabname="'+t+'">New View: '+this.counter_new+'</li>');
			ol.bind("click",function(e){switchin('recdefviews',t)});

			var p=$('<div id="page_recdefviews_'+t+'" data-t="'+t+'" class="page page_recdefviews" data-tabgroup="recdefviews" data-tabname="'+t+'" />');

			var ul=$('<ul class="recdef_edit_actions clearfix" />');
		
			var oname=$('<li>Name: <input type="text" name="viewkey_'+t+'" data-t="'+t+'" value="'+t+'" /></li>');
			var ocopy=$('<li>Copy: <select name="viewcopy_'+t+'" data-t="'+t+'" "/></li>');
			var oremove=$('<li class="recdef_edit_action_remove" data-t="'+t+'"><img src="'+EMEN2WEBROOT+'/static/images/remove_small.png" /> Remove</li>');
			ul.append(oname, ocopy, oremove);
		
			var ovalue=$('<textarea name="view_'+t+'" data-t="'+t+'" rows="30" cols="80">');

			p.append(ul,ovalue);

			$("#buttons_recdefviews ul").prepend(ol);
			$("#pages_recdefviews", this.element).append(p);

			switchin('recdefviews',t);
			this.bindview(t,p);
			this.refreshall();

		},
	
	
		removeview: function(t) {
			$('.button_recdefviews[data-t="'+t+'"]').remove();
			$('.page_recdefviews[data-t="'+t+'"]').remove();
		
			var tabname=$($('.button_recdefviews')[0]).attr("data-tabname");
			switchin('recdefviews',tabname);
		
			this.refreshall();
		},
	
	
		copyview: function(src,dest) {
			var v=$('textarea[data-t="'+src+'"]').val();
			$('textarea[data-t="'+dest+'"]').val(v);		
		},
	
	
		getvalues: function() {
			rd={}
			rd["name"]=$("input[name='name']", this.element).val();

			var prv=$("input[name='private']", this.element).attr("checked");
			if (prv) {rd["private"]=1} else {rd["private"]=0}


			rd["typicalchld"]=[];

			$("input[name^='typicalchld']", this.element).each(function(){
				if ($(this).val()) {
					rd["typicalchld"].push($(this).val());
				}
			});

			rd["desc_short"]=$("input[name='desc_short']", this.element).val();
			rd["desc_long"]=$("textarea[name='desc_long']", this.element).val();

			rd["mainview"]=$("textarea[name='view_mainview']", this.element).val();

			rd["views"]={};
			var viewroot=$('#pages_recdefviews');
			$('.page[data-tabgroup="recdefviews"]',viewroot).each(function() {
				var n=$('input[name^="viewkey_"]',this).val();
				var v=$('textarea[name^="view_"]',this).val();			
				if (n && v) {
					rd["views"][n]=v;
				}
			});

			return rd			
		},

		destroy: function() {
		},

		_setOption: function(option, value) {
			$.Widget.prototype._setOption.apply( this, arguments );
		}
	});
	
})(jQuery);
