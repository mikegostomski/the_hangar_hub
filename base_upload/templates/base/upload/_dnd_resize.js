{% load base_taglib %}

/** resizeImage()
 *  Resizes a single file
 *      - maxDeviation is the difference that is allowed default: 50kb
 *        Example: targetFileSizeKb = 500 then result will be between 450kb
 *        and 500kb increase the deviation to reduce the amount of iterations.
 ********************************************************************/
async function resizeImage(input, dataUrl, targetFileSizeKb, maxDeviation, status_container){
    let originalFile = dataUrl;

    //Only resize image files greater than specified size
    let imageTypes = ['image/jpeg', 'image/gif', 'image/png'];
    if((!imageTypes.includes(dataUrl.type))||(originalFile.size / 1000 < targetFileSizeKb)){
        return dataUrl;
    }

    let original_file_name = dataUrl.name
    let original_file_type = dataUrl.type

    // Add resizing indicator when the image is being resized
    let resize_ind = '<span class="upload_ind text-info">{%icon fa-spinner bi-arrows-angle-contract fa-spin%} Resizing...</span>';
    if(typeof status_container === 'undefined'){
        input.after(resize_ind);
    }
    else{
        status_container.html(resize_ind);
    }

    let low = 0.0;
    let middle = 0.5;
    let high = 1.0;
    let result = dataUrl;
    let file = originalFile;

    // Image will be resized multiple times to get to the target file size
    while(Math.abs(file.size / 1000 - targetFileSizeKb) > maxDeviation){
        const canvas = document.createElement("canvas");
        const context = canvas.getContext("2d");
        const img = document.createElement('img');
        const promise = new Promise((resolve, reject) => {
            img.onload = () => resolve();
            img.onerror = reject;
        });

        async function readFileAsDataURL(file) {
            let result_base64 = await new Promise((resolve) => {
                let fileReader = new FileReader();
                fileReader.onload = (e) => resolve(fileReader.result);
                fileReader.readAsDataURL(file);
            });

            return result_base64;
        }

        // read file to Data URL using base-64
        let dataURL = await readFileAsDataURL(dataUrl);
        img.src=dataURL;
        await promise;
        canvas.width = Math.round(img.width * middle);
        canvas.height = Math.round(img.height * middle);
        context.scale(canvas.width / img.width, canvas.height / img.height);
        context.drawImage(img, 0, 0);
        file = await urlToFile(canvas.toDataURL(original_file_type),original_file_name,original_file_type);
        if(file.size/1000 < (targetFileSizeKb - maxDeviation)){
            low = middle;
        }
        else if(file.size/1000 > targetFileSizeKb){
            high = middle;
        }
        middle = (low+high)/2;
        result = canvas.toDataURL(original_file_type);
    }
    // convert URL to a file
    res= await urlToFile(result, original_file_name, original_file_type);

    // Remove the resizing indicator
    if(typeof status_container === 'undefined'){
        input.parent().find('.upload_ind').remove();
    }
    else{
        status_container.html('');
    }
    return res;
}

// Used by resizeImage()
function urlToFile(url, filename, mimeType){
    return (fetch(url)
        .then(function(res){return res.arrayBuffer();})
        .then(function(buf){return new File([buf], filename, {type:mimeType});})
    );
}
