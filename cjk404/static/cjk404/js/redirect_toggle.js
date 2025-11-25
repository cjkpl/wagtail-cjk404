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

    async function toggleRedirect(trigger) {
        const url = trigger.dataset.cjk404ToggleUrl;
        if (!url) {
            return;
        }
        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken') || '',
                    Accept: 'application/json',
                },
            });
            if (!response.ok) {
                throw new Error(`Toggle Failed (${response.status})`);
            }
            const data = await response.json();
            if (!data || data.ok !== true) {
                throw new Error('Toggle Failed');
            }
            const targetSelector = data.target_selector || trigger.dataset.cjk404ReplaceSelector;
            if (targetSelector && data.badge_html) {
                replaceWithHtml(targetSelector, data.badge_html);
            }
        } catch (error) {
            /* eslint-disable no-console */
            console.error(error);
            /* eslint-enable no-console */
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

    document.addEventListener('mouseover', (event) => {
        const trigger = event.target.closest('[data-cjk404-toggle-url]');
        if (trigger) {
            trigger.style.opacity = '0.7';
        }
    });

    document.addEventListener('mouseout', (event) => {
        const trigger = event.target.closest('[data-cjk404-toggle-url]');
        if (trigger) {
            trigger.style.opacity = '';
        }
    });
})();
