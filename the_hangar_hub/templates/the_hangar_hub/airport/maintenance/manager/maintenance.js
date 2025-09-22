{% load base_taglib %}

function update_priority(input_el){
    let input_container = input_el.parent();
    $.ajax({
        type:   "POST",
        url:    "{%url 'mx:update_priority' request.airport.identifier mx_request.id%}",
        data:   {
            csrfmiddlewaretoken: '{{ csrf_token }}',
            priority_code: $("#priority_code").val()
        },
        beforeSend:function(){
            clearAjaxStatusIcon(input_container);
            input_el.after(getAjaxLoadImage());
        },
        success:function(data){
            flash_success(input_el);
        },
        error:function(){
            flash_error(input_el);
        },
        complete:function(){
            clearAjaxLoadImage(input_container);
        }
    });
}


function update_status(input_el){
    let input_container = input_el.parent();
    $.ajax({
        type:   "POST",
        url:    "{%url 'mx:update_status' request.airport.identifier mx_request.id%}",
        data:   {
            csrfmiddlewaretoken: '{{ csrf_token }}',
            status_code: $("#status_code").val()
        },
        beforeSend:function(){
            clearAjaxStatusIcon(input_container);
            input_el.after(getAjaxLoadImage());
        },
        success:function(data){
            flash_success(input_el);
        },
        error:function(){
            flash_error(input_el);
        },
        complete:function(){
            clearAjaxLoadImage(input_container);
        }
    });
}


function make_public(comment_id, btn_el){
    {%js_confirm icon="bi-eye" title="Change Visibility"  onconfirm="_update_visibility(comment_id, btn_el, 'P');"%}
        Are you sure you want to make this comment public?
    {%end_js_confirm%}
}
function make_private(comment_id, btn_el){
    {%js_confirm icon="bi-eye-slash" title="Change Visibility"  onconfirm="_update_visibility(comment_id, btn_el, 'I');"%}
        Are you sure you want to make this an internal comment?
    {%end_js_confirm%}
}
function _update_visibility(comment_id, btn_el, visibility_code){
    let comment_container = $("#comments-container");
    let btn_container = btn_el.parent();
    $.ajax({
        type:   "POST",
        url:    "{%url 'mx:comment_visibility' request.airport.identifier%}",
        data:   {
            csrfmiddlewaretoken: '{{ csrf_token }}',
            comment_id: comment_id,
            visibility_code: visibility_code
        },
        beforeSend:function(){
            btn_container.html(getAjaxLoadImage());
        },
        success:function(data){
            comment_container.html(data);
        },
        error:function(){
            btn_container.html(getAjaxSaveFailedIcon());
        },
        complete:function(){}
    });
}