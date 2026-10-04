(function () {
    "use strict";

    const template = document.getElementById(
        "manager-navigation-template"
    );
    const sidebarNav = document.querySelector(
        ".sidebar__nav"
    );

    if (!template || !sidebarNav) {
        return;
    }

    const fragment = template.content.cloneNode(true);
    sidebarNav.replaceChildren(fragment);

    const groups = Array.from(
        sidebarNav.querySelectorAll(
            ".manager-navigation__group"
        )
    );

    function setGroupOpen(group, isOpen) {
        group.classList.toggle(
            "manager-navigation__group--open",
            isOpen
        );

        const toggle = group.querySelector(
            "[data-manager-nav-toggle]"
        );

        if (toggle) {
            toggle.setAttribute(
                "aria-expanded",
                String(isOpen)
            );
        }
    }

    groups.forEach(function (group) {
        const toggle = group.querySelector(
            "[data-manager-nav-toggle]"
        );

        if (!toggle) {
            return;
        }

        toggle.addEventListener(
            "click",
            function () {
                const willOpen = !group.classList.contains(
                    "manager-navigation__group--open"
                );

                groups.forEach(function (otherGroup) {
                    if (otherGroup !== group) {
                        setGroupOpen(
                            otherGroup,
                            false
                        );
                    }
                });

                setGroupOpen(
                    group,
                    willOpen
                );
            }
        );
    });

    sidebarNav.addEventListener(
        "click",
        function (event) {
            const link = event.target.closest("a");

            if (!link) {
                return;
            }

            document.body.classList.remove(
                "sidebar-open"
            );

            const openButton = document.querySelector(
                "[data-sidebar-open]"
            );

            if (openButton) {
                openButton.setAttribute(
                    "aria-expanded",
                    "false"
                );
            }
        }
    );
})();
