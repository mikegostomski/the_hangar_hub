function airport_query(){

    let input = $("#airport_query_form").find("#aqf-identifier");
    let response_container = $("#airport_query_response");
    let identifier = input.val();

    if(!identifier){
        response_container.html("");
        return;
    }

    $.ajax({
        type:   "GET",
        url:    "{%url 'hub:search'%}",
        data:   {identifier: identifier},
        beforeSend:function(){
            response_container.html(getAjaxLoadImage())
        },
        success:function(data){
            response_container.html(data)
        },
        error:function(){
            response_container.html(`<div class="alert alert-danger">Airport could not be found</div>`);
        },
        complete:function(){}
    });
}