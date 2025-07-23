{% load base_taglib %}

/** handle_file_selection()
 *  Resize and upload all selected files from one input
 *********************************************************/
function handle_file_selection(input, upload_url, max_size){
    if(typeof max_size === "undefined"){
        max_size = 300;  //Previously 1000
    }

    // Get the file input name
    let input_name = input.attr('name');
    let id = input.attr('id');

    // Get all files from the input (if multiple="true")
    let files = input.prop('files');

    //Prepare file list display elements
    let files_container = $('#' + input_name + '_files_container');
    if(files_container.length == 0){
        input.after(`
            <div id="${input_name}_files_container" class="dnd-status-container hidden">
                <b>Uploaded Files</b>:
                <ol class="dnd-file-list"></ol>
            </div>
        `);
        files_container = $('#' + input_name + '_files_container');
    }
    let file_list = files_container.find('ol');
    if(file_list.length == 0){
        files_container.append(`<ol class="dnd-file-list"></ol>`);
        file_list = files_container.find('ol');
    }

    //Resize each image and upload (individually)
    ([...files]).forEach(function(file_instance) {
        // Get the actual file name of the uploaded file to display on the browser
        let file_name = file_instance.name;

        //Add file to file list
        files_container.removeClass('hidden');
        let file_seq = file_list.find('li').length + 1;
        let li = `<li id="li-fs-${file_seq}"><span class="file_name">${file_name}</span><span class="file_status"></span></li>`;
        file_list.append(li);

        //Get status container
        let status_container = file_list.find(`#li-fs-${file_seq}`).find('.file_status');

        //Status indicators
        let upload_ind = '<span class="upload_ind text-info">{%icon fa-spinner fa-pulse fa-fw%} Uploading...</span>';
        let success_ind = '<span class="upload_ind text-success">{%icon fa-floppy-o fa-fw title="File has been uploaded"%}</span>';
        let error_ind = '<span class="upload_ind text-danger">{%icon fa-exclamation-triangle fa-fw%}</span>';

        //Resize image (if applicable), then...
        resizeImage(input, file_instance, max_size, 50, status_container).then((resized_image)=>{

            // Create a new FormData object
            let formData = new FormData();

            // Add CSRF token (required for all POST requests)
            formData.append('csrfmiddlewaretoken', '{{csrf_token}}');

            //Add the input name
            formData.append('input_name', input_name);

            // Add resized file to the FormData
            formData.append(input_name, resized_image);

            $.ajax({
                type:   "POST",
                url:    upload_url,
                data:   formData,
                processData: false,
                contentType: false,
                beforeSend:function(){
                    status_container.html(upload_ind);
                },
                success:function(data){
                    status_container.html(success_ind);
                },
                error:function(data){
                    status_container.html(error_ind);
                },
                complete:function(){}
            });
        });
    });
    input.val('');
}

function dndHoverStyles(){
    $('.dnd-input').on('dragenter', function(){
        $(this).addClass('dnd-input-hover');
    });
    $('input[type=file]').on('dragleave', function(){
        $(this).removeClass('dnd-input-hover');
    });
}

$(document).ready(function(){
    dndHoverStyles();
});