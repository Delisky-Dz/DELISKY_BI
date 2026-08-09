
document.addEventListener("DOMContentLoaded", () => {

    const header = document.querySelector(".site-header");
    const toggle = document.querySelector(".menu-toggle");
    const nav = document.querySelector(".main-nav");

    const links = [
        ...document.querySelectorAll(
            '.main-nav a[href^="#"]'
        )
    ];


    function updateHeader() {
        if (!header) return;

        header.classList.toggle(
            "is-scrolled",
            window.scrollY > 15
        );
    }


    function updateActiveLink() {

        let current = "";

        for (const link of links) {

            const selector =
                link.getAttribute("href");

            const section =
                document.querySelector(selector);

            if (!section) continue;

            const rect =
                section.getBoundingClientRect();

            if (rect.top <= 150) {
                current = selector;
            }
        }

        for (const link of links) {

            const active =
                link.getAttribute("href")
                === current;

            link.classList.toggle(
                "active",
                active
            );

            if (active) {
                link.setAttribute(
                    "aria-current",
                    "page"
                );
            } else {
                link.removeAttribute(
                    "aria-current"
                );
            }
        }
    }


    if (toggle && nav) {

        toggle.addEventListener(
            "click",
            () => {

                const open =
                    nav.classList.toggle(
                        "open"
                    );

                toggle.setAttribute(
                    "aria-expanded",
                    String(open)
                );

            }
        );

    }


    for (const link of links) {

        link.addEventListener(
            "click",
            () => {

                if (nav) {
                    nav.classList.remove(
                        "open"
                    );
                }

                if (toggle) {
                    toggle.setAttribute(
                        "aria-expanded",
                        "false"
                    );
                }

            }
        );

    }


    let ticking = false;

    window.addEventListener(
        "scroll",
        () => {

            if (ticking) return;

            ticking = true;

            window.requestAnimationFrame(
                () => {

                    updateHeader();
                    updateActiveLink();

                    ticking = false;

                }
            );

        },
        { passive: true }
    );


    updateHeader();
    updateActiveLink();

});
