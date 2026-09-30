(function () {
    "use strict";

    var timers = new Map();

    function renderIcons() {
        if (window.lucide) window.lucide.createIcons();
    }

    function clearTimer(container) {
        var timer = timers.get(container);
        if (timer !== undefined) {
            window.clearTimeout(timer);
            timers.delete(container);
        }
    }

    function hideSecret(container) {
        if (!container || !container.matches("[data-client-secret-revealed]")) return;

        var template = container.querySelector("[data-client-secret-masked-template]");
        if (!template || !template.content.firstElementChild) return;

        clearTimer(container);
        var masked = template.content.firstElementChild.cloneNode(true);
        container.replaceWith(masked);
        if (window.htmx) window.htmx.process(masked);
        renderIcons();
    }

    function initialize(container) {
        if (!container.matches("[data-client-secret-revealed]") || timers.has(container)) return;

        var delay = Number.parseInt(container.dataset.autoHideMs || "30000", 10);
        if (!Number.isFinite(delay) || delay < 0) delay = 30000;
        timers.set(container, window.setTimeout(function () {
            hideSecret(container);
        }, delay));
    }

    function initializeWithin(root) {
        if (root instanceof Element && root.matches("[data-client-secret-revealed]")) {
            initialize(root);
        }
        if (root.querySelectorAll) {
            root.querySelectorAll("[data-client-secret-revealed]").forEach(initialize);
        }
    }

    document.addEventListener("click", function (event) {
        var target = event.target;
        if (!(target instanceof Element)) return;

        var hideButton = target.closest("[data-client-secret-hide]");
        if (hideButton) {
            hideSecret(hideButton.closest("[data-client-secret-container]"));
            return;
        }

        var copyButton = target.closest("[data-client-secret-copy]");
        if (!copyButton) return;

        var container = copyButton.closest("[data-client-secret-container]");
        var value = container && container.querySelector("[data-client-secret-value]");
        if (!value) return;

        navigator.clipboard.writeText(value.textContent || "").then(function () {
            copyButton.textContent = "Copied";
        }).catch(function () {
            copyButton.textContent = "Could not copy";
        });
    });

    document.body.addEventListener("htmx:afterSwap", function () {
        initializeWithin(document);
        renderIcons();
    });

    document.addEventListener("visibilitychange", function () {
        if (!document.hidden) return;
        Array.from(timers.keys()).forEach(hideSecret);
    });

    initializeWithin(document);
    renderIcons();
}());
