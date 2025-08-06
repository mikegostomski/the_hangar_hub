
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