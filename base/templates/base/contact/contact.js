
function close_contact_form(){
    $('.popup').remove();
    console.log("DEBUG: 1")
    try{
        {%if new_contact and contact_id%}
            console.log("DEBUG: 2")
            $('#row-contact-new').before('<tr id="row-contact-{{contact_id}}" class="outdated"></tr>');
        {%endif%}
        {%if contact_id%}
            console.log("DEBUG: 3")
            $('.outdated').each(function(){
                refresh_contact($(this).attr('id').replace('row-contact-', ''));
            });
        {%endif%}
    }
    catch(ee){console.log("DEBUG: ee")}

}

function update_contact(el){
    let tr = el.closest('tr');
    let attribute = el.attr('name');
    let value = el.val();

    $.ajax({
        type:   "POST",
        url:    '{%url 'base:update_contact'%}',
        data:   {
            csrfmiddlewaretoken: '{{ csrf_token }}',
            attribute: attribute,
            value: value,
            {%if contact_id%}contact_id: {{contact_id}},{%endif%}
        },
        beforeSend:function(){
            clearAjaxStatusClasses(tr);
            el.addClass('ajax-pending');
        },
        success:function(data){
            clearAjaxStatusClasses(tr);
            el.addClass('ajax-success');
            $('.last-edited-contact').addClass('outdated');
        },
        error:function(){
            clearAjaxStatusClasses(tr);
            el.addClass('ajax-error');
        },
        complete:function(){
        }
    });
}