{%if manages_this_airport%}
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


    function update_entry(el, copy_from_new_form){
        let container = el.closest(".list-group-item");
        let entry_id = container.data("entry_id");
        let popup = $("#blog-edit-container");
        $.ajax({
            type:   "POST",
            url:    "{%url 'airport:blog_update' airport.identifier%}",
            data:   {
                csrfmiddlewaretoken: '{{ csrf_token }}',
                entry_id:entry_id,
            },
            beforeSend:function(){
                el.after(getAjaxLoadImage());
                el.addClass("hidden");
            },
            success:function(data){
                popup.html(data);
                popup.removeClass("hidden");
                el.removeClass("hidden");
                if(copy_from_new_form){
                    $("#blog-title").val($("#new-title").val());
                    $("#blog-content").val($("#new-content").val());
                    $("#new-title").val("");
                    $("#new-content").val("");
                }
                prepare_wysiwyg();
            },
            error:function(){
                el.after(getAjaxStatusFailedIcon());
            },
            complete:function(){
                clearAjaxLoadImage(el.parent());
            }
        });
    }

    {%if prefill and prefill.entry_id%}
    $(document).ready(function(){
        let list_group_item = $("#lgi-" + {{prefill.entry_id}});
        update_entry(list_group_item.find(".bi-pencil-square"), true);
    });
    {%endif%}
{%endif%}

function read_more(btn_el){
    let card = btn_el.hasClass("card") ? btn_el : btn_el.closest(".card");
    let entry_id = card.data("entry_id");
    let icon = card.find(".bi-three-dots");

    $.ajax({
        type:   "GET",
        url:    "{%url 'airport:blog_popup' airport.identifier%}",
        data:   {
            entry_id:entry_id,
        },
        beforeSend:function(){
            $(".blog-popup").remove();
            icon.after(getAjaxLoadImage());
        },
        success:function(data){
            console.log(data)
            $("body").append(data);
        },
        error:function(){
            btn_el.after(getAjaxStatusFailedIcon());
        },
        complete:function(){
            clearAjaxLoadImage(card);
        }
    });
}
