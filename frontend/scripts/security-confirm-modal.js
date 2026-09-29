// scripts/security-confirm-modal.js
// Popup de confirmation affiché quand le pipeline détecte une faille CRITICAL
// patchable (statut AWAITING_CONFIRMATION). Countdown purement visuel : le vrai
// blocage après 10s est géré côté backend (wait_for_decision), pas ici.
// Dépend de vuln-render.js (doit être chargé avant ce script).

const SecurityConfirmModal = (() => {
    let countdownInterval = null;

    function show({ vulnCount, vulnerabilities, slug, onConfirm, onReject }) {
        const modal = document.getElementById('security-confirm-modal');
        if (!modal) return;

        const countEl = document.getElementById('security-modal-vuln-count');
        if (countEl) countEl.textContent = vulnCount;

        const listEl = document.getElementById('security-modal-vuln-list');
        if (listEl && typeof renderVulnerabilityList === 'function') {
            renderVulnerabilityList(listEl, vulnerabilities);
        }

        // Countdown visuel (10s), indépendant du timeout réel côté backend
        let remaining = 10;
        const countdownEl = document.getElementById('security-modal-countdown');
        if (countdownEl) countdownEl.textContent = remaining;

        clearInterval(countdownInterval);
        countdownInterval = setInterval(() => {
            remaining -= 1;
            if (countdownEl) countdownEl.textContent = Math.max(remaining, 0);
            if (remaining <= 0) {
                clearInterval(countdownInterval);
                hide();
                // Pas d'appel réseau ici : le backend gère déjà son propre timeout
                // côté pipeline (wait_for_decision). On ferme juste l'UI.
            }
        }, 1000);

        // On clone les boutons à chaque show() pour repartir sans aucun listener
        // accroché d'un affichage précédent (évite les doubles appels si la modale
        // a déjà été fermée par timeout une première fois pour un autre run).
        const oldConfirm = document.getElementById('security-modal-confirm');
        const oldCancel = document.getElementById('security-modal-cancel');
        const btnConfirm = oldConfirm.cloneNode(true);
        const btnCancel = oldCancel.cloneNode(true);
        oldConfirm.replaceWith(btnConfirm);
        oldCancel.replaceWith(btnCancel);

        btnConfirm.addEventListener('click', async () => {
            btnConfirm.disabled = true;
            btnCancel.disabled = true;
            try {
                if (onConfirm) await onConfirm();
            } finally {
                hide();
            }
        });

        btnCancel.addEventListener('click', async () => {
            btnConfirm.disabled = true;
            btnCancel.disabled = true;
            try {
                if (onReject) await onReject();
            } finally {
                hide();
            }
        });

        modal.classList.remove('hidden');
        modal.classList.add('flex');
    }

    function hide() {
        const modal = document.getElementById('security-confirm-modal');
        if (!modal) return;
        modal.classList.add('hidden');
        modal.classList.remove('flex');
        clearInterval(countdownInterval);
    }

    return { show, hide };
})();