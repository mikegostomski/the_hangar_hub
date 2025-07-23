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