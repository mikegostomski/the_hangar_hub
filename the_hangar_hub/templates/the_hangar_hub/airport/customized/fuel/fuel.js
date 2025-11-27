function edit_fuel_prices(){
    let container = $(".fuel-prices");

    //Hide plain-text fuel prices
    container.find('.fuel-price').addClass('hidden');

    //Reveal price inputs
    container.find('.fuel-edit').removeClass('hidden');

    //Remove the edit button
    container.find(".bi-pencil-square").closest("button").remove();
}

function update_fuel_price(element) {
    let airport_id = {{airport.id}};
    let container = element.closest('.input-group');
    let input = container.find('input[type=text]');
    let attribute = input.attr('name');
    let value = input.val();
    let save_icon = container.find(".bi-floppy");
    if(save_icon.length == 0){
        save_icon = container.find(".bi-check2-circle");
    }

    $.ajax({
        type:   "POST",
        url:    "{%url 'airport:update_airport' airport.identifier%}",
        data:   {
            csrfmiddlewaretoken: '{{ csrf_token }}',
            airport_id: airport_id,
            attribute: attribute,
            value: value
        },
        beforeSend:function(){
            clearAjaxStatusClasses(container);
            input.addClass('ajax-pending');
            save_icon.removeClass("bi-check2-circle").addClass("bi-floppy").addClass("bi-spin");
        },
        success:function(data){
            clearAjaxStatusClasses(container);
            input.addClass('ajax-success');
            save_icon.removeClass("bi-floppy").addClass("bi-check2-circle");

            let price_display = input.closest(".border").find(".fuel-price");
            let price_edit = input.closest(".border").find(".fuel-edit");
            price_display.html("$" + value);
            price_display.removeClass("hidden");
            price_edit.addClass("hidden");
            
        },
        error:function(){
            clearAjaxStatusClasses(container);
            input.addClass('ajax-error');
            save_icon.removeClass("bi-floppy").removeClass("bi-check2-circle").addClass("exclamation-triangle");
        },
        complete:function(){
            save_icon.removeClass("bi-spin");
        }
    });

}

$(document).ready(function(){
    $(".fuel-edit").find("input[type=text]").keyup(function(event) {
        if (event.keyCode == 13) {
            update_fuel_price($(this));
        }
        else{
            $(this).closest('.input-group').find(".bi-check2-circle").addClass("bi-floppy").removeClass("bi-check2-circle");
        }
    });
})