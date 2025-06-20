{% load base_taglib %}

{%if is_manager%}
function mark_reviewed(){
    _change_status('R');
}
{%endif%}

function withdraw_application(){
    {%js_confirm icon="bi-slash-circle" title="Withdraw Application" onconfirm="_change_status('W');"%}
        Are you sure you want to withdraw your application?<br />
        <br />
        If you are on a waitlist, you may be giving up your position in the queue.
    {%end_js_confirm%}
}


function _change_status(new_status){
    $.ajax({
        type: "POST",
        url: "{%url 'apply:change_status' application.id%}",
        data: {csrfmiddlewaretoken: '{{ csrf_token }}', "new_status": new_status},
        beforeSend:function(){
            setAjaxLoadDiv();
        },
        success: function(data){
            $("#application-status-container").html("Application status has been updated to: " + data)
        },
        complete:function(){
            clearAjaxLoadDiv();
        }
    });
}