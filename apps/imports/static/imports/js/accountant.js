document.addEventListener("DOMContentLoaded", () => {
    const input = document.querySelector(
        ".accountant-file-input"
    );

    const label = document.querySelector(
        ".drop-zone"
    );

    const filename = document.querySelector(
        "#selected-file-name"
    );

    if (!input || !label || !filename) {
        return;
    }

    const updateFilename = () => {
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

    input.addEventListener(
        "change",
        updateFilename
    );

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
});
