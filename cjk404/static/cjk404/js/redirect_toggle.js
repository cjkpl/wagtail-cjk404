(function () {
    function getCookie(name) {
        const cookies = document.cookie ? document.cookie.split('; ') : [];
        for (let i = 0; i < cookies.length; i += 1) {
            const [key, value] = cookies[i].split('=');
            if (key === name) {
                return decodeURIComponent(value);
            }
        }
        return null;
    }

    function replaceWithHtml(selector, html) {
        if (!html) {
            return;
        }
        const existing = document.querySelector(selector);
        if (!existing) {
            return;
        }
        const template = document.createElement('template');
        template.innerHTML = html.trim();
        const replacement = template.content.firstElementChild;
        if (replacement) {
            existing.replaceWith(replacement);
        }
    }

    async function toggleRedirect(button) {
        const url = button.dataset.cjk404ToggleUrl;
        const pk = button.dataset.cjk404Target;
        if (!url || !pk) {
            return;
        }
        button.disabled = true;
        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken') || '',
                    Accept: 'application/json',
                },
            });
            if (!response.ok) {
                throw new Error(`Toggle failed (${response.status})`);
            }
            const data = await response.json();
            if (!data || data.ok !== true) {
                throw new Error('Toggle failed');
            }
            replaceWithHtml(
                `[data-cjk404-active-indicator="${pk}"]`,
                data.badge_html,
            );
            replaceWithHtml(`[data-cjk404-toggle-button="${pk}"]`, data.button_html);
        } catch (error) {
            /* eslint-disable no-console */
            console.error(error);
            /* eslint-enable no-console */
            button.disabled = false;
        }
    }

    document.addEventListener('click', (event) => {
        const trigger = event.target.closest('[data-cjk404-toggle-url]');
        if (!trigger) {
            return;
        }
        event.preventDefault();
        toggleRedirect(trigger);
    });
})();
