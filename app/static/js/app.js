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

    /* ---------------------------------------------------------------- */
    /* Repeatable input groups, e.g. one MAC address per interface.      */
    /* ---------------------------------------------------------------- */
    function listOf(button) {
        var group = button.closest("[data-field-group]");
        return group ? group.querySelector("[data-field-list]") : null;
    }

    function rowsOf(list) {
        return list.querySelectorAll(".field-list-row");
    }

    function atMax(list) {
        var max = parseInt(list.getAttribute("data-field-max"), 10);
        return !isNaN(max) && rowsOf(list).length >= max;
    }

    function syncAddButton(list) {
        var group = list.closest("[data-field-group]");
        var button = group ? group.querySelector("[data-field-add]") : null;
        if (!button) { return; }
        var max = parseInt(list.getAttribute("data-field-max"), 10);
        if (!isNaN(max)) {
            button.disabled = atMax(list);
            button.title = button.disabled ? "Limit of " + max + " entries reached" : "";
        }
    }

    function addRow(list, focus) {
        var template = list.querySelector("[data-field-template]");
        if (!template || atMax(list)) {
            syncAddButton(list);
            return null;
        }
        var row = template.content.firstElementChild.cloneNode(true);
        list.insertBefore(row, template);
        syncAddButton(list);
        var input = row.querySelector(".field-list-input");
        if (input && focus) { input.focus(); }
        return input;
    }

    function removeRow(button) {
        var list = button.closest("[data-field-list]");
        var row = button.closest(".field-list-row");
        if (rowsOf(list).length === 1) {
            // Keep one row so the field always stays reachable.
            var only = row.querySelector(".field-list-input");
            if (only) {
                only.value = "";
                validateRow(only);
            }
            return;
        }
        row.parentNode.removeChild(row);
        syncAddButton(list);
    }

    // "AA:BB:CC:DD:EE:FF, 11:22:.." typed or pasted into one row becomes many.
    function splitRow(input) {
        if (input.value.indexOf(",") === -1 && input.value.indexOf(";") === -1) { return; }
        var parts = input.value.split(/[,;]/).map(function (part) {
            return part.trim();
        }).filter(function (part) {
            return part.length > 0;
        });
        if (parts.length < 2) { return; }

        var list = input.closest("[data-field-list]");
        input.value = parts[0];
        parts.slice(1).forEach(function (part) {
            var created = addRow(list, false);
            if (created) { created.value = part; }
        });
    }

    function validateRow(input) {
        if (!input.value.trim()) {
            input.classList.remove("is-invalid");
            input.removeAttribute("aria-invalid");
            return;
        }
        if (input.checkValidity()) {
            input.classList.remove("is-invalid");
            input.removeAttribute("aria-invalid");
        } else {
            input.classList.add("is-invalid");
            input.setAttribute("aria-invalid", "true");
        }
    }

    function isFieldInput(node) {
        return !!(node && node.matches && node.matches(".field-list-input"));
    }

    document.addEventListener("click", function (event) {
        var target = event.target;
        if (!target || !target.closest) { return; }
        var add = target.closest("[data-field-add]");
        var remove = target.closest("[data-field-remove]");
        if (add) {
            event.preventDefault();
            addRow(listOf(add), true);
        } else if (remove) {
            event.preventDefault();
            removeRow(remove);
        }
    });

    document.addEventListener("blur", function (event) {
        if (isFieldInput(event.target)) {
            splitRow(event.target);
            validateRow(event.target);
        }
    }, true);

    document.addEventListener("input", function (event) {
        if (isFieldInput(event.target) && event.target.classList.contains("is-invalid")) {
            validateRow(event.target);
        }
    });

    // Flag any values that arrived pre-filled, e.g. on the edit form.
    document.querySelectorAll("[data-field-list]").forEach(function (list) {
        syncAddButton(list);
        list.querySelectorAll(".field-list-input").forEach(validateRow);
    });
})();
