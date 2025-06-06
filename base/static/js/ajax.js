
/** getAjaxLoadImage()
 *
 *  Returns a spinning icon to indicate that something is happening
 */
function getAjaxLoadImage(){
    var icon = '<i class="bi bi-gear bi-pulse" aria-hidden="true" style="color:#6A7F10;"></i>';
    var aria = '<span class="visually-hidden">Loading...</span>';
    var loadImg = '<span class="ajaxLoadImage">'+icon+aria+'</span>';
    return loadImg;
}

/** clearAjaxLoadImage()
 *
 *  Clear the spinning icon set by getAjaxLoadImage()
 *
 *  Parameter "container" may be one of the following:
 *      undefined:      Remove all load images from entire page
 *      jQuery object:  Remove load images from given container object
 *      html id:        Remove load images from container with given ID
 */
function clearAjaxLoadImage(container){
    if(typeof container === 'undefined') {
        //remove all ajax load images (entire page)
        $(".ajaxLoadImage").remove();
    }
    else if(typeof container === 'object'){
        //remove ajax load image(s) contained within the given object
        container.find(".ajaxLoadImage").remove();
    }
    else{
        //remove ajax load image(s) contained within the element with the given ID
        $("#"+container).find(".ajaxLoadImage").remove();
    }
}

/** [set|clear]AjaxLoadDiv()
 *
 *  Display a spinning icon in the center of the screen to indicate a full-page loading action/event
 */
function setAjaxLoadDiv(){
    var spinner = '<span class="ajaxLoading">'+getAjaxLoadImage()+'</span>';
    var div = '<div class="ajaxLoading">'+spinner+'</div>';

    clearAjaxLoadDiv();     //Remove any existing loadDiv
    $('body').append(div);  //Append the loadDiv to the body
}
function clearAjaxLoadDiv(){
    $(".ajaxLoading").remove();
}


/** ajaxSave%Icon()
 *
 *  Get icon to represent successful or failed save action
 *
 */
function getAjaxSavedIcon(message){
    if(typeof message === 'undefined'){
        message = "Changes have been saved.";
    }
    var icon = '<i class="bi bi-floppy ajax-save-result text-success" aria-hidden="true" title="'+message+'"></i>';
    var aria = '<span class="visually-hidden">'+message+'</span>';
    return '<span role="alert">'+icon+aria+'</span>';
}
function getAjaxSaveFailedIcon(message){
    if(typeof message === 'undefined'){
        message = "Save failed.";
    }
    var icon = '<i class="bi bi-exclamation-triangle ajax-save-result text-danger" aria-hidden="true" title="'+message+'"></i>';
    var aria = '<span class="visually-hidden">'+message+'</span>';
    return '<span role="alert">'+icon+aria+'</span>';
}

/** clearAjaxSaveIcon()
 *
 *  Parameter "container" may be one of the following:
 *      undefined:      Remove all load images from entire page
 *      jQuery object:  Remove load images from given container object
 *      html id:        Remove load images from container with given ID
 */
function clearAjaxSaveIcon(container){
    if(typeof container === 'undefined') {
        //remove all visible ajax save icons
        $(".ajax-save-result").parent().remove();
    }
    else if(typeof container === 'object'){
        //remove ajax save icons(s) contained within the given object
        container.find(".ajax-save-result").parent().remove();
    }
    else{
        //remove ajax save icons(s) contained within the element with the given ID
        $("#"+container).find(".ajax-save-result").parent().remove();
    }
}

/** ajaxStatus%Icon()
 *
 *  Get icon to represent successful or failed non-save action
 *
 */
function getAjaxStatusSuccessIcon(message){
    if(typeof message === 'undefined'){
        message = "Transaction succeeded.";
    }
    var icon = '<i class="bi bi-check2-circle ajax-status-result" style="color:Green;" aria-hidden="true" title="'+message+'"></i>';
    var aria = '<span class="visually-hidden">'+message+'</span>';
    return '<span role="alert">'+icon+aria+'</span>';
}
function getAjaxStatusFailedIcon(message){
    if(typeof message === 'undefined'){
        message = "Transaction failed.";
    }
    var icon = '<i class="bi bi-exclamation-triangle ajax-status-result" style="color:Red;" aria-hidden="true" title="'+message+'"></i>';
    var aria = '<span class="visually-hidden">'+message+'</span>';
    return '<span role="alert">'+icon+aria+'</span>';
}

/** clearAjaxStatusIcon()
 *
 *  Parameter "container" may be one of the following:
 *      undefined:      Remove all load images from entire page
 *      jQuery object:  Remove load images from given container object
 *      html id:        Remove load images from container with given ID
 */
function clearAjaxStatusIcon(container){
    if(typeof container === 'undefined') {
        //remove all visible ajax status icons
        $(".ajax-status-result").parent().remove();
    }
    else if(typeof container === 'object'){
        //remove ajax status icons(s) contained within the given object
        container.find(".ajax-status-result").parent().remove();
    }
    else{
        //remove ajax status icons(s) contained within the element with the given ID
        $("#"+container).find(".ajax-status-result").parent().remove();
    }
}


/** clearAjaxStatusClasses()
 *
 *  Clear ajax status classes (colors applied to inputs on page, not status icons)
 *
 *  Parameter "container" may be one of the following:
 *      undefined:      Remove all load images from entire page
 *      jQuery object:  Remove load images from given container object
 *      html id:        Remove load images from container with given ID
 */
function clearAjaxStatusClasses(container){
    var inputs;
    if(typeof container === 'undefined') {
        //remove all visible ajax classes
        inputs = $('input').add("select").add("textarea");
    }
    else if(typeof container === 'object'){
        //remove ajax classes contained within the given object
        inputs = container.find('input').add(container.find("select")).add(container.find("textarea"));
    }
    else{
        //remove ajax save icons(s) contained within the element with the given ID
        var cc = $("#"+container);
        inputs = cc.find('input').add(cc.find("select")).add(cc.find("textarea"));
    }

    inputs.each(function(){
        $(this).removeClass('ajax-success');
        $(this).removeClass('ajax-error');
        $(this).removeClass('ajax-pending');
    });
}


function flash_success(element){
    flash_element(element, 'green')
}
function flash_error(element){
    flash_element(element, 'red')
}
function flash_pending(element){
    flash_element(element, 'orange')
}

function flash_element(element, flash_color, flash_duration, final_color){
    //Set defaults
    if(typeof flash_color === 'undefined'){
        flash_color = '#49ca3b'
    }
    if(typeof flash_duration === 'undefined'){
        flash_duration = 750
    }
    if(typeof final_color === 'undefined'){
        final_color = 'transparent'
    }

    let t = 'transition';
    let tt = 'background-color 1s linear';
    element.css('background-color', flash_color).css(t, tt).css('-moz-'+t, tt).css('-webkit-'+t, tt).css('-ms-'+t, tt);
    setTimeout(function () {
      element.css('background-color', final_color);
    }, flash_duration);
}
