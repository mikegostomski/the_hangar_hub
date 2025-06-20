{% load base_taglib %}

function save_changes(){
    var form = $("#application-form");
    $.ajax({
        type: "POST",
        url: "{%url 'apply:save' application.id%}",
        data: form.serialize(),
        success: function(data){}
    });

}

function delete_application(){
    {%js_confirm icon="bi-trash" title="Delete Application" onconfirm="_delete_application();"%}
        Are you sure you want to delete your application?
    {%end_js_confirm%}
}

function _delete_application(){
    document.location.href="{%url 'apply:delete' application.id%}";
}