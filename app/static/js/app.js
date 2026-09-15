(function () {
    "use strict";

    // Confirmation prompts for destructive forms
    document.addEventListener("submit", function (event) {
        var form = event.target;
        if (form.matches("[data-confirm]")) {
            if (!window.confirm(form.getAttribute("data-confirm"))) {
                event.preventDefault();
            }
        }
    });

    // Auto-dismiss flash alerts after 6 seconds
    document.querySelectorAll(".flash-alert").forEach(function (el) {
        window.setTimeout(function () {
            var close = new bootstrap.Alert(el);
            close.close();
        }, 6000);
    });
})();