//scripts/login.js
document.addEventListener('DOMContentLoaded', () => {
  const form = document.querySelector('form');
  const email = document.getElementById('email');
  const password = document.getElementById('password');
  const submitButton = form.querySelector('button[type="submit"]');
  const originalButtonText = submitButton.textContent;

  if (!form || !password) return;

  form.addEventListener('submit', async (event) => {
    event.preventDefault();

    submitButton.disabled = true;
    submitButton.textContent = "Signing in...";

    try {
      // 1. Connexion
      const data = await loginUser(email.value, password.value);
      console.log('Login successful:', data);

      // 2. Récupère immédiatement le profil utilisateur
      const user = await getCurrentUser(currentAccessToken);

      // 3. Redirige selon le flag must_change_password
      if (user.must_change_password) {
        console.log("Nouvel admin détecté : redirection vers account.html");
        window.location.href = "account.html";
      } else {
        console.log("Utilisateur standard : redirection vers dashboard.html");
        window.location.href = "dashboard.html";
      }

    } catch (error) {
      console.error('Login error:', error);
      
      // Utilise ValaToast pour la cohérence UX (au lieu de alert)
      const errorMsg = error.message || "Failed to log in. Please check your credentials.";
      
      // Vérifie si ValaToast est disponible
      if (typeof ValaToast !== 'undefined' && ValaToast.show) {
        ValaToast.show(errorMsg, "error");
      } else {
        alert(errorMsg); // Fallback si ValaToast n'est pas chargé
      }

      submitButton.disabled = false;
      submitButton.textContent = originalButtonText;
    }
  });
});