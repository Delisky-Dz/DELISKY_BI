document.addEventListener("DOMContentLoaded", () => {
    const button = document.querySelector(".menu-toggle");
    const navigation = document.querySelector(".main-nav");

    if (!button || !navigation) {
        return;
    }

    button.addEventListener("click", () => {
        const isOpen = navigation.classList.toggle("open");
        button.setAttribute("aria-expanded", String(isOpen));
    });

    navigation.querySelectorAll("a").forEach((link) => {
        link.addEventListener("click", () => {
            navigation.classList.remove("open");
            button.setAttribute("aria-expanded", "false");
        });
    });
});
