/** scriptAlreadyIncluded()
 *
 * Has the script with the given src already been loaded?
 *
 **/
function scriptAlreadyIncluded(src){
    var scripts = document.getElementsByTagName("script");
    for(var ii = 0; ii < scripts.length; ii++)
        if(scripts[ii].getAttribute('src') === src){
            return true;
        }
    return false;
}


/** getSelectionText()
 *
 * Get text that user has selected/highlighted
 *
 **/
function getSelectionText() {
    //http://stackoverflow.com/questions/5379120/get-the-highlighted-selected-text
    var text = "";
    try {
        if (window.getSelection) {
            text = window.getSelection().toString();
        }
        else if (document.selection && document.selection.type !== "Control") {
            text = document.selection.createRange().text;
        }
    }
    catch(ee){}
    return text;
}


function formatTelephone(phoneNumber){
    try {
        //Get number without any non-word characters
        var digits = phoneNumber.replace(/\W/g, '');

        //Prepare a formatted string
        var formatted = "";

        //If less than three characters, do not format them
        if (digits.length < 3) {
            formatted = digits;
        }
        else {
            //###-
            formatted = digits.substring(0, 3) + '-';
            digits = digits.substring(3);

            if (digits.length <= 4) {
                //###-####
                formatted += digits;
            }
            else {
                //###-###-
                formatted += digits.substring(0, 3) + '-';
                digits = digits.substring(3);

                if (digits.length <= 4) {
                    //###-###-####
                    formatted += digits;
                }
                else{
                    //###-###-####
                    formatted += digits.substring(0, 4) + ' ';
                    digits = digits.substring(4);
                    //###-###-#### ##
                    formatted += digits;
                }
            }
        }
        return formatted
    }
    catch(ee){
        return phoneNumber
    }
}


/** One-Time Link functions:
 *      setOneTimeLinks(), resetOneTimeLink(element), oneTimeLinkClicked(element)
 *
 * These functions deactivate any clickable element with the "one-time-link" class as soon as the user clicks on it
 * (i.e. A link (<a>), or any element with an onclick="" action)
 *
 * Only the setOneTimeLinks() function needs to be called. The rest is automated.
 * Calling setOneTimeLinks() multiple times is fine. Subsequent calls will set all links back to a non-clicked state
 */
var otlSequence = 0;
function setOneTimeLinks(){
    //For each original one-time-link (alternate elements will contain the same classes)
    $('.one-time-link').not('.otl-alternate').each(function(){

        //Note: The link may be an <a> or any element with an onclick event
        var clickable = $(this);

        //If not yet initialized
        if(!clickable.hasClass('otl-original')) {

            //Get type of element
            var elementType = clickable.prop('nodeName').toLowerCase();

            //Create a unique sequence for this clickable
            otlSequence++;
            var otlId = 'otl-' + otlSequence;
            while ($('#'+otlId).length > 0){
                otlSequence++;
                otlId = 'otl-' + otlSequence;
            }

            //Assign a unique OneTimeLink ID
            clickable.attr('otlId', otlId);

            //Get original classes and content for alternate element
            var altClass = clickable.attr('class') + ' otl-alternate disabled hidden';
            var altStyle = clickable.attr('style');
            var altData = clickable.html();
            var type = (elementType === 'button' ? 'type="button"' : '');

            //Create another (hidden) blank element with the same OTL ID
            clickable.after('<'+elementType+' class="'+altClass+'" style="'+altStyle+'" otlId="'+otlId+'" '+type+'>'+altData+'</'+elementType+'>');

            //Mark the original as such
            clickable.addClass('otl-original');

            //Call additional action when original link is clicked
            clickable.click(function(){
                oneTimeLinkClicked(clickable);
            });
        }

        //Reset any clicked links after some action has happened that resulted in calling this
        else{
            resetOneTimeLink(clickable);
        }
    });
}
function resetOneTimeLink(element){
    //Get the id that ties original and alternate elements
    var otlId = element.attr('otlId');
    //Find the alternate element
    var alternateElement = element.parent().find('.otl-alternate').filter(function(){
        return ($(this).attr('otlId') === otlId);
    });
    //Show original and hide alternate
    element.removeClass('hidden');
    alternateElement.addClass('hidden');

}
function oneTimeLinkClicked(element){
    //Get the id that ties original and alternate elements
    var otlId = element.attr('otlId');
    //Find the alternate element
    var alternateElement = element.parent().find('.otl-alternate').filter(function(){
        return ($(this).attr('otlId') === otlId);
    });
    //Show alternate and hide original
    alternateElement.removeClass('hidden');
    element.addClass('hidden');
}


