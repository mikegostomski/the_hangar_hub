
function update_airport_data(element) {
    // Wait one second for when browser auto-completes after partial value entered
   setTimeout(function () {
      _update_airport_data(element)
    }, 750);

}

function _update_airport_data(element) {
    let airport_id = {{airport.id}};
    let tr = element.closest('tr');
    let attribute = element.attr('name');
    let value = element.val();
    let status_container = tr.find('.ajax-status-container');

    $.ajax({
        type:   "POST",
        url:    "{%url 'manage:update_airport' airport.identifier%}",
        data:   {
            csrfmiddlewaretoken: '{{ csrf_token }}',
            airport_id: airport_id,
            attribute: attribute,
            value: value
        },
        beforeSend:function(){
            clearAjaxStatusClasses(tr);
            element.addClass('ajax-pending');
            status_container.html(getAjaxLoadImage());
        },
        success:function(data){
            clearAjaxStatusClasses(tr);
            element.addClass('ajax-success');
            status_container.html(getAjaxSavedIcon());
            if(attribute == "identifier"){
                window.location.reload();
            }
        },
        error:function(){
            clearAjaxStatusClasses(tr);
            element.addClass('ajax-error');
            status_container.html(getAjaxStatusFailedIcon());
        },
        complete:function(){
        }
    });

}


function invite_manager() {
    let input = $("#invitee")
    let airport_id = {{airport.id}};
    let invitee = input.val();
    let container = input.closest(".input-group");
    let submit_btn = container.find(".btn");
    let btn_content = submit_btn.html()

    $.ajax({
        type:   "POST",
        url:    "{%url 'manage:add_manager' airport.identifier%}",
        data:   {
            csrfmiddlewaretoken: '{{ csrf_token }}',
            airport_id: airport_id,
            invitee: invitee
        },
        beforeSend:function(){
            clearAjaxStatusClasses(container);
            submit_btn.prop("disabled", true);
            submit_btn.html(getAjaxLoadImage());
        },
        success:function(data){
            $("#managers-container").html(data);
        },
        error:function(){
            input.addClass("ajax-error")
        },
        complete:function(){
            submit_btn.prop("disabled", false);
            submit_btn.html(btn_content);
        }
    });

}

function change_am_status(select_menu_el){
    let manager_id = select_menu_el.data("manager_id");
    let row = select_menu_el.closest("tr");

    $.ajax({
        type:   "POST",
        url:    "{%url 'manage:update_manager' airport.identifier%}",
        data:   {
            csrfmiddlewaretoken: '{{ csrf_token }}',
            manager_id: manager_id,
            new_status: select_menu_el.val(),
        },
        beforeSend:function(){
            select_menu_el.after(getAjaxLoadImage());
            select_menu_el.addClass("hidden");
        },
        success:function(data){
            $("#managers-container").html(data);
        },
        error:function(){
            select_menu_el.after(getAjaxStatusFailedIcon());
            clearAjaxLoadImage(row);
        },
        complete:function(){
        }
    });
}


function delete_hangar(el){
    let row = el.closest("tr");
    let hangar_id = row.data("hangar_id");

    $.ajax({
        type:   "POST",
        url:    "{%url 'manage:delete_hangar' airport.identifier%}",
        data:   {
            csrfmiddlewaretoken: '{{ csrf_token }}',
            hangar_id: hangar_id,
        },
        beforeSend:function(){
            el.after(getAjaxLoadImage());
            el.addClass("hidden");
        },
        success:function(data){
            row.remove()
        },
        error:function(){
            el.after(getAjaxStatusFailedIcon());
            clearAjaxLoadImage(row);
        },
        complete:function(){
        }
    });
}

function create_invoice(el, rental_id){
    let row = el.closest("tr");
    console.log(`Create invoice for ${rental_id}`)

    $.ajax({
        type:   "POST",
        url:    "{%url 'manage:create_invoice' airport.identifier%}",
        data:   {
            csrfmiddlewaretoken: '{{ csrf_token }}',
            rental_id: rental_id,
        },
        beforeSend:function(){
            el.after(getAjaxLoadImage());
            el.addClass("hidden");
        },
        success:function(data){
            console.log(data)
        },
        error:function(){
            el.after(getAjaxStatusFailedIcon());
        },
        complete:function(){
            clearAjaxLoadImage(row);
        }
    });
}

function create_subscription(el, rental_id){
    let row = el.closest("tr");
    console.log(`Create invoice for ${rental_id}`)

    $.ajax({
        type:   "POST",
        url:    "{%url 'manage:create_subscription' airport.identifier%}",
        data:   {
            csrfmiddlewaretoken: '{{ csrf_token }}',
            rental_id: rental_id,
        },
        beforeSend:function(){
            el.after(getAjaxLoadImage());
            el.addClass("hidden");
        },
        success:function(data){
            console.log(data)
        },
        error:function(){
            el.after(getAjaxStatusFailedIcon());
        },
        complete:function(){
            clearAjaxLoadImage(row);
        }
    });
}