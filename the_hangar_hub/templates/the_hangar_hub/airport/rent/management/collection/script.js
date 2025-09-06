function refresh_rental_status(el, rental_id){
    let td = el.closest("td");
    $.ajax({
        type:   "POST",
        url:    "{%url 'rent:refresh_rental_status_tbd' airport.identifier%}",
        data:   {
            csrfmiddlewaretoken: '{{ csrf_token }}',
            rental_id: rental_id,
        },
        beforeSend:function(){
            el.after(getAjaxLoadImage());
            el.remove();
        },
        success:function(data){
            td.html(data);
        },
        error:function(){
            td.html(getAjaxStatusFailedIcon());
        },
        complete:function(){
            clearAjaxLoadImage(td);
        }
    });

}