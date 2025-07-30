function update_account(input_el){
    console.log("Update Account")
    let row = input_el.closest("tr");
    let account_id = row.data("account_id");
    console.log(`Account ID: ${account_id}`)

    if(input_el.is("button")){
        console.log("Is a button")
        let street_1 = row.find("input[name='street_1']").val()
        let street_2 = row.find("input[name='street_2']").val()
        let city = row.find("input[name='city']").val()
        let state = row.find("input[name='state']").val()
        let zip_code = row.find("input[name='zip_code']").val()
        let country = row.find("input[name='country']").val()

       console.log("Doing it...");
        $.ajax({
            type:   "POST",
            url:    "{%url 'stripe:modify_account'%}",
            data:   {
                csrfmiddlewaretoken: '{{ csrf_token }}',
                account_id: account_id,
                street_1: street_1,
                street_2: street_2,
                city: city,
                state: state,
                zip_code: zip_code,
                country: country
            },
            beforeSend:function(){
                input_el.after(getAjaxLoadImage());
                input_el.addClass("hidden");
                console.log("Sending...")
            },
            success:function(data){
                input_el.removeClass("hidden");
                flash_success(input_el);
            },
            error:function(){
                input_el.removeClass("hidden");
                flash_error(input_el);
            },
            complete:function(){
                clearAjaxLoadImage(input_el.parent());
            }
        });

    }
    else{
        console.log("Not a button")
        let attr = input_el.attr("name");
        let val = input_el.val();
        $.ajax({
            type:   "POST",
            url:    "{%url 'stripe:modify_account'%}",
            data:   {
                csrfmiddlewaretoken: '{{ csrf_token }}',
                account_id: account_id,
                [attr]: val
            },
            beforeSend:function(){
                input_el.after(getAjaxLoadImage());
                input_el.addClass("hidden");
            },
            success:function(data){
                input_el.removeClass("hidden");
                flash_success(input_el);
            },
            error:function(){
                input_el.removeClass("hidden");
                flash_error(input_el);
            },
            complete:function(){
                clearAjaxLoadImage(input_el.parent());
            }
        });
    }
}