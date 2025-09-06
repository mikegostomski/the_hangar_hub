function update_auto_pay(btn_el){
    let invoice_container = $("#open-invoice-container");
    let icon = btn_el.find(".bi");
    let use_auto_pay = icon.hasClass("bi-toggle-off") ? "Y" : "N"


        $.ajax({
            type:   "POST",
            url:    '{%url 'pay:set_auto_pay'%}',
            data:   {
                csrfmiddlewaretoken: '{{ csrf_token }}',
                use_auto_pay: use_auto_pay,
            },
            beforeSend:function(){
                btn_el.after(getAjaxLoadImage());
            },
            success:function(data){
                btn_el.closest(".autopay-ind").addClass("hidden")
                if(use_auto_pay == "Y"){
                    $("#autopay-on").removeClass("hidden");
                }
                else{
                    $("#autopay-off").removeClass("hidden");
                }
                invoice_container.html(data);
            },
            error:function(){
                btn_el.closest(".autopay-ind").addClass("hidden")
                if(use_auto_pay == "Y"){
                    $("#autopay-off").removeClass("hidden");
                }
                else{
                    $("#autopay-on").removeClass("hidden");
                }
            },
            complete:function(){
                clearAjaxLoadImage(btn_el.parent());
            }
        });
}