{% load base_taglib %}

function cancel_invoice(el){
    let td = el.closest("td");
    let tr = td.closest("tr");
    let invoice_id = tr.data("invoice_id");
    {%js_confirm icon="bi-slash-circle" title="Cancel Invoice" onconfirm="_cancel_invoice(invoice_id, tr);"%}
        Are you sure you want to cancel the invoice?
    {%end_js_confirm%}
}
function _cancel_invoice(invoice_id, tr){
    $.ajax({
            type: "POST",
            url: "{%url 'rent:update_rental_invoice' airport.identifier rental_agreement.id%}",
            data:   {
                csrfmiddlewaretoken: '{{ csrf_token }}',
                action: "cancel",
                invoice_id: invoice_id,
            },
            beforeSend:function(){
                setAjaxLoadDiv();
            },
            success: function(data){
                tr.after(data);
                tr.remove();
            },
            error:function(){

            },
            complete:function(){
                clearAjaxLoadDiv();
            }

        });

}


function show_payment_form(el){
    let td = el.closest("td");
    let tr = td.closest("tr");
    let invoice_id = tr.data("invoice_id");

    let container = $("#invoice-payment-container");
    container.removeClass("hidden");

    period = tr.find("td:eq(1)")
    container.find("#invoice-payment-invoice_id").val(invoice_id);
    container.find("#invoice-payment-invoice_label").html("Invoice Period " + period.html());
    container.find("#invoice-payment-amount_paid").val("");
    container.find("#invoice-payment-payment_method_code").val("");
    container.find("#invoice-payment-waive").prop("checked", false);
}

function hide_payment_form(){
    let container = $("#invoice-payment-container");
    container.addClass("hidden");
}

$(document).ready(function(){

    // SUBMIT INVOICE PAYMENT FORM AS AJAX
    $("#invoice-payment-form").submit(function(e){
        e.preventDefault();
        let form = $("#invoice-payment-form");
        let invoice_id = $("#invoice-payment-invoice_id").val();
        let tr = $("#invoice_table").find("tr").filter(function(){
            console.log(`This invoice ID: ${$(this).data("invoice_id")}`)
            return $(this).data("invoice_id") == invoice_id;
        });
        console.log(`Adding payment to invoice: ${invoice_id}`);
        console.log(tr);
        $.ajax({
            type: "POST",
            url: "{%url 'rent:update_rental_invoice' airport.identifier rental_agreement.id%}",
            data: form.serialize(),
            beforeSend:function(){
                setAjaxLoadDiv();
            },
            success: function(data){
                tr.after(data);
                tr.remove();
            },
            error:function(){

            },
            complete:function(){
                hide_payment_form();
                clearAjaxLoadDiv();
            }

        });
    })
});