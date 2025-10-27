function delete_entry(el){
    let container = el.closest(".list-group-item");
    let entry_id = container.data("entry_id");

    $.ajax({
        type:   "POST",
        url:    '{%url 'airport:blog_delete' airport.identifier%}',
        data:   {
            csrfmiddlewaretoken: '{{ csrf_token }}',
            entry_id:entry_id,
        },
        beforeSend:function(){
            el.after(getAjaxLoadImage());
            el.addClass("hidden");
        },
        success:function(data){
            container.remove();
        },
        error:function(){
            el.after(getAjaxSaveFailedIcon());
        },
        complete:function(){
            clearAjaxLoadImage(el.parent());
        }
    });
}