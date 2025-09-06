//
//function create_invoice(el, rental_id){
//    let row = el.closest("tr");
//    console.log(`Create invoice for ${rental_id}`)
//
//    $.ajax({
//        type:   "POST",
//        url:    "{ %url 'rent:create_invoice' airport.identifier% }",
//        data:   {
//            csrfmiddlewaretoken: '{{ csrf_token }}',
//            rental_id: rental_id,
//        },
//        beforeSend:function(){
//            el.after(getAjaxLoadImage());
//            el.addClass("hidden");
//        },
//        success:function(data){
//            console.log(data)
//        },
//        error:function(){
//            el.after(getAjaxStatusFailedIcon());
//        },
//        complete:function(){
//            clearAjaxLoadImage(row);
//        }
//    });
//}

function show_subscription_form(el, rental_id){
    let row = el.closest("tr");

    $.ajax({
        type:   "GET",
        url:    "{%url 'rent:subscription_form' airport.identifier%}",
        data:   {
            rental_id: rental_id,
        },
        beforeSend:function(){
            //Remove any existing form
            $("#rent_subscribe_form").remove();
            setAjaxLoadDiv();
        },
        success:function(data){
            el.after(data);
        },
        error:function(){
            el.after(getAjaxStatusFailedIcon());
        },
        complete:function(){
            clearAjaxLoadDiv();
        }
    });
}

//function create_subscription(el, rental_id){
//    let row = el.closest("tr");
//
//
//
//    $.ajax({
//        type:   "POST",
//        url:    "{%url 'rent:create_subscription' airport.identifier%}",
//        data:   {
//            csrfmiddlewaretoken: '{{ csrf_token }}',
//            rental_id: rental_id,
//        },
//        beforeSend:function(){
//            el.after(getAjaxLoadImage());
//            el.addClass("hidden");
//        },
//        success:function(data){
//            console.log(data)
//        },
//        error:function(){
//            el.after(getAjaxStatusFailedIcon());
//        },
//        complete:function(){
//            clearAjaxLoadImage(row);
//        }
//    });
//}

function delete_draft_invoice(el, invoice_id){
    let row = el.closest("tr");
    console.log(`Delete draft invoice ${invoice_id}`)

    $.ajax({
        type:   "POST",
        url:    "{%url 'rent:delete_draft_invoice' airport.identifier%}",
        data:   {
            csrfmiddlewaretoken: '{{ csrf_token }}',
            invoice_id: invoice_id,
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