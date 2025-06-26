function request_type_changed(el){
    let container = el.closest("form").find("#er-fields");
    if(el.val()){
        container.removeClass("hidden");
        container.find("#summary").trigger("focus");
    }
    else{
        container.addClass("hidden");
    }
}

function submit_vote(button_el){
    let icon = button_el.find(".bi");
    let vote_container = button_el.closest("td");
    let vote;
    if(icon.hasClass("bi-hand-thumbs-up")){
        vote = 1;
    }
    else if(icon.hasClass("bi-hand-thumbs-down")){
        vote = -1;
    }
    else{
        console.log(icon);
    }
    $.ajax({
        type:   "POST",
        url:    '{%url "base:enhancement_vote"%}',
        data:   {
            csrfmiddlewaretoken: '{{ csrf_token }}',
            enhancement_id: button_el.data("application_id"),
            vote: vote,
        },
        beforeSend:function(){
            vote_container.html(getAjaxLoadImage());
        },
        success:function(data){
            vote_container.html(data);
        },
        error:function(){
            vote_container.html(getAjaxStatusFailedIcon());
        },
        complete:function(){}
    });
}


