function approve_amenity(el){
    let row = el.closest("tr");
    let amenity_id = row.data("amenity_id");
    let attr = el.attr("name");
    let val = el.val();
    let container = el.parent();

    if(el.is("input[type=checkbox]")){
        val = el.prop("checked");
    }

    $.ajax({
        type:   "POST",
        url:    '{%url "dev:amenity_review"%}',
        data:   {
            amenity_id: amenity_id,
            attr: attr,
            val: val,
            csrfmiddlewaretoken: '{{ csrf_token }}'
        },
        beforeSend:function(){
            clearAjaxStatusClasses(container);
            el.after(getAjaxLoadImage());
            el.addClass("ajax-pending")
        },
        success:function(infotext){
            el.addClass("ajax-success")
        },
        error:function(ee){
            el.addClass("ajax-error")
        },
        complete:function(){
            clearAjaxLoadImage(container);
            el.removeClass("ajax-pending")
        }
    });
}


$(document).ready(function(){
    $("#approved-amenities").DataTable( {
        "order": [[ 2, "asc" ], [ 1, "asc" ], ],
        "pageLength": 100,
        "lengthChange": false,
        "pagingType": "full_numbers",
        "oLanguage": {
            "sEmptyTable": "No Approved Amenities"
        }
    } );

});