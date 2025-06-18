function save_changes(){
    var form = $("#application-form");
    $.ajax({
        type: "POST",
        url: "{%url 'apply:save' application.id%}",
        data: form.serialize(),
        success: function(data){}
    });

}