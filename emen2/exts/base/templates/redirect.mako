<%! import jsonrpc.jsonutil %>
<%inherit file="/page" />
<%namespace name="buttons" file="/buttons"  /> 

<%block name="meta">
    ${parent.meta()}
    % if auto:
        <meta http-equiv="refresh" content="0; url=${location}">
    % endif
</%block>

<h1>${ctxt.title}</h1>

<p>
${content}
</p>

% if showlink:
    <p>Please <a href="${location}">click here</a> to continue.</p>
% endif