/** Timer functions:
 *      create, start, pause, resume, reset, touch
 *
 * These functions create timers (either displayed on-screen, or not included in the UI).
 * The timers may count up or down, and call an action when the specified time has passed.
 *
 * Creating a timer:
 *      counterName      - A name for the timer that is unique to the page
 *      minutes, seconds - Number of minutes/seconds until the timer stops
 *      direction        - "up" to count up from zero, or "down" to count down to zero
 *      timerAction      - JS code to be called when timer completes
 *      speedMultiplier  - Allows timers to count time in increments less than 1 second. Examples:
 *                             speedMultiplier of 1 == 1 second iterations
 *                             speedMultiplier of 2 == 1/2 second iterations
 *                             speedMultiplier of 5 == 1/5 second iterations
 *      autostart        - Timer will start automatically unless you provide a false value
 *
 * Displaying a timer:
 *    To display a counter in the UI, you must assign conventional ID(s) to the containing element(s):
 *
 *      >  The ID must end with "-<counterName>"
 *      >  To display only seconds, ID must contain "second"
 *      >  To display only minutes, ID must contain "minute"
 *
 *      Examples:
 *        To display minutes only:      id="minutes-<counterName>"
 *        To display seconds only:      id="seconds-<counterName>"
 *        To display full time:         id="counter-<counterName>"
 */
