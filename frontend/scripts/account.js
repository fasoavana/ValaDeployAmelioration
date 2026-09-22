//scripts/account.js

document.addEventListener("DOMContentLoaded", () => {
  const logoutBtn = document.getElementById("btn-logout-everywhere");
  const deleteBtn = document.getElementById("btn-delete-account");

  // Remplit les infos du compte + calcule le temps restant de la session
  initUserSession(
    (user, accessToken) => {
      if (user.must_change_password) {
        console.warn("Password change required.");
        
        // Masque les sections profil et danger zone
        const profileSection = document.querySelector("section:has(#profile-fullname)");
        const dangerZoneSection = document.querySelector("section:has(#btn-delete-account)");
        
        if (profileSection) profileSection.style.display = "none";
        if (dangerZoneSection) dangerZoneSection.style.display = "none";
        
        // Optionnel : ajoute un message d'alerte en haut
        const mainHeader = document.querySelector("header");
        if (mainHeader && !document.getElementById("password-change-alert")) {
          const alertDiv = document.createElement("div");
          alertDiv.id = "password-change-alert";
          alertDiv.className = "bg-warning-yellow/20 border border-warning-yellow text-primary-dark px-lg py-md rounded-lg mb-xl";
          alertDiv.innerHTML = `
            <div class="flex items-center gap-sm">
              <span class="material-symbols-outlined text-warning-yellow">warning</span>
              <p class="font-body-md text-body-md">
                <strong>Security:</strong> You must change your password before continuing.
              </p>
            </div>
          `;
          mainHeader.after(alertDiv);
        }
        
        // Passe à la gestion du formulaire de changement de mot de passe
        setupPasswordChangeForm(accessToken);
        return;
      }
      const fullnameEl = document.getElementById('profile-fullname');
      const emailEl = document.getElementById('profile-email');
      const roleEl = document.getElementById('profile-role');
      const expiryEl = document.getElementById('session-expiry-text');

      if (fullnameEl) fullnameEl.textContent = user.full_name;
      if (emailEl) emailEl.textContent = user.email;
      if (roleEl) roleEl.textContent = user.role;

      if (expiryEl) {
        const payload = decodeJwt(accessToken);
        expiryEl.textContent = formatTimeRemaining(payload.exp);
      }
    },
    (error) => {
      console.log('Session invalide ou expirée :', error.message);
      window.location.href = "login.html";
    }
  );

  if (logoutBtn) {
    logoutBtn.addEventListener("click", async () => {
      const confirmed = await ValaModal.confirm({
        title: "Logout",
        message: "This will end your current session. Continue?",
        confirmLabel: "Logout",
        cancelLabel: "Cancel",
        variant: "default"
      });
      if (confirmed) {
        logoutUser()
          .then(() => {
            window.location.href = "login.html";
          })
          .catch(error => {
            ValaToast.show({ type: 'error', title: 'Error', message: error.message });
          });
      }
    });
  }

  if (deleteBtn) {
    deleteBtn.addEventListener("click", async () => {
      const confirmed = await ValaModal.confirm({
        title: "Delete Account",
        message: "This action is permanent and cannot be undone. All your data will be permanently deleted.",
        confirmLabel: "Delete Account",
        cancelLabel: "Cancel",
        variant: "danger"
      });
      if (confirmed) {
        // TODO: appel API réel de suppression de compte (pas encore implémenté côté backend)
        console.log("Account deletion requested.");
      }
    });
  }
});

// Fonction dédiée au formulaire de changement de mot de passe
function setupPasswordChangeForm(accessToken) {
  const submitBtn = document.querySelector("section:has(#current_password) button");
  const currentPasswordInput = document.getElementById("current_password");
  const newPasswordInput = document.getElementById("new_password");
  const confirmPasswordInput = document.getElementById("confirm_password");

  if (submitBtn) {
    submitBtn.addEventListener("click", async () => {
      const oldPass = currentPasswordInput.value;
      const newPass = newPasswordInput.value;
      const confirmPass = confirmPasswordInput.value;

      // Validations
      if (!oldPass || !newPass || !confirmPass) {
        ValaToast.show({ type: 'error', title: 'Missing Fields', message: "Please fill in all fields." });
        return;
      }

      if (newPass !== confirmPass) {
        ValaToast.show({ type: 'error', title: 'Error', message: "Passwords do not match." });
        return;
      }

      if (newPass.length < 8) {
        ValaToast.show({ type: 'error', title: 'Error', message: "Password must be at least 8 characters long." });
        return;
      }

      // Feedback visuel
      const originalText = submitBtn.textContent;
      submitBtn.disabled = true;
      submitBtn.textContent = "Updating...";

      try {
        await changePassword(oldPass, newPass);
        
        ValaToast.show({ type: 'success', title: 'Success', message: "Password changed successfully!" });

        
        // Recharge la page pour réafficher tout le profil
        setTimeout(() => {
          window.location.reload();
        }, 1500);
        
      } catch (error) {
        ValaToast.show({ type: 'error', title: 'Error', message: error.message || "Error occurred while changing password" });

        submitBtn.disabled = false;
        submitBtn.textContent = originalText;
      }
    });
  }
}


// Transforme un "exp" (timestamp Unix, en secondes) en texte lisible du style "Expires in 42 min"
function formatTimeRemaining(expTimestamp) {
  const nowInSeconds = Math.floor(Date.now() / 1000); // Date.now() donne des millisecondes, on convertit en secondes
  const secondsRemaining = expTimestamp - nowInSeconds;

  if (secondsRemaining <= 0) {
    return "Expired";
  }

  const minutesRemaining = Math.floor(secondsRemaining / 60);

  if (minutesRemaining < 60) {
    return `Expires in ${minutesRemaining} min`;
  }

  const hoursRemaining = Math.floor(minutesRemaining / 60);
  return `Expires in ${hoursRemaining}h`;
}