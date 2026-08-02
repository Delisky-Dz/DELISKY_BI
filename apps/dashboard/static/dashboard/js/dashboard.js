(function () {
    "use strict";

    const body = document.body;
    const openButton = document.querySelector(
        "[data-sidebar-open]"
    );
    const closeButton = document.querySelector(
        "[data-sidebar-close]"
    );
    const overlay = document.querySelector(
        "[data-sidebar-overlay]"
    );
    const sidebarLinks = Array.from(
        document.querySelectorAll(
            ".sidebar__link"
        )
    );
    const sectionLinks = Array.from(
        document.querySelectorAll(
            '.sidebar__link[href^="#"]'
        )
    );
    const overviewLink = document.querySelector(
        ".sidebar__link--active"
    );

    function setSidebarOpen(isOpen) {
        body.classList.toggle(
            "sidebar-open",
            isOpen
        );

        if (openButton) {
            openButton.setAttribute(
                "aria-expanded",
                String(isOpen)
            );
        }
    }

    function setActiveLink(activeLink) {
        sidebarLinks.forEach(function (link) {
            const isActive = link === activeLink;

            link.classList.toggle(
                "sidebar__link--active",
                isActive
            );

            if (isActive) {
                link.setAttribute(
                    "aria-current",
                    "location"
                );
            } else {
                link.removeAttribute(
                    "aria-current"
                );
            }
        });
    }

    function getTarget(link) {
        const targetSelector = link.getAttribute(
            "href"
        );

        if (
            !targetSelector ||
            !targetSelector.startsWith("#")
        ) {
            return null;
        }

        return document.querySelector(
            targetSelector
        );
    }

    const availableSectionLinks = (
        sectionLinks.filter(function (link) {
            const target = getTarget(link);
            const listItem = link.closest("li");

            if (!target) {
                if (listItem) {
                    listItem.hidden = true;
                }

                return false;
            }

            return true;
        })
    );

    if (openButton) {
        openButton.addEventListener(
            "click",
            function () {
                setSidebarOpen(true);
            }
        );
    }

    if (closeButton) {
        closeButton.addEventListener(
            "click",
            function () {
                setSidebarOpen(false);
            }
        );
    }

    if (overlay) {
        overlay.addEventListener(
            "click",
            function () {
                setSidebarOpen(false);
            }
        );
    }

    sidebarLinks.forEach(function (link) {
        link.addEventListener(
            "click",
            function () {
                setSidebarOpen(false);
            }
        );
    });

    document.addEventListener(
        "keydown",
        function (event) {
            if (event.key === "Escape") {
                setSidebarOpen(false);
            }
        }
    );

    if (
        "IntersectionObserver" in window &&
        availableSectionLinks.length > 0
    ) {
        const linkByTargetId = new Map();

        availableSectionLinks.forEach(
            function (link) {
                const target = getTarget(link);

                if (target) {
                    linkByTargetId.set(
                        target.id,
                        link
                    );
                }
            }
        );

        const observer = new IntersectionObserver(
            function (entries) {
                const visibleEntries = entries
                    .filter(function (entry) {
                        return entry.isIntersecting;
                    })
                    .sort(function (first, second) {
                        return (
                            second.intersectionRatio -
                            first.intersectionRatio
                        );
                    });

                if (visibleEntries.length === 0) {
                    return;
                }

                const activeTarget = (
                    visibleEntries[0].target
                );
                const activeLink = (
                    linkByTargetId.get(
                        activeTarget.id
                    )
                );

                if (activeLink) {
                    setActiveLink(activeLink);
                }
            },
            {
                rootMargin: "-20% 0px -65% 0px",
                threshold: [
                    0,
                    0.1,
                    0.25,
                    0.5,
                ],
            }
        );

        linkByTargetId.forEach(
            function (link, targetId) {
                const target = document.getElementById(
                    targetId
                );

                if (target) {
                    observer.observe(target);
                }
            }
        );
    }

    window.addEventListener(
        "scroll",
        function () {
            if (
                window.scrollY < 180 &&
                overviewLink
            ) {
                setActiveLink(overviewLink);
            }
        },
        {
            passive: true,
        }
    );
})();


/* DELISKY THEME SWITCHER V1 */

(function () {
    "use strict";

    const storageKey = "delisky-dashboard-theme";

    const allowedPreferences = new Set([
        "light",
        "dark",
        "system",
    ]);

    const buttons = Array.from(
        document.querySelectorAll(
            "[data-theme-option]"
        )
    );

    const systemMedia = window.matchMedia(
        "(prefers-color-scheme: dark)"
    );

    function readPreference() {
        try {
            const stored = localStorage.getItem(
                storageKey
            );

            if (allowedPreferences.has(stored)) {
                return stored;
            }
        } catch (error) {
            return "system";
        }

        return "system";
    }

    function resolveTheme(preference) {
        if (preference === "system") {
            return systemMedia.matches
                ? "dark"
                : "light";
        }

        return preference;
    }

    function updateButtons(preference) {
        buttons.forEach(function (button) {
            const isActive = (
                button.dataset.themeOption === preference
            );

            button.classList.toggle(
                "theme-switcher__button--active",
                isActive
            );

            button.setAttribute(
                "aria-pressed",
                String(isActive)
            );
        });
    }

    function applyPreference(preference) {
        const safePreference = (
            allowedPreferences.has(preference)
                ? preference
                : "system"
        );

        const resolvedTheme = resolveTheme(
            safePreference
        );

        document.documentElement.setAttribute(
            "data-theme-preference",
            safePreference
        );

        document.documentElement.setAttribute(
            "data-theme",
            resolvedTheme
        );

        updateButtons(
            safePreference
        );
    }

    buttons.forEach(function (button) {
        button.addEventListener(
            "click",
            function () {
                const preference = (
                    button.dataset.themeOption
                );

                if (!allowedPreferences.has(preference)) {
                    return;
                }

                try {
                    localStorage.setItem(
                        storageKey,
                        preference
                    );
                } catch (error) {
                    // The theme still works for this page.
                }

                applyPreference(
                    preference
                );
            }
        );
    });

    systemMedia.addEventListener(
        "change",
        function () {
            if (readPreference() === "system") {
                applyPreference(
                    "system"
                );
            }
        }
    );

    window.addEventListener(
        "storage",
        function (event) {
            if (event.key === storageKey) {
                applyPreference(
                    readPreference()
                );
            }
        }
    );

    applyPreference(
        readPreference()
    );
})();



