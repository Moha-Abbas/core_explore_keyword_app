/**
 * Search
 */
var SUBMIT_DELAY = 3000;
var SORTING_SUBMIT_DELAY = 500;
var timer;
var cachedOperators;
const SELECT_ALL_LABEL = "Select All";
const UNSELECT_ALL_LABEL = "Unselect All";

const global_event = {
    input_id: 'id_global_templates',
    button_selector: '.selectAllGlobalTemplateButton'
}

const user_event = {
    input_id: 'id_user_templates',
    button_selector: '.selectAllUserTemplateButton'
}

/**
 * Show / hide placeholder
 */
function showHidePlaceholder($tagit){
   var $input = $tagit.data("ui-tagit").tagInput;
   placeholderText = $tagit.data("ui-tagit").options.placeholderText;

    if ($tagit.tagit("assignedTags").length > 0) {
        $input.removeAttr('placeholder');
        $(".tagit-new").css({"width": "auto"});

    } else {
        $input.attr('placeholder', placeholderText);
        $(".tagit-new").css({"width": "100%"});
        $(".tagit-new input").css({"width": "100%"});

    }
}

/**
 * Initialize auto submission
 */
var initAutoSubmit = function() {
    $("#id_keywords").tagit({
        onTagAdded: function(event, ui) {
            // delay submission after a tag is added
            fancyTreeSelectDelaySubmit();
            cleanSearchOperatorStyle(true);
        }
    });

    $('#id_keywords').tagit().next('ul').find('li input.ui-widget-content').focus(function(e) {
        if (!e.originalEvent) return;
        // avoid submission when a tag is focused
        clearTimeout(timer);
        timer = null;
    });

    $(".ui-autocomplete-input").on("keyup", (event) => {

        var jqNewTagInputValue = $(".ui-autocomplete-input").val();
        // check the key if the key is ':' it could be a search operator
        if (event.originalEvent && event.originalEvent.key === ':') {
            var jqCurrentTarget = $(event.currentTarget).parent();
            checkOperator(jqNewTagInputValue, jqCurrentTarget);
        } else if ( jqNewTagInputValue === "" || jqNewTagInputValue.indexOf(":") === -1) {
            cleanSearchOperatorStyle(true);
        } else if ( event.originalEvent.key !== "Enter") {
            // avoid submission when user is typing
            clearTimeout(timer);
            timer = null;
        }
    });
}

/**
  * Call the REST API to get the operators list and check if operatorValue is a valid operator
  * if yes color the tag in green if not color the tag in blue
  * @param: operatorValue the operator tapped by the user
  * @param: the jQuery element of the element to color
  * @param: the optional success callBack function
  */
var checkOperator = function(operatorValue, target, callBack) {
        if (cachedOperators === undefined) {
            $.ajax({
                url: operatorListURL,
                type : "GET",
                contentType: 'application/json',
                success: function(data){
                    if (data && data.length > 0) {
                        cachedOperators = data;
                        applyInputStyle(cachedOperators, operatorValue, target);
                    }
                    if (typeof callBack === 'function') callBack(data);
                },
                error: function(data){
                    cleanSearchOperatorStyle(true);
                    target.addClass('tagit-choice-editable operator-bg-error-color');
                }
            });
        } else {
            applyInputStyle(cachedOperators, operatorValue, target);
            if (typeof callBack === 'function') callBack(cachedOperators);
        }
}



/**
  * Add the input style if the current operator match with the operator list
  * @param: operatorsList: Array<string> list of the available operator
  * @param: operatorsValue: string value tapped bu the user
  * @param: target: DomElement element to apply the style
  */
var applyInputStyle = function(operatorList, operatorValue, target) {
    operatorList.forEach( (operator, index) => {
        if (operatorValue && operator.name && operator.name === operatorValue.slice(0, -1)) {
            cleanSearchOperatorStyle(true);
            target.addClass('tagit-choice-editable operator-bg-success-color');
        }
    });
}


/**
  * Clean the style added when the user tape ':' a potential search operator
  * @param: force boolean force the clean if true clean only if there are not tags left
  */
var cleanSearchOperatorStyle = function(force) {
    // get all the tags in the page
    if (force || $("li.tagit-choice").length === 0) {
        // remove all the possible state of the tag
        var jqTagInputElement = $(".tagit-new");
        jqTagInputElement.removeClass("tagit-choice-editable " +
            "operator-bg-success-color " +
            "operator-bg-error-color "
        );

        showHidePlaceholder($("#id_keywords").tagit());
    }
}

/**
  * Add style to the operator tag
  */
