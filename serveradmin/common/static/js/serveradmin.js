$(document).ready(function() {
    // Mark the current page as active in navigation
    let selector = 'nav .nav-link[href="' + window.location.pathname + '"]';
    $(selector)[0].classList.add('active');

    // This is our progress spinner we can call e.g. spinner.enable() from
    // everywhere when ever we need it for example when doing long running
    // ajax requests for the servershell search.
    spinner = {
        enable: function () {
            $('#spinner').show();
        },
        disabled: function () {
            $('#spinner').hide();
        },
    }
});