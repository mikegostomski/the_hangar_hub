
function update_airport_data(element) {
    let airport_id = {{airport.id}};
    let tr = element.closest('tr');
    let attribute = element.attr('name');
    let value = element.val();
    let status_container = tr.find('.ajax-status-container');

    $.ajax({
        type:   "POST",
        url:    "{%url 'hub:update_airport_data'%}",
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