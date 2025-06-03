/** Proxy Functions *******************************/

//Add key-press event to input
$('#impersonation-form-input').keydown(function(e){
    if(e.keyCode === 9){
        $('#impersonation-form').submit();
    }
});

function toggle_impersonation_form(){
    let popup = $('#impersonation-form-container');
    let smokescreen = popup.closest(".smokescreen");
    let container;
    if(smokescreen.length == 1){
        container = smokescreen;
        popup.click(function(e) {
           e.stopPropagation();
        });
    }
    else{
        container = popup;
    }

    if(container.is(':visible')) {
        container.addClass('hidden');
    }
    else {
        container.removeClass('hidden');
        $('#impersonation-form-input').trigger("focus");
    }
}