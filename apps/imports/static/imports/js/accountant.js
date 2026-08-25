document.addEventListener("DOMContentLoaded", () => {
    const themeStorageKey = (
        "delisky-dashboard-theme"
    );

    const themeRoot = document.documentElement;

    const themeButtons = Array.from(
        document.querySelectorAll(
            "[data-theme-option]"
        )
    );

    const systemThemeQuery = window.matchMedia(
        "(prefers-color-scheme: dark)"
    );

    const validThemePreferences = new Set([
        "light",
        "system",
        "dark",
    ]);

    const readThemePreference = () => {
        try {
            const savedPreference = (
                localStorage.getItem(
                    themeStorageKey
                )
            );

            return validThemePreferences.has(
                savedPreference
            )
                ? savedPreference
                : "system";
        } catch (error) {
            return "system";
        }
    };

    const resolveTheme = (preference) => {
        if (preference === "system") {
            return systemThemeQuery.matches
                ? "dark"
                : "light";
        }

        return preference;
    };

    const updateThemeButtons = (
        preference
    ) => {
        themeButtons.forEach((button) => {
            const isActive = (
                button.dataset.themeOption
                === preference
            );

            button.classList.toggle(
                "is-active",
                isActive
            );

            button.setAttribute(
                "aria-pressed",
                String(isActive)
            );
        });
    };

    const applyTheme = (
        preference,
        options = {}
    ) => {
        const normalizedPreference = (
            validThemePreferences.has(
                preference
            )
                ? preference
                : "system"
        );

        const resolvedTheme = resolveTheme(
            normalizedPreference
        );

        themeRoot.dataset.themePreference = (
            normalizedPreference
        );

        themeRoot.dataset.theme = resolvedTheme;

        updateThemeButtons(
            normalizedPreference
        );

        if (options.persist) {
            try {
                localStorage.setItem(
                    themeStorageKey,
                    normalizedPreference
                );
            } catch (error) {
                // The selected theme still works
                // for the current page.
            }
        }
    };

    themeButtons.forEach((button) => {
        button.addEventListener(
            "click",
            () => {
                applyTheme(
                    button.dataset.themeOption,
                    {
                        persist: true,
                    }
                );
            }
        );
    });

    const handleSystemThemeChange = () => {
        if (
            themeRoot.dataset
                .themePreference
            === "system"
        ) {
            applyTheme("system");
        }
    };

    if (
        typeof systemThemeQuery
            .addEventListener
        === "function"
    ) {
        systemThemeQuery.addEventListener(
            "change",
            handleSystemThemeChange
        );
    } else if (
        typeof systemThemeQuery
            .addListener
        === "function"
    ) {
        systemThemeQuery.addListener(
            handleSystemThemeChange
        );
    }

    window.addEventListener(
        "storage",
        (event) => {
            if (
                event.key
                === themeStorageKey
            ) {
                applyTheme(
                    readThemePreference()
                );
            }
        }
    );

    applyTheme(
        themeRoot.dataset
            .themePreference
        || readThemePreference()
    );

    const input = document.querySelector(
        ".accountant-file-input"
    );

    const label = document.querySelector(
        ".drop-zone"
    );

    const filename = document.querySelector(
        "#selected-file-name"
    );

    const reportType = document.querySelector(
        "#id_report_type"
    );

    const periodStartLabel = document.querySelector(
        "#period-start-label"
    );

    const periodEndField = document.querySelector(
        "#period-end-field"
    );

    const periodEndInput = document.querySelector(
        "#id_period_end"
    );

    const updateFilename = () => {
        if (!input || !label || !filename) {
            return;
        }

        const file = input.files?.[0];

        filename.textContent = file
            ? file.name
            : "\u0644\u0645 \u064a\u062a\u0645 "
              + "\u0627\u062e\u062a\u064a\u0627\u0631 "
              + "\u0623\u064a \u0645\u0644\u0641";

        label.classList.toggle(
            "has-file",
            Boolean(file)
        );
    };

    const updatePeriodFields = () => {
        if (
            !reportType
            || !periodEndField
            || !periodEndInput
        ) {
            return;
        }

        const normalizedValue = (
            reportType.value || ""
        )
            .trim()
            .replaceAll("-", "_")
            .toUpperCase();

        const selectedLabel = (
            reportType.options[
                reportType.selectedIndex
            ]?.textContent || ""
        ).trim();

        const isOpeningStock = (
            normalizedValue === "OPENING_STOCK"
            || normalizedValue === "OPENINGSTOCK"
            || selectedLabel.includes(
                "\u0627\u0644\u0645\u062e\u0632\u0648\u0646 "
                + "\u0627\u0644\u0627\u0641\u062a\u062a\u0627\u062d\u064a"
            )
        );

        periodEndField.classList.toggle(
            "is-hidden",
            isOpeningStock
        );

        periodEndField.hidden = isOpeningStock;
        periodEndInput.required = !isOpeningStock;
        periodEndInput.disabled = isOpeningStock;

        if (isOpeningStock) {
            periodEndInput.value = "";
        }

        if (periodStartLabel) {
            periodStartLabel.textContent = (
                isOpeningStock
                    ? "\u062a\u0627\u0631\u064a\u062e "
                      + "\u0627\u0644\u0645\u062e\u0632\u0648\u0646 "
                      + "\u0627\u0644\u0627\u0641\u062a\u062a\u0627\u062d\u064a"
                    : "\u0645\u0646 \u062a\u0627\u0631\u064a\u062e"
            );
        }
    };

    if (input) {
        input.addEventListener(
            "change",
            updateFilename
        );
    }

    if (reportType) {
        reportType.addEventListener(
            "change",
            updatePeriodFields
        );

        updatePeriodFields();
    }

    if (label) {
        ["dragenter", "dragover"].forEach(
            (eventName) => {
                label.addEventListener(
                    eventName,
                    (event) => {
                        event.preventDefault();

                        label.classList.add(
                            "is-dragging"
                        );
                    }
                );
            }
        );

        ["dragleave", "drop"].forEach(
            (eventName) => {
                label.addEventListener(
                    eventName,
                    () => {
                        label.classList.remove(
                            "is-dragging"
                        );
                    }
                );
            }
        );
    }

    const setupDynamicFormset = ({
        listSelector,
        addButtonSelector,
        templateSelector,
        totalFormsSelector,
        maxFormsSelector,
        rowSelector,
        removeButtonSelector,
        titleSelector,
    }) => {
        const formList = document.querySelector(
            listSelector
        );

        const addButton = document.querySelector(
            addButtonSelector
        );

        const emptyTemplate = document.querySelector(
            templateSelector
        );

        const totalForms = document.querySelector(
            totalFormsSelector
        );

        const maxFormsInput = document.querySelector(
            maxFormsSelector
        );

        const updateAddButton = () => {
            if (!addButton || !totalForms) {
                return;
            }

            const total = Number.parseInt(
                totalForms.value || "0",
                10
            );

            const configuredMax = Number.parseInt(
                maxFormsInput?.value || "20",
                10
            );

            const maxForms = Number.isFinite(
                configuredMax
            )
                ? configuredMax
                : 20;

            addButton.disabled = (
                total >= maxForms
            );
        };

        const markFormDeleted = (row) => {
            if (!row) {
                return;
            }

            const deleteInput = row.querySelector(
                'input[name$="-DELETE"]'
            );

            if (deleteInput) {
                deleteInput.checked = true;
            }

            row.hidden = true;
        };

        if (
            !formList
            || !addButton
            || !emptyTemplate
            || !totalForms
        ) {
            return;
        }

        addButton.addEventListener(
            "click",
            () => {
                const total = Number.parseInt(
                    totalForms.value || "0",
                    10
                );

                const configuredMax = Number.parseInt(
                    maxFormsInput?.value || "20",
                    10
                );

                const maxForms = Number.isFinite(
                    configuredMax
                )
                    ? configuredMax
                    : 20;

                if (total >= maxForms) {
                    updateAddButton();
                    return;
                }

                const html = (
                    emptyTemplate.innerHTML
                    .replaceAll(
                        "__prefix__",
                        String(total)
                    )
                );

                const wrapper = (
                    document.createElement("div")
                );

                wrapper.innerHTML = html.trim();

                const row = wrapper.firstElementChild;

                if (!row) {
                    return;
                }

                const title = row.querySelector(
                    titleSelector
                );

                if (title) {
                    title.textContent = (
                        "\u0645\u0644\u0641 "
                        + String(total + 1)
                    );
                }

                formList.appendChild(row);

                totalForms.value = String(
                    total + 1
                );

                updateAddButton();
            }
        );

        formList.addEventListener(
            "click",
            (event) => {
                const removeButton = (
                    event.target.closest(
                        removeButtonSelector
                    )
                );

                if (!removeButton) {
                    return;
                }

                const row = removeButton.closest(
                    rowSelector
                );

                markFormDeleted(row);
            }
        );

        updateAddButton();
    };

    setupDynamicFormset({
        listSelector: "#raw-form-list",
        addButtonSelector: "#raw-add-file",
        templateSelector: "#raw-empty-form-template",
        totalFormsSelector: "#id_raw-TOTAL_FORMS",
        maxFormsSelector: "#id_raw-MAX_NUM_FORMS",
        rowSelector: "[data-raw-form]",
        removeButtonSelector: ".raw-remove-file",
        titleSelector: "[data-raw-form-title]",
    });

    setupDynamicFormset({
        listSelector: "#sales-form-list",
        addButtonSelector: "#sales-add-file",
        templateSelector: "#sales-empty-form-template",
        totalFormsSelector: "#id_sales-TOTAL_FORMS",
        maxFormsSelector: "#id_sales-MAX_NUM_FORMS",
        rowSelector: "[data-sales-form]",
        removeButtonSelector: ".sales-remove-file",
        titleSelector: "[data-sales-form-title]",
    });
});

