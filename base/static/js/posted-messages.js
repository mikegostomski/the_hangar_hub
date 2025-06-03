  /** posted_messages()
   *
   *  Gets messages (error, warning, debug, success) from the session and
   *  posts them as alerts in the message console
   */
  function posted_messages(message_url){
    $.ajax({
        bypassGlobalComplete: true,
        type:   "GET",
        url:    message_url,
        data:   { ts: new Date().getTime() },
        beforeSend:function(){
            clearStaleMessages();
        },
        success:function(data){
            $("#message-container").append(data);
            clearDuplicateMessages();
            autoHideMessages();
        },
        error:function(){
        },
        complete:function(){
        }
    });
   };

  /** clearStaleMessages(seconds)
   *
   * Every time new messages are rendered, clear any "stale" messages still on the screen.
   * Considered stale after given number of seconds;   default: 3
   **/
  function clearStaleMessages(seconds){
    if(typeof seconds === 'undefined'){
        seconds = 3;
    }

    let now = Math.round(new Date() / 1000);
    let stale = now - seconds;

    $("#message-container").find('.alert-dismissible').filter(function(){
        let dob = $(this).attr('birth_date');
        return (dob && parseInt(dob) < stale);
    }).remove();
  }

  /** clearDuplicateMessages()
   *
   * Remove all existing messages of specified class and content prior to posting the new one
   */
  function clearDuplicateMessages(){

    $('#message-container').find('.alert-dismissible').each(function(){
        let thisMessage = $(this);
        let identifier = getMessageIdentifier(thisMessage);
        let className = thisMessage.attr('class').split(/\s+/)[1];
        let content = thisMessage.find('span.message-content').text().replace(/\s/g,'');

        //If messages are posted twice in the same second, identifiers could be duplicated
        let identifierCount = 0;

        let matches = $('#message-container').find('.'+className).filter(function(){
            let thisInstance = $(this);
            let instanceIdentifier = getMessageIdentifier(thisInstance);

            //Does this message have the same content?
            let instanceContent = thisInstance.find('span.message-content').text().replace(/\s/g,'');
            let duplicate = (instanceContent === content);

            //If this is duplicate content, it could be the same instance
            if(duplicate){
                let sameIdentifier = (instanceIdentifier === identifier);

                if(sameIdentifier){
                    identifierCount += 1;
                }

                //If this duplicate content is not the same instance, or identifier has been duplicated
                if( (!sameIdentifier) || identifierCount > 1){
                    return true //This is a true duplicate, and one of them must be removed
                }
            }
            return false;
        });

        if(matches.length > 0){
            //If there are (newer) matches, remove this (older) one.
            thisMessage.remove();
        }
    });
  }
  function getMessageIdentifier(msg){
        let dob = msg.attr('birth_date');
        let seq = msg.attr('seq');
        return `${dob}-${seq}`
  }

  /** autoHideMessages()
   *
   * Hide messages (messages fixed at top of screen)
   */
  function autoHideMessages(){
      // Auto-hide may be annoying because it makes content move
      return false;
      var msgContainer = $("#message-container");
      var numSeconds = 0;
      var offset = 1;
      var offset_warn = 0;
      var offset_info = 0;

      msgContainer.find(".alert").each(function(){

          //If a timeout was already set, ignore this message
          if($(this).attr('timeout-set')){
              return true;
          }

          //Do not auto-hide errors
          if($(this).hasClass('alert-danger') || $(this).hasClass('alert-error')){
              return true;
          }

          //Warnings auto-hide after 20 seconds
          if($(this).hasClass('alert-warning')){
              numSeconds = 20 + offset_warn;
              offset_warn += offset;
          }
          //Hide info/success after 10 seconds
          else{
              numSeconds = 10 + offset_info;
              offset_info += offset;
          }

          var identifier = $(this).attr('id');
          if(typeof identifier === 'undefined' || identifier == 'undefined'){
              identifier = 'postedMsg-' + postedSeq;
              $(this).attr('id', identifier);
          }

          setTimeout((function() { $("#"+identifier).fadeOut(400); }), (numSeconds*1000));
          $(this).attr('timeout-set', true);

          postedSeq++;
      });
  }

var postedSeq = 0;
$(document).ready(function(){
    autoHideMessages();
});

$(document).ajaxComplete(function(e, xhr, settings){
    if (!settings.bypassGlobalComplete){
        posted_messages("{% url 'base:messages' %}");
    }
});