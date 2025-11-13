{%load base_taglib%}

function mb_expand(el){
    $(".popup").addClass("hidden");
    el.parent().find('.popup').removeClass('hidden');
}

function mb_reply(btn){
    let container = btn.closest(".card");
    let post_id = container.data("post_id");
    let posted_content = container.find(".posted_content").text();
    let popup = $("#mb-response-container");
    popup.find("input[name=response_to]").val(post_id);
    popup.find(".source").html(posted_content);
    popup.removeClass("hidden");
}

function mb_flag(btn){
    {%js_confirm column_class="medium" icon="bi-flag" title="Flag for Review" confirm="Flag" cancel="Cancel" onconfirm="_mb_flag(btn);"%}
    Are you sure you want to flag this post for review?
    {%end_js_confirm%}
}

function _mb_flag(btn){
    let container = btn.closest(".card");
    let post_id = container.data("post_id");
    let content_container = container.find(".posted_content");
    $.ajax({
        type:   "POST",
        url:    "{%url 'airport:mb_flag' airport.identifier%}",
        data:   {
            csrfmiddlewaretoken: '{{ csrf_token }}',
            post_id: post_id,
        },
        beforeSend:function(){
            content_container.html(getAjaxLoadImage());
        },
        success:function(data){
            content_container.html("<strong>Flagged for Review</strong>");
        },
        error:function(){
            content_container.html(getAjaxStatusFailedIcon());
        },
        complete:function(){
            clearAjaxLoadImage(container)
        }
    });
}