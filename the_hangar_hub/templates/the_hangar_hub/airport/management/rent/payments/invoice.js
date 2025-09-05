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