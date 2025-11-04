
function update_hangar_data(element) {
    // Wait one second for when browser auto-completes after partial value entered
   setTimeout(function () {
      _update_hangar_data(element)
    }, 500);

}

function _update_hangar_data(element) {
    let attr = element.attr("name");
    let value = element.val();
    if(element.is("input[type=checkbox]")){
        if(!element.prop("checked")){
            value = "";
        }
    }
    container = element.parent();

    $.ajax({
        type:   "POST",
        url:    "{%url 'infrastructure:update_hangar' airport.identifier hangar.code%}",
        data:   {
            csrfmiddlewaretoken: '{{ csrf_token }}',
            attr: attr,
            value: value
        },
        beforeSend:function(){
            clearAjaxStatusClasses(container);
            element.addClass('ajax-pending');
            container.append(getAjaxLoadImage());
        },
        success:function(data){
            clearAjaxStatusClasses(container);
            element.addClass('ajax-success');
        },
        error:function(){
            clearAjaxStatusClasses(container);
            element.addClass('ajax-error');
        },
        complete:function(){
            clearAjaxLoadImage(container);
        }
    });

}
