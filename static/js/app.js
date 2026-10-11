/* ============================================================
   PERCEPTION MAROVOAY — Interactions
   ============================================================ */
(function () {
    'use strict';

    var prefersReducedMotion =
        window.matchMedia &&
        window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // ---------------------------------------------
    // 1. Toasts : fermeture + auto-dismiss ciblé
    // ---------------------------------------------
    document.querySelectorAll('.toast').forEach(function (toast) {
        // Bouton fermer
        var closeBtn = toast.querySelector('.toast__close');
        if (closeBtn) {
            closeBtn.addEventListener('click', function () {
                removeToast(toast);
            });
        }

        // Auto-dismiss uniquement pour success et info
        var tag = toast.dataset.autodismiss || '';
        if (tag === 'success' || tag === 'info') {
            setTimeout(function () {
                removeToast(toast);
            }, 5000);
        }
    });

    function removeToast(toast) {
        if (prefersReducedMotion) {
            toast.remove();
            return;
        }
        toast.style.transition = 'opacity .25s, transform .25s';
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(20px)';
        setTimeout(function () { toast.remove(); }, 260);
    }

    // ---------------------------------------------
    // 2. Confirmation sur form[data-confirm]
    // ---------------------------------------------
    document.querySelectorAll('form[data-confirm]').forEach(function (form) {
        form.addEventListener('submit', function (e) {
            if (!window.confirm(form.getAttribute('data-confirm'))) {
                e.preventDefault();
            }
        });
    });

    // ---------------------------------------------
    // 3. Loading state sur boutons de soumission
    // ---------------------------------------------
    document.querySelectorAll('form').forEach(function (form) {
        form.addEventListener('submit', function () {
            var btn = form.querySelector('button[type="submit"]:not([formaction]):not([data-no-loading])');
            if (!btn || btn.disabled) return;
            btn.style.opacity = '0.75';
            btn.style.pointerEvents = 'none';
            var originalText = btn.innerHTML;
            btn.dataset.originalHtml = originalText;
            btn.innerHTML = '<span>Traitement…</span>';
            // Filet de sécurité : restaurer après 8 s
            setTimeout(function () {
                if (btn.dataset.originalHtml) {
                    btn.innerHTML = btn.dataset.originalHtml;
                    btn.style.opacity = '';
                    btn.style.pointerEvents = '';
                }
            }, 8000);
        });
    });

    // ---------------------------------------------
    // 4. Fermer le menu utilisateur au clic extérieur
    // ---------------------------------------------
    document.querySelectorAll('.user-menu[open]').forEach(function (details) {
        document.addEventListener('click', function handler(e) {
            if (!details.contains(e.target)) {
                details.removeAttribute('open');
                document.removeEventListener('click', handler);
            }
        });
    });

    // ---------------------------------------------
    // 5. Auto-submit des filtres select (optionnel)
    // ---------------------------------------------
    document.querySelectorAll('.filters select[data-autosubmit]').forEach(function (sel) {
        sel.addEventListener('change', function () {
            var form = sel.closest('form');
            if (form) form.submit();
        });
    });

})();
