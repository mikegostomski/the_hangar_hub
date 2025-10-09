function toggle_visibility(btn_el){
    let icon = btn_el.find(".bi");
    let new_visibility = icon.hasClass("bi-incognito");
    let price_id = btn_el.closest(".list-group-item").data("price_id");
    let label_container = btn_el.parent().find("span.label");

    $.ajax({
        type:   "POST",
        url:    '{%url "dev:price_visibility"%}',
        data:   {
            price_id: price_id,
            new_visibility: new_visibility ? "Y" : "N",
            csrfmiddlewaretoken: '{{ csrf_token }}'
        },
        beforeSend:function(){
            label_container.html(getAjaxLoadImage());
        },
        success:function(infotext){
            if(new_visibility){
                label_container.html("Displayed");
                icon.removeClass("bi-incognito").removeClass("text-muted").addClass("bi-check-circle").addClass("text-success");
            }
            else{
                label_container.html("Hidden");
                icon.removeClass("bi-check-circle").removeClass("text-success").addClass("bi-incognito").addClass("text-muted");
            }
        },
        error:function(ee){
            label_container.html(getAjaxStatusFailedIcon());
        },
        complete:function(){}
    });
}