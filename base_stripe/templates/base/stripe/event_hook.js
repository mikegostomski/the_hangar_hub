{% load base_taglib %}

function react_to_stripe_webhooks(){
    let status_container = $("#footer-indicators-container");
    let stripe_spinner = `{%icon bi-stripe bi-spin%}`;
    let stripe_error = `{%icon bi-stripe text-danger%}`
    $.ajax({
        type:   "POST",
        url:    '{%url 'stripe:webhook_reaction'%}',
        data:   {
            csrfmiddlewaretoken: '{{ csrf_token }}'
        },
        beforeSend:function(){
            status_container.find(".bi-stripe").remove();
            status_container.append(stripe_spinner);
        },
        success:function(data){
        },
        error:function(){
            status_container.append(stripe_error);
        },
        complete:function(){
            status_container.find(".bi-stripe").filter(function(){return $(this).hasClass("bi-spin");}).remove();
            clearAjaxLoadImage(status_container);
        }
    });
}

{%if is_developer or True%}
    $(document).ready(function(){
        $(".header-icons").prepend(`{%icon bi-stripe title="Process Stripe Events" onclick="react_to_stripe_webhooks()"%}`);
    });

{%endif%}