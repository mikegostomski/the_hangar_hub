{% load base_taglib %}

function update_wl_priority(select_el){
    let new_priority = select_el.val();
    let application_id = select_el.data("application_id");
    $.ajax({
            type:   "POST",
            url:    '{%url "manage:change_wl_priority" request.airport.identifier%}',
            data:   {
                csrfmiddlewaretoken: '{{ csrf_token }}',
                application_id: application_id,
                new_priority: new_priority
            },
            beforeSend:function(){
                select_el.after(getAjaxLoadImage());
                select_el.addClass("hidden");
            },
            success:function(data){
                $("#waitlist-container").html(data);
            },
            error:function(){
                select_el.after(getAjaxStatusFailedIcon());
                clearAjaxLoadImage(select_el.parent())
            },
            complete:function(){
            }
        });
}

function update_wl_index(input_el){
//    if input_el.is()
    let new_index = input_el.val();
    let application_id = input_el.data("application_id");
    $.ajax({
            type:   "POST",
            url:    '{%url "manage:change_wl_index" request.airport.identifier%}',
            data:   {
                csrfmiddlewaretoken: '{{ csrf_token }}',
                application_id: application_id,
                new_index: new_index,
                restore_ind: "N"
            },
            beforeSend:function(){
                input_el.after(getAjaxLoadImage());
                input_el.addClass("hidden");
            },
            success:function(data){
                $("#waitlist-container").html(data);
            },
            error:function(){
                input_el.after(getAjaxStatusFailedIcon());
                clearAjaxLoadImage(input_el.parent())
            },
            complete:function(){
            }
        });

}