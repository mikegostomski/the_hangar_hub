{% load base_taglib %}
{% load infotext_taglib %}

function enable_edit(el){
    let tr = el.closest('tr');
    tr.find('.it-editable').removeClass('hidden');
    tr.find('.it-readonly').addClass('hidden');
    el.addClass('hidden');
}

var SaveButton = function(context) {
  let ui = $.summernote.ui;
  let icon_class = "{%icon_base_class%} {%icon_class 'fa-floppy-o'%}";
  let button = ui.button({
    contents: '<span class="'+icon_class+'"></span> Save',
    tooltip: 'Save text changes',
    click: function() {

        editable = context.$note.closest('tr').find('.note-editable');
        content = editable.html();
        update_infotext(content, editable)

    }
  });

  return button.render();
}

$(document).ready(function() {
    $('.summernote').summernote({
        toolbar: [
            ['style', ['bold', 'italic', 'underline', 'clear']],
            ['font', ['strikethrough', 'superscript', 'subscript']],
            ['fontsize', ['fontsize']],
            ['fontname', ['fontname']],
            ['color', ['color']],
            ['insert', ['link', 'picture', 'table']],
            ['para', ['ul', 'ol', 'paragraph']],
            ['view', ['fullscreen', 'codeview', 'help']],
            ['height', ['height']],
            ['save', ['save']]
        ],
        buttons: {
          save: SaveButton
        },
        codeviewIframeFilter: true,
        width: '100%',
        theme: 'lite',
        // airMode: true,
        callbacks: {
            onChange: function(content, $editable) {
                let row = $editable.closest('.it-row');
                let original_text = row.find('.summernote').html();
                let editable_text_container = row.find('.note-editable');
                let save_button = row.find('.{%icon_class "fa-floppy-o"%}').parent();

                if(content === original_text){
                    save_button.css('border', '1px solid #dae0e5');
                    editable_text_container.css('background-color', 'inherit');
                }
                else{
                    save_button.css('border', '3px solid orange');
                    editable_text_container.css('background-color', '#EBE3C6');
                }
            }
        }
    });
});


function update_infotext(content, element){
    let row = element.closest('.it-row');
    let saveButton = row.find('.{%icon_class "fa-floppy-o"%}').parent();
    let originalTextContainer = row.find('.summernote');
    let editableTextContainer = row.find('.note-editable');
    let id = row.find('.it-id').html();
    $.ajax({
        type:   "POST",
        url:    "{% url 'infotext:update' %}",
        data:   { id: id, content: content, csrfmiddlewaretoken: '{{ csrf_token }}' },
        beforeSend:function(){
            saveButton.after(getAjaxLoadImage());
            editableTextContainer.css('background-color', '#EBE3C6');
        },
        success:function(data){
            //Update original text (not displayed)
            originalTextContainer.html(data);
            //Ensure editable content matches (if modified server-side)
            editableTextContainer.html(data);
            saveButton.css('border', '1px solid green');
            flash_success(editableTextContainer)

        },
        error:function(){
            saveButton.css('border', '1px solid red');
            editableTextContainer.css('background-color', '#F3DDDF');
        },
        complete:function(){
            clearAjaxLoadImage(saveButton.parent());
        }
    });
}

function delete_infotext(element){
    {%js_confirm column_class="medium" icon="fa-trash-o" title="Delete Infotext" confirm="Delete" cancel="Cancel" onconfirm="_delete_infotext(element);"%}
        Are you sure you want to delete this text?<br />
        <br />
        <em>
            Note: If the text is still in use, it will be automatically re-created with its default content.
        </em>
    {%end_js_confirm%}
}
function _delete_infotext(element){
    let row = element.closest('.it-row');
    let id = row.find('.it-id').html();
    $.ajax({
        type:   "POST",
        url:    "{% url 'infotext:delete' %}",
        data:   { id: id, csrfmiddlewaretoken: '{{ csrf_token }}' },
        beforeSend:function(){
            element.after(getAjaxLoadImage());
        },
        success:function(data){
            row.remove();
        },
        error:function(){

        },
        complete:function(){
            clearAjaxLoadImage(row);
        }
    });
}


function update_group(el){
    let row = el.closest('.it-row');
    let group_title = el.val();
    let id = row.find('.it-id').html();
    $.ajax({
        type:   "POST",
        url:    "{% url 'infotext:group' %}",
        data:   { id: id, group_title: group_title, csrfmiddlewaretoken: '{{ csrf_token }}' },
        beforeSend:function(){
            el.addClass('ajax-pending');
            clearAjaxStatusClasses(row);
        },
        success:function(data){
            el.removeClass('ajax-pending');
            el.addClass('ajax-success');
        },
        error:function(){
            el.removeClass('ajax-pending');
            el.addClass('ajax-error');
        },
        complete:function(){
        }
    });
}
