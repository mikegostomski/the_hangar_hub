function mb_reply(btn){
    let container = btn.closest(".card");
    let post_id = container.data("post_id");
    let posted_content = container.find(".posted_content").text();
    let popup = $("#mb-response-container");
    popup.find("input[name=response_to]").val(post_id);
    popup.find(".source").html(posted_content);
    popup.removeClass("hidden");
}