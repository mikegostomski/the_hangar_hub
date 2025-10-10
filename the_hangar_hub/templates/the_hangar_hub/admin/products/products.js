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

function set_trial_days(input_el){
    let price_id = input_el.closest(".list-group-item").data("price_id");
    let num_days = input_el.val();

    $.ajax({
        type:   "POST",
        url:    '{%url "dev:trial_days"%}',
        data:   {
            price_id: price_id,
            trial_days: num_days,
            csrfmiddlewaretoken: '{{ csrf_token }}'
        },
        beforeSend:function(){
            clearAllAjaxStatuses(input_el.parent());
            input_el.after(getAjaxLoadImage());
        },
        success:function(infotext){
            input_el.after(getAjaxSavedIcon());
        },
        error:function(ee){
            input_el.after(getAjaxStatusFailedIcon());
        },
        complete:function(){
            clearAjaxLoadImage(input_el.parent());
        }
    });
}

function update_price(input_el){
    let price_id = input_el.closest(".list-group-item").data("price_id");
    let attr = input_el.attr("name");
    let value = input_el.val();
    if(input_el.is("input[type=checkbox]")){
        value = input_el.prop("checked") ? value : ""
    }

    $.ajax({
        type:   "POST",
        url:    '{%url "dev:update_price"%}',
        data:   {
            price_id: price_id,
            attr: attr,
            value: value,
            csrfmiddlewaretoken: '{{ csrf_token }}'
        },
        beforeSend:function(){
            clearAllAjaxStatuses(input_el.parent());
            input_el.after(getAjaxLoadImage());
        },
        success:function(infotext){
            input_el.after(getAjaxSavedIcon());
        },
        error:function(ee){
            input_el.after(getAjaxStatusFailedIcon());
        },
        complete:function(){
            clearAjaxLoadImage(input_el.parent());
        }
    });
}