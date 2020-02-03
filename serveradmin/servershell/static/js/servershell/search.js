/**
 * Submit Search Term
 *
 * Take the current entered search term and the settings such as per_page etc.
 * and submit the query to the Serveradmin backend. On success extract the
 * result to the corresponding servershell properties.
 */
let submit_search = function() {
    spinner.enable();

    let data = {
        term: servershell.term,
        shown_attributes: servershell.shown_attributes,
        offset: servershell.offset,
        limit: servershell.limit,
        order_by: servershell.order_by,
        async: false,
    };

    let url = $('#search_form').get(0).action;
    console.debug(`Submitting query to URL "${url}" with data:`);
    console.debug(data);

    $.getJSON(url, data, function(data) {
        // Update property used by bookmark link of search
        servershell.href = '?' + $.param({
            'term': servershell.term,
            'attrs': servershell.shown_attributes
        });

        servershell.editable_attributes = data.editable_attributes;
        servershell.num_servers = data.num_servers;
        servershell.servers = data.servers;
        servershell.status = data.status;
        servershell.understood = data.understood;

        console.debug(`Query result status is: "${data.status}" with data:`);
        console.debug(data);

        spinner.disabled();
    });
};

$(document).ready(function() {
    // 2-Way Data Binding for search, command, understood elements

    // Update input elements when values change by e.g. submitted search
    $(document).on('servershell_property_set', function(event, data) {
        $(`[data-servershell-property-bind=${data.property}]`).val(servershell[data.property]);
    });

    // Update servershell object properties when input element value change
    $('[data-servershell-property-bind]').on('change', function(event) {
        // @TODO Avoid triggering the sync twice
        let property = $(event.target).data('servershell-property-bind');
        servershell[property] = event.target.value;
    });

    // ------------------------------------------------------------------------

    // Submit form with Ajax and prevent normal submission
    $('#search_form').submit(function(event) {
        event.preventDefault();
        submit_search();
    });

    // Reload search if anything relevant changes ...
    let events = [
        'servershell_property_set_shown_attributes',
        'servershell_property_push_shown_attributes',
        'servershell_property_splice_shown_attributes',
    ];
    $(document).on(events.join(' '), function() {
        submit_search();
    });
});