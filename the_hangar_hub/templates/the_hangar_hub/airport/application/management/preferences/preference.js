function when_cb_clicked(cb){
    let row = cb.closest("tr");
    if(cb.prop("checked")){
        row.find("input[type=checkbox]").not(cb).prop("checked", false);
    }
}

$(document).ready(function(){
    $("#field-table").find("input[type=checkbox]").change(function(){
        when_cb_clicked($(this));
    })
});