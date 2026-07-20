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
