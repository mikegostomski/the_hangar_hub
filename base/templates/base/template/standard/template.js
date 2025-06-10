{% load base_taglib %}

var numDismissedPageLoads = 0;
function setPageLoadIndicatorUnlessCtrlClick(ev){
    show_page_loading();
    //If control-click (link opened in new tab)
    if(ev.ctrlKey){
        //Disable the load indicator after 1/2 second
        createCounter(`tempPageLoadInd${numDismissedPageLoads}`, 0, 1, "down", hide_page_loading, 2);
        numDismissedPageLoads++;
    }
}

function setPageLoadIndicator(){
    show_page_loading();
}


$(document).ready(function(){
    try{
        let bc = $('#breadcrumb-container');
        if(bc.html() == ''){
            bc.remove();
        }
    }
    catch(ee){}

    try{setOneTimeLinks();}
    catch(ee){}

    try{
        $(".sr-only").addClass("visually-hidden");
        //Focus on any element given the initial-focus class
        $('.initial-focus').focus();
    }
    catch(ee){}
});
