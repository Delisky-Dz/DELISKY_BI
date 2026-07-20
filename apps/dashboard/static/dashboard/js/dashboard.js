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
    const sidebarLinks = document.querySelectorAll(
        ".sidebar__link"
    );

    if (!openButton) {
        return;
    }

    function setSidebarOpen(isOpen) {
        body.classList.toggle(
            "sidebar-open",
            isOpen
        );

        openButton.setAttribute(
            "aria-expanded",
            String(isOpen)
        );
    }

    openButton.addEventListener(
        "click",
        function () {
            setSidebarOpen(true);
        }
    );

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
})();