var addOperatorTagStyle = function() {
    var tagList = $("#id_keywords").tagit("assignedTags");
    var jqNewTagInputValue = $(".ui-autocomplete-input").val();
    var jqTargetElement = $(".tagit-new");
    var operatorsIndexes = [];
    checkOperator(jqNewTagInputValue, jqTargetElement, (operators)=>{
        tagList.forEach( (tagValue, tagIndex) => {
            if(tagValue.indexOf(":") !== -1) {
                // we get the element at the left of the operator separator
                var operatorTagValue = tagValue.split(":")[0];
                // search in the current tag list if one of these values match with one of the created Operators
                for (var index=0; index<operators.length; ++index) {
                    if (operators[index] && operators[index].name === operatorTagValue) {
                        operatorsIndexes.push(tagIndex);
                    }
                }
            }
        });

        var tagElements = $('.tagit-choice');
        operatorsIndexes.forEach( (currentTagIndex) => {
            $(tagElements[currentTagIndex]).addClass('tagit-choice-editable operator-bg-success-color');
        });

    });
}

/**
 * Initialize autocomplete
 */
var initAutocomplete = function () {
    $("#id_keywords").tagit({
        allowSpaces: false,
        placeholderText: 'Search record names, properties and values, or leave blank to retrieve all records',
        afterTagRemoved: function (event, ui) {
            showHidePlaceholder($(this));
        },
        afterTagAdded: function (event, ui) {
            showHidePlaceholder($(this));
            addOperatorTagStyle();
        },
        autocomplete: ({
            search: function (event, ui) {
                $("#loading").addClass("isloading");
            },
            response: function (event, ui) {
                $("#loading").removeClass("isloading");
            },
            focus: function (event, ui) {
                this.value = ui.item.label;
            },
            source: getAutocompleteSource,
            minLength: 2,
            select: function (event, ui) {
                this.value = ui.item.label;
                $("#id_keywords").tagit("createTag", this.value);
                return false;
            }
        })
    });
    // init the place holder and calc his width
    showHidePlaceholder($("#id_keywords").tagit());
};


/**
 * Initialize select template all button
 */
var initSelectAllTemplate = function() {
    $(".selectAllGlobalTemplateButton").on("click", global_event, selectAllTemplate);
    $(".selectAllUserTemplateButton").on("click", user_event, selectAllTemplate);
    $("input[id^='id_global_templates']").each(function(i) {
        $(this).on("change", global_event, checkIfAllTemplateSelected);
    });
    $("input[id^='id_user_templates']").each(function(i) {
        $(this).on("change", user_event, checkIfAllTemplateSelected);
    });
    checkIfAllTemplateSelected({ data: global_event });
    checkIfAllTemplateSelected({ data: user_event });
}

/**
 * check if all templates are selected
 */
var checkIfAllTemplateSelected = function(event) {
    var allSelected = true;
    $("input[id^=" + event.data.input_id + "]").each(function(i) {
        if($(this).prop("checked") == false) {
            allSelected = false;
            return false;
        }
    });

    if (allSelected) {
        $(event.data.button_selector).html(UNSELECT_ALL_LABEL);
    } else {
        $(event.data.button_selector).html(SELECT_ALL_LABEL);
    }
}

/**
 * Select all Template function
 */
var selectAllTemplate = function(event) {
    var selectAll = false;
    if ($(event.data.button_selector).html().trim() == SELECT_ALL_LABEL) {
        selectAll = true;
        $(event.data.button_selector).html(UNSELECT_ALL_LABEL);
    } else {
        $(event.data.button_selector).html(SELECT_ALL_LABEL);
    }
    $("input[id^=" + event.data.input_id + "]").each(function(i) {
        $(this).prop("checked", selectAll);
    });
}

/**
 * Called after any selection in the tree
 */
var fancyTreeSelectDelaySubmit = function(force=true){
    if (force) {
        delaySubmission();
    } else {
        if (timer)
            delaySubmission();
    }
}

/**
 * Delay submission
 */
var delaySubmission = function() {
    // clear the timer
    clearTimeout(timer);
    // submit the form after 3 sec
    timer = setTimeout(submitForm, SUBMIT_DELAY);
}

/**
 * Submit the form
 */
var submitForm = function () {
    $("#form_search").submit();
}

var initSortingAutoSubmit = function() {
    // waiting for the end of the AJAX call result DOM injection
    var MAX_INTERVAL_ITER = 10;
    var iteration = 0;

    var interval = setInterval(function() {
        iteration++;
        if (iteration >= MAX_INTERVAL_ITER) clearInterval(interval);
        if ($(".filter-dropdown-menu").length > 0) {
            clearInterval(interval);
            $(".dropdown-menu.tools-menu.filter-dropdown-menu li").click(debounce(function() {
                submitForm();
            }, SORTING_SUBMIT_DELAY));
        }
    }, 500);
}

$(document).ready(function() {
    initAutocomplete();
    initAutoSubmit();
    initSelectAllTemplate();
    initSortingAutoSubmit();
    addOperatorTagStyle();
});