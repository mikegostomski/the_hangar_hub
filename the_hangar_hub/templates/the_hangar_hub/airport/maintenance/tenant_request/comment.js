function post_comment(btn_el){
    let comment_container = $("#comments-container");
    let btn_container = btn_el.parent();
    $.ajax({
        type:   "POST",
        url:    "{%url 'tenant:post_comment' request.airport.identifier mx_request.id%}",
        data:   {
            csrfmiddlewaretoken: '{{ csrf_token }}',
            comment: $("#new_comment").val()
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