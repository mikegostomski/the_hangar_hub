function manage_amenity(el){
    let amenity_id = 0;
    let amenity_title;
    let mode;
    let container = $("#amenities-container").parent();
    if(el.is("input[type=checkbox]")){
        amenity_id = el.val();
        mode = el.prop("checked") ? "add" : "remove";
    }
    else{
        mode = "create"
        amenity_title = $("#new_amenity").val();
    }
    $.ajax({
        type:   "POST",
        url:    '{%url 'airport:manage_amenity' airport.identifier%}',
        data:   {
            csrfmiddlewaretoken: '{{ csrf_token }}',
            mode:mode,
            amenity_id:amenity_id,
            amenity_title:amenity_title,
        },
        beforeSend:function(){
            el.after(getAjaxLoadImage());
            el.addClass("hidden");
        },
        success:function(data){
            container.html(data);
        },
        error:function(){
            el.after(getAjaxSaveFailedIcon());
        },
        complete:function(){
            clearAjaxLoadImage(el.parent());
        }
    });
}