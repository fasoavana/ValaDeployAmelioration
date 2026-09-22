//scripts/components.js
// Charge un fragment HTML (composant) et l'injecte dans un placeholder.
// Usage : <div data-component="../components/sidebar.html"></div>
// Le lien de nav dont data-page correspond à document.body.dataset.page
// reçoit automatiquement le style "actif".

async function loadComponents() {
    const placeholders = document.querySelectorAll('[data-component]');

    await Promise.all(
        Array.from(placeholders).map(async (placeholder) => {
            const path = placeholder.getAttribute('data-component');
            try {
                const response = await fetch(path);
                if (!response.ok) throw new Error(`Impossible de charger ${path}`);
                placeholder.outerHTML = await response.text();
            } catch (error) {
                console.error('Erreur de chargement de composant :', error);
            }
        })
    );

    highlightActiveNavLink();
}

function highlightActiveNavLink() {
    const currentPage = document.body.dataset.page;
    if (!currentPage) return;

    document.querySelectorAll('.nav-link').forEach((link) => {
        if (link.dataset.page !== currentPage) return;

        link.classList.remove('text-on-surface-variant', 'opacity-70');
        link.classList.add('text-on-surface', 'font-semibold', 'bg-surface-container-high');

        const iconWrap = link.querySelector('.nav-icon-wrap');
        if (iconWrap) {
            iconWrap.classList.add('bg-primary');
            const icon = iconWrap.querySelector('.material-symbols-outlined');
            if (icon) icon.classList.add('text-on-primary');
        }
    });
}

document.addEventListener('DOMContentLoaded', loadComponents);