/* RAW_ITEMS_FILE_LABELS */
document.querySelectorAll(
    "#raw-items-form input[type='file'][multiple]"
).forEach((input) => {
    const label = document.querySelector(
        `[data-items-file-label="${input.id}"]`
    );

    if (!label) {
        return;
    }

    input.addEventListener("change", () => {
        const count = input.files
            ? input.files.length
            : 0;

        if (count === 0) {
            label.textContent =
                "\u0644\u0645 \u064a\u062a\u0645 \u0627\u062e\u062a\u064a\u0627\u0631 \u0623\u064a \u0645\u0644\u0641";
            return;
        }

        if (count === 1) {
            label.textContent =
                input.files[0].name;
            return;
        }

        label.textContent =
            "\u062a\u0645 \u0627\u062e\u062a\u064a\u0627\u0631 "
            + count
            + " \u0645\u0644\u0641\u0627\u062a";
    });
});

/* ACCOUNTANT_LOCALIZED_NATIVE_CONTROLS */
(function () {
    "use strict";

    const DATE_SELECTOR = [
        "#raw-chargement-form input[type='date']",
        "#raw-items-form input[type='date']",
        "#raw-sales-form input[type='date']",
    ].join(",");

    const FILE_SELECTOR = [
        "#raw-chargement-form input[type='file']",
        "#raw-sales-form input[type='file']",
    ].join(",");

    function installStyles() {
        if (
            document.getElementById(
                "accountant-localized-native-controls-style"
            )
        ) {
            return;
        }

        const style = document.createElement("style");

        style.id =
            "accountant-localized-native-controls-style";

        style.textContent = `
            .accountant-localized-date {
                position: relative;
                width: 100%;
                min-height: 40px;
            }

            .accountant-localized-date-display {
                display: flex;
                align-items: center;
                justify-content: space-between;
                box-sizing: border-box;
                width: 100%;
                min-height: 40px;
                pointer-events: none;
            }

            .accountant-localized-date-input {
                position: absolute;
                inset: 0;
                width: 100%;
                height: 100%;
                opacity: 0;
                cursor: pointer;
            }

            .accountant-localized-date-icon {
                flex: 0 0 auto;
                margin-inline-start: 0.5rem;
            }

            .accountant-localized-file {
                display: flex;
                align-items: center;
                gap: 0.75rem;
                flex-wrap: wrap;
            }

            .accountant-localized-file-input {
                display: none !important;
            }

            .accountant-localized-file-status {
                opacity: 0.85;
                overflow-wrap: anywhere;
            }
        `;

        document.head.appendChild(style);
    }

    function formatDate(value) {
        if (!value) {
            return "\u0627\u062e\u062a\u0631 \u0627\u0644\u062a\u0627\u0631\u064a\u062e";
        }

        const parts = value.split("-");

        if (parts.length !== 3) {
            return value;
        }

        return (
            parts[2]
            + "/"
            + parts[1]
            + "/"
            + parts[0]
        );
    }

    function enhanceDateInput(input) {
        if (
            input.dataset.accountantLocalizedDate
            === "1"
        ) {
            return;
        }

        input.dataset.accountantLocalizedDate = "1";

        const wrapper =
            document.createElement("div");

        wrapper.className =
            "accountant-localized-date";

        const display =
            document.createElement("div");

        display.className =
            "secondary-button "
            + "accountant-localized-date-display";

        display.setAttribute(
            "aria-hidden",
            "true"
        );

        const text =
            document.createElement("span");

        const icon =
            document.createElement("span");

        icon.className =
            "accountant-localized-date-icon";

        icon.textContent = "\uD83D\uDCC5";

        display.appendChild(text);
        display.appendChild(icon);

        input.parentNode.insertBefore(
            wrapper,
            input
        );

        wrapper.appendChild(display);
        wrapper.appendChild(input);

        input.classList.add(
            "accountant-localized-date-input"
        );

        function render() {
            text.textContent =
                formatDate(input.value);
        }

        input.addEventListener(
            "change",
            render
        );

        input.addEventListener(
            "input",
            render
        );

        render();
    }

    function fileButtonText(input) {
        const form = input.closest("form");

        if (
            form
            && form.id === "raw-chargement-form"
        ) {
            return (
                "\u0627\u062e\u062a\u064a\u0627\u0631 "
                + "\u0645\u0644\u0641 "
                + "\u0627\u0644\u062a\u062d\u0645\u064a\u0644"
            );
        }

        return (
            "\u0627\u062e\u062a\u064a\u0627\u0631 "
            + "\u0645\u0644\u0641 "
            + "\u0627\u0644\u0645\u0628\u064a\u0639\u0627\u062a"
        );
    }

    function enhanceFileInput(input) {
        if (
            input.dataset.accountantLocalizedFile
            === "1"
        ) {
            return;
        }

        input.dataset.accountantLocalizedFile = "1";

        const wrapper =
            document.createElement("div");

        wrapper.className =
            "accountant-localized-file";

        const button =
            document.createElement("label");

        button.className =
            "secondary-button";

        button.htmlFor = input.id;
        button.style.cursor = "pointer";

        button.textContent =
            fileButtonText(input);

        const status =
            document.createElement("span");

        status.className =
            "accountant-localized-file-status";

        input.parentNode.insertBefore(
            wrapper,
            input
        );

        wrapper.appendChild(input);
        wrapper.appendChild(button);
        wrapper.appendChild(status);

        input.classList.add(
            "accountant-localized-file-input"
        );

        function render() {
            const files = Array.from(
                input.files || []
            );

            if (files.length === 0) {
                status.textContent =
                    "\u0644\u0645 "
                    + "\u064a\u062a\u0645 "
                    + "\u0627\u062e\u062a\u064a\u0627\u0631 "
                    + "\u0623\u064a "
                    + "\u0645\u0644\u0641";
                return;
            }

            if (files.length === 1) {
                status.textContent =
                    files[0].name;
                return;
            }

            status.textContent =
                "\u062a\u0645 "
                + "\u0627\u062e\u062a\u064a\u0627\u0631 "
                + files.length
                + " "
                + "\u0645\u0644\u0641\u0627\u062a";
        }

        input.addEventListener(
            "change",
            render
        );

        render();
    }

    function matchesOrFind(root, selector) {
        const result = [];

        if (
            root.nodeType === 1
            && root.matches(selector)
        ) {
            result.push(root);
        }

        if (root.querySelectorAll) {
            result.push(
                ...root.querySelectorAll(selector)
            );
        }

        return result;
    }

    function enhanceRoot(root) {
        matchesOrFind(
            root,
            DATE_SELECTOR
        ).forEach(enhanceDateInput);

        matchesOrFind(
            root,
            FILE_SELECTOR
        ).forEach(enhanceFileInput);
    }

    function watchDynamicRows() {
        [
            document.querySelector(
                "#raw-form-list"
            ),
            document.querySelector(
                "#sales-form-list"
            ),
        ].forEach((list) => {
            if (!list) {
                return;
            }

            const observer =
                new MutationObserver(
                    (mutations) => {
                        mutations.forEach(
                            (mutation) => {
                                mutation.addedNodes
                                    .forEach(
                                        enhanceRoot
                                    );
                            }
                        );
                    }
                );

            observer.observe(
                list,
                {
                    childList: true,
                    subtree: true,
                }
            );
        });
    }

    function initialize() {
        installStyles();
        enhanceRoot(document);
        watchDynamicRows();
    }

    if (
        document.readyState === "loading"
    ) {
        document.addEventListener(
            "DOMContentLoaded",
            initialize
        );
    } else {
        initialize();
    }
}());
