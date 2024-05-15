// Filter by Test / Filter by User Template pills: toggles .ek-pill-checked
// on each checkbox's <label> (the pill itself) so the CSS can style the
// selected state reliably across browsers, instead of a CSS :has() selector.
// Targets the <label>, not a wrapping <li>/<div> - the label is the one
// element guaranteed present regardless of which container Django's
// CheckboxSelectMultiple widget happens to render around it.
$(document).ready(function () {
    function syncPillState(checkbox) {
        checkbox.closest('label').toggleClass('ek-pill-checked', checkbox.is(':checked'));
    }

    var $checkboxes = $('.ek-pill-list input[type="checkbox"]');
    $checkboxes.each(function () { syncPillState($(this)); });
    $checkboxes.on('change', function () { syncPillState($(this)); });

    // "Select All" flips every checkbox's checked state without firing
    // individual change events - re-sync all pills right after.
    $('.selectAllGlobalTemplateButton, .selectAllUserTemplateButton').on('click', function () {
        setTimeout(function () {
            $checkboxes.each(function () { syncPillState($(this)); });
        }, 0);
    });
});