var counters = {};
function createCounter(counterName, minutes, seconds, direction, timerAction, speedMultiplier, autostart){
    //If counter already exists, do not overwrite it.  Reset it instead.
    if(counterName in counters){
        resetCounter(counterName, minutes, seconds);
        return true;
    }

    //For speeding up timer (to count time in increments less than 1 second)
    //Ex. speedMultiplier of 2 == 1/2 second iterations
    if(typeof speedMultiplier === 'undefined'){
        speedMultiplier = 1;
    }

    //Create a new counter
    counters[counterName] = {
        defaultMinutes: minutes, defaultSeconds: seconds,
        direction: direction, speedMultiplier: speedMultiplier,
        action:function(){ timerAction(); },
        minutes: undefined, seconds: undefined, interval: undefined, initialized: false, paused: false
    };

    //Set counter to specified time
    resetCounter(counterName, minutes, seconds);

    //Set any displays to the initial time
    updateCounterDisplay(counterName);

    //Start the timer, unless specified not to
    if((typeof autostart === 'undefined') || autostart){
        startCounter(counterName);
    }
}
function startCounter(counterName, minutes, seconds){
    try {
        //Set counter to specified or default time
        resetCounter(counterName, minutes, seconds);

        //If counter is already running, do not start it again
        if(counters[counterName]['initialized']){
            return true;
        }

        //Start the timer
        counters[counterName]['interval'] = setInterval(function(){touchCounter(counterName)}, 1000/counters[counterName]['speedMultiplier']);
        counters[counterName]['initialized'] = true;
    }
    catch(ee){ }

}
function pauseCounter(counterName){
    try{
        clearInterval(counters[counterName]['interval']);
        counters[counterName]['paused'] = true;
    }
    catch(ee){ }
}
function resumeCounter(counterName){
    try{
        counters[counterName]['interval'] = setInterval(function(){touchCounter(counterName)}, 1000/counters[counterName]['speedMultiplier']);
        counters[counterName]['paused'] = false;
    }
    catch(ee){ }
}
function resetCounter(counterName, minutes, seconds){
    try{
        if(counters[counterName]['direction'] === 'down') {

            //If reset time not specified, use default
            if (typeof minutes === 'undefined') {
                minutes = counters[counterName]['defaultMinutes'];
            }
            if (typeof seconds === 'undefined') {
                seconds = counters[counterName]['defaultSeconds'];
            }
        }
        else{
            //If reset time not specified, reset to zero
            if (typeof minutes === 'undefined') {
                minutes = 0;
            }
            if (typeof seconds === 'undefined') {
                seconds = 0;
            }
        }

        //Reset counter
        counters[counterName]['minutes'] = minutes;
        counters[counterName]['seconds'] = seconds;
        //Also set default time to this new time
        counters[counterName]['defaultMinutes'] = minutes;
        counters[counterName]['defaultSeconds'] = seconds;
    }
    catch(ee){}
}
function touchCounter(counterName){
    try{
        var mm = counters[counterName]['minutes'];
        var ss = counters[counterName]['seconds'];

        //If counting down
        if(counters[counterName]['direction'] === 'down') {

            //If counter is done counting
            if (mm + ss === 0) {
                //Interval should have already been cleared, but clear again, just to be safe
                try{
                    clearInterval(counters[counterName]['interval']);
                }
                catch(ee){}
                return
            }

            //If reducing minutes
            if (ss === 0 && mm > 0) {
                mm -= 1;
                ss = 60;
            }
            //If reducing seconds
            if (ss > 0) {
                ss -= 1;
            }

            //Update minutes and seconds
            counters[counterName]['minutes'] = mm;
            counters[counterName]['seconds'] = ss;

            //Stop the counter at 0:00, and call the defined action
            if (mm + ss === 0) {

                //Make sure counter is set to 0:00
                counters[counterName]['minutes'] = 0;
                counters[counterName]['seconds'] = 0;

                //Stop the timer
                clearInterval(counters[counterName]['interval']);
                counters[counterName]['initialized'] = false;
                //Call the action
                try {
                    counters[counterName]['action']();
                }
                catch(ee){}
            }
        }

        //If counting up
        else{
            ss += 1;
            if(ss === 60){
                mm += 1;
                ss = 0;
            }

            //Update minutes and seconds
            counters[counterName]['minutes'] = mm;
            counters[counterName]['seconds'] = ss;

            //Stop the counter at its limit, and call the defined action
            if (mm === counters[counterName]['defaultMinutes'] && ss === counters[counterName]['defaultSeconds']) {

                //Stop the timer
                clearInterval(counters[counterName]['interval']);
                //Call the action
                try {
                    counters[counterName]['action']();
                }
                catch(ee){}
            }
        }

        updateCounterDisplay(counterName);
    }
    catch(ee){}
}
function updateCounterDisplay(counterName){
    var mm = counters[counterName]['minutes'];
    var ss = counters[counterName]['seconds'];

    //seconds as two-digit string
    var ssStr = ('00' + ss).substr(-2);
    var timeStr = mm + ":" + ssStr;

    //Look for any ID containing the timer name
    $('*[id$='+counterName+']').each(
        function(){
            var el = $(this);
            var id = el.attr('id').toLowerCase().replace('-'+counterName, '');
            //If container is for minutes
            if(id.indexOf('minute') >= 0){
                if(el.is("input")){ el.val(mm); } else{ el.html(mm); }
            }
            //If container is for seconds
            else if(id.indexOf('second') >= 0){
                if(el.is("input")){ el.val(ssStr); } else{ el.html(ssStr); }
            }
            //Otherwise, show full time
            else{
                if(el.is("input")){ el.val(timeStr); } else{ el.html(timeStr); }
            }
        }
    );
}
