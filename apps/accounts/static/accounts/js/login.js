document.addEventListener("DOMContentLoaded", () => {
    const toggle = document.querySelector(
        "[data-password-toggle]"
    );

    const password = document.querySelector(
        'input[name="password"]'
    );

    if (!toggle || !password) {
        return;
    }

    toggle.addEventListener("click", () => {
        const isVisible = password.type === "text";

        password.type = isVisible
            ? "password"
            : "text";

        toggle.textContent = isVisible
            ? "إظهار"
            : "إخفاء";

        toggle.setAttribute(
            "aria-label",
            isVisible
                ? "إظهار كلمة المرور"
                : "إخفاء كلمة المرور"
        );

        toggle.setAttribute(
            "aria-pressed",
            String(!isVisible)
        );
    });
});