/* ASK DELISKY V1 */

(function () {
    "use strict";

    const assistants = Array.from(
        document.querySelectorAll(
            "[data-ask-delisky]"
        )
    );

    assistants.forEach(function (assistant) {
        const form = assistant.querySelector(
            "[data-ask-delisky-form]"
        );
        const submitButton = assistant.querySelector(
            "[data-ask-delisky-submit]"
        );
        const status = assistant.querySelector(
            "[data-ask-delisky-status]"
        );
        const answer = assistant.querySelector(
            "[data-ask-delisky-answer]"
        );
        const answerText = assistant.querySelector(
            "[data-ask-delisky-answer-text]"
        );
        const question = assistant.querySelector(
            "[data-ask-delisky-question]"
        );

        if (
            !form ||
            !submitButton ||
            !status ||
            !answer ||
            !answerText ||
            !question
        ) {
            return;
        }

        let submitting = false;

        function setBusy(isBusy) {
            submitting = isBusy;
            submitButton.disabled = isBusy;
            question.readOnly = isBusy;

            form.setAttribute(
                "aria-busy",
                String(isBusy)
            );
        }

        function showStatus(message, kind) {
            status.hidden = false;
            status.textContent = message;

            status.classList.toggle(
                "ask-delisky__status--error",
                kind === "error"
            );

            status.classList.toggle(
                "ask-delisky__status--success",
                kind === "success"
            );
        }

        function hideAnswer() {
            answer.hidden = true;
            answerText.textContent = "";
        }

        form.addEventListener(
            "submit",
            async function (event) {
                event.preventDefault();

                if (submitting) {
                    return;
                }

                if (!form.reportValidity()) {
                    return;
                }

                hideAnswer();
                setBusy(true);

                showStatus(
                    "\u062c\u0627\u0631\u064a \u062a\u062d\u0644\u064a\u0644 "
                    + "\u0627\u0644\u0645\u0624\u0634\u0631\u0627\u062a... "
                    + "\u0642\u062f \u064a\u0633\u062a\u063a\u0631\u0642 "
                    + "\u0630\u0644\u0643 \u0628\u0636\u0639 \u062b\u0648\u0627\u0646\u064d.",
                    "loading"
                );

                try {
                    const response = await fetch(
                        form.action,
                        {
                            method: "POST",
                            body: new FormData(form),
                            credentials: "same-origin",
                            headers: {
                                "X-Requested-With":
                                    "XMLHttpRequest",
                            },
                        }
                    );

                    let payload = null;

                    try {
                        payload = await response.json();
                    } catch (error) {
                        throw new Error(
                            "\u062a\u0639\u0630\u0631 \u0642\u0631\u0627\u0621\u0629 "
                            + "\u0631\u062f Ask DELISKY."
                        );
                    }

                    if (
                        !response.ok ||
                        !payload ||
                        payload.ok !== true
                    ) {
                        const message = (
                            payload &&
                            payload.error &&
                            payload.error.message
                        )
                            ? payload.error.message
                            : (
                                "\u062a\u0639\u0630\u0631 \u062a\u0646\u0641\u064a\u0630 "
                                + "\u0627\u0644\u0633\u0624\u0627\u0644 "
                                + "\u062d\u0627\u0644\u064a\u0627\u064b."
                            );

                        throw new Error(message);
                    }

                    if (
                        typeof payload.answer !== "string" ||
                        payload.answer.trim() === ""
                    ) {
                        throw new Error(
                            "\u0644\u0645 \u064a\u0635\u0644 \u0631\u062f "
                            + "\u0642\u0627\u0628\u0644 \u0644\u0644\u0639\u0631\u0636."
                        );
                    }

                    answerText.textContent = (
                        payload.answer
                    );
                    answer.hidden = false;

                    showStatus(
                        "\u0627\u0643\u062a\u0645\u0644 \u0627\u0644\u062a\u062d\u0644\u064a\u0644.",
                        "success"
                    );
                } catch (error) {
                    const message = (
                        error instanceof Error &&
                        error.message
                    )
                        ? error.message
                        : (
                            "\u062a\u0639\u0630\u0631 \u0627\u0644\u0627\u062a\u0635\u0627\u0644 "
                            + "\u0628\u0640 Ask DELISKY."
                        );

                    showStatus(
                        message,
                        "error"
                    );
                } finally {
                    setBusy(false);
                }
            }
        );
    });
})();
