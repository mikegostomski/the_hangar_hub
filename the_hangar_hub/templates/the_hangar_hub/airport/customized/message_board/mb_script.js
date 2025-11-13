{%load base_taglib%}

function mb_go_to_post(post_id) {
    document.getElementById("post-"+post_id).scrollIntoView({
        behavior: "smooth",   // smooth animation
        block: "start"        // aligns the top of the div to the top of the viewport
    });
}

function mb_expand(el){
    $(".popup").addClass("hidden");
    el.parent().find('.popup').removeClass('hidden');
}

function mb_reply(btn){
    let container = btn.closest(".card");
    let post_id = container.data("post_id");
    let posted_content = container.find(".posted-message").text();
    let popup = $("#mb-response-container");
    popup.find("input[name=response_to]").val(post_id);
    popup.find(".source").html(posted_content);
    popup.removeClass("hidden");
}


function mb_submit_reply(){
    var form = $("#mb_reply_form");
    $.ajax({
        type: "POST",
        url: form.attr("action"),
        data: form.serialize(),
        success: function(data){
            let old_content = $("#airport-message-board");
            old_content.addClass("hidden");
            old_content.after(data);
            old_content.remove();
        }
    });

}

function mb_flag(el){
    {%js_confirm column_class="medium" icon="bi-flag" title="Flag for Review" confirm="Flag" cancel="Cancel" onconfirm="_mb_flag(el);"%}
    Are you sure you want to flag this post for review?
    {%end_js_confirm%}
}

function _mb_flag(icon){
    let btn = icon.closest(".btn");
    let container = btn.closest(".card");
    let post_id = container.data("post_id");
    let content_container = container.find(".posted_content");
    let post_container = $("#post-" + post_id);
    let reply_container = $("#replies-" + post_id);
    $.ajax({
        type:   "POST",
        url:    "{%url 'airport:mb_flag' airport.identifier%}",
        data:   {
            csrfmiddlewaretoken: '{{ csrf_token }}',
            post_id: post_id,
            flag: "F",
        },
        beforeSend:function(){
            content_container.html(getAjaxLoadImage());
        },
        success:function(data){
                reply_container.remove();
                post_container.addClass("hidden");
                post_container.after(data);
                post_container.remove();
        },
        error:function(){
            content_container.html(getAjaxStatusFailedIcon());
        },
        complete:function(){
            clearAjaxLoadImage(container)
        }
    });
}

{%if is_airport_manager%}
    function mb_review(icon){
        let btn = icon.closest(".btn");
        let container = btn.closest(".card");
        let post_id = container.data("post_id");
        let content_container = container.find(".posted_content");
        let post_container = $("#post-" + post_id);
        let reply_container = $("#replies-" + post_id);
        $.ajax({
            type:   "POST",
            url:    "{%url 'airport:mb_flag' airport.identifier%}",
            data:   {
                csrfmiddlewaretoken: '{{ csrf_token }}',
                post_id: post_id,
                flag: "A",
            },
            beforeSend:function(){
                btn.after(getAjaxLoadImage());
                btn.addClass("hidden");
            },
            success:function(data){
                reply_container.remove();
                post_container.addClass("hidden");
                post_container.after(data);
                post_container.remove();
            },
            error:function(){
                btn.after(getAjaxStatusFailedIcon());
            },
            complete:function(){
                clearAjaxLoadImage(container)
            }
        });
    }

    function mb_delete(el){
        {%js_confirm column_class="medium" icon="bi-trash" title="Delete Post" confirm="Delete" cancel="Cancel" onconfirm="_mb_delete(el);"%}
        Are you sure you want to delete this post?
        {%end_js_confirm%}
    }
    function _mb_delete(icon){
        let btn = icon.closest(".btn");
        let container = btn.closest(".card");
        let post_id = container.data("post_id");
        let content_container = container.find(".posted_content");
        let post_container = $("#post-" + post_id);
        let reply_container = $("#replies-" + post_id);
        $.ajax({
            type:   "POST",
            url:    "{%url 'airport:mb_flag' airport.identifier%}",
            data:   {
                csrfmiddlewaretoken: '{{ csrf_token }}',
                post_id: post_id,
                flag: "D",
            },
            beforeSend:function(){
                btn.after(getAjaxLoadImage());
                btn.addClass("hidden");
            },
            success:function(data){
                reply_container.remove();
                post_container.addClass("hidden");
                post_container.after(data);
                post_container.remove();
            },
            error:function(){
                btn.after(getAjaxStatusFailedIcon());
            },
            complete:function(){
                clearAjaxLoadImage(container)
            }
        });
    }
    {%endif%}