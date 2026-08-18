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

    const rawFormList = document.querySelector(
        "#raw-form-list"
    );

    const rawAddFileButton = document.querySelector(
        "#raw-add-file"
    );

    const rawEmptyTemplate = document.querySelector(
        "#raw-empty-form-template"
    );

    const rawTotalForms = document.querySelector(
        "#id_raw-TOTAL_FORMS"
    );

    const rawMaxForms = document.querySelector(
        "#id_raw-MAX_NUM_FORMS"
    );

    const updateRawAddButton = () => {
        if (
            !rawAddFileButton
            || !rawTotalForms
        ) {
            return;
        }

        const total = Number.parseInt(
            rawTotalForms.value || "0",
            10
        );

        const configuredMax = Number.parseInt(
            rawMaxForms?.value || "20",
            10
        );

        const maxForms = Number.isFinite(
            configuredMax
        )
            ? configuredMax
            : 20;

        rawAddFileButton.disabled = (
            total >= maxForms
        );
    };

    const markRawFormDeleted = (row) => {
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
        rawFormList
        && rawAddFileButton
        && rawEmptyTemplate
        && rawTotalForms
    ) {
        rawAddFileButton.addEventListener(
            "click",
            () => {
                const total = Number.parseInt(
                    rawTotalForms.value || "0",
                    10
                );

                const configuredMax = Number.parseInt(
                    rawMaxForms?.value || "20",
                    10
                );

                const maxForms = Number.isFinite(
                    configuredMax
                )
                    ? configuredMax
                    : 20;

                if (total >= maxForms) {
                    updateRawAddButton();
                    return;
                }

                const html = (
                    rawEmptyTemplate.innerHTML
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
                    "[data-raw-form-title]"
                );

                if (title) {
                    title.textContent = (
                        "ملف "
                        + String(total + 1)
                    );
                }

                rawFormList.appendChild(row);

                rawTotalForms.value = String(
                    total + 1
                );

                updateRawAddButton();
            }
        );

        rawFormList.addEventListener(
            "click",
            (event) => {
                const removeButton = (
                    event.target.closest(
                        ".raw-remove-file"
                    )
                );

                if (!removeButton) {
                    return;
                }

                const row = removeButton.closest(
                    "[data-raw-form]"
                );

                markRawFormDeleted(row);
            }
        );

        updateRawAddButton();
    }
});
