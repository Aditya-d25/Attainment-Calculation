/**
 * Clean & Minimalist Login Gateway Client Logic
 * Handles Google Login button and Demo Login button.
 */

document.addEventListener("DOMContentLoaded", () => {
  initCardTilt();
  initAuthButtons();
});

// Toast notification helper
function showToast(message, type = "info") {
  const toast = document.getElementById("login-toast");
  const toastMsg = document.getElementById("toast-message");
  if (!toast || !toastMsg) return;

  toastMsg.textContent = message;
  toast.className = `glass-toast ${type} show`;

  clearTimeout(window._toastTimeout);
  window._toastTimeout = setTimeout(() => {
    toast.className = `glass-toast ${type}`;
  }, 3500);
}

/**
 * Subtle 3D Glass Tilt Effect on Mouse Move
 */
function initCardTilt() {
  const card = document.getElementById("glass-login-card");
  const viewport = document.getElementById("login-viewport");
  if (!card || !viewport) return;

  if (window.matchMedia("(pointer: coarse)").matches) return;

  viewport.addEventListener("mousemove", (e) => {
    const rect = card.getBoundingClientRect();
    const cardCenterX = rect.left + rect.width / 2;
    const cardCenterY = rect.top + rect.height / 2;

    const mouseX = e.clientX - cardCenterX;
    const mouseY = e.clientY - cardCenterY;

    const rotateX = -(mouseY / (rect.height / 2)) * 3.5;
    const rotateY = (mouseX / (rect.width / 2)) * 3.5;

    card.style.transform = `perspective(1000px) rotateX(${rotateX.toFixed(2)}deg) rotateY(${rotateY.toFixed(2)}deg)`;
  });

  viewport.addEventListener("mouseleave", () => {
    card.style.transform = "perspective(1000px) rotateX(0deg) rotateY(0deg)";
  });
}

/**
 * Initialize Google & Demo Login Handlers
 */
function initAuthButtons() {
  const googleBtn = document.getElementById("btn-google-login");
  const demoBtn = document.getElementById("btn-demo-login");
  const googleClientId = window.GOOGLE_CLIENT_ID || "";

  // 1. Google Identity Services (GIS) if client id configured
  if (googleClientId && typeof google !== "undefined" && google.accounts) {
    try {
      google.accounts.id.initialize({
        client_id: googleClientId,
        callback: handleGoogleCredentialResponse,
        auto_select: false,
      });

      const container = document.getElementById("google-signin-btn-container");
      if (container) {
        google.accounts.id.renderButton(container, {
          theme: "outline",
          size: "large",
          shape: "rectangular",
          text: "signin_with",
          width: 380,
        });
      }
    } catch (err) {
      console.warn("Could not initialize Google Identity Services:", err);
    }
  }

  // 2. Google Button Click
  if (googleBtn) {
    googleBtn.addEventListener("click", async () => {
      if (googleClientId && typeof google !== "undefined" && google.accounts) {
        try {
          google.accounts.id.prompt();
          return;
        } catch (e) {
          console.warn("GIS prompt error, proceeding with fallback", e);
        }
      }

      // If GOOGLE_CLIENT_ID not set or offline, log in directly as Google User
      await executeLogin({
        email: "google.user@college.edu.in",
        name: "Google User",
        role: "Faculty Member",
        picture: "https://api.dicebear.com/7.x/initials/svg?seed=Google+User&backgroundColor=1b6348",
      });
    });
  }

  // 3. Demo Login Button Click
  if (demoBtn) {
    demoBtn.addEventListener("click", async () => {
      const originalText = demoBtn.innerHTML;
      demoBtn.innerHTML = `
        <span class="glass-spinner"></span>
        <span>Signing in...</span>
      `;
      demoBtn.disabled = true;

      await executeLogin({
        email: "faculty.demo@college.edu.in",
        name: "Demo Faculty",
        role: "Course Faculty & Evaluator",
        picture: "https://api.dicebear.com/7.x/initials/svg?seed=Demo+Faculty&backgroundColor=1b6348",
      });

      demoBtn.innerHTML = originalText;
      demoBtn.disabled = false;
    });
  }
}

/**
 * Google Credential Handler (Triggered by Google Identity Services JWT)
 */
async function handleGoogleCredentialResponse(response) {
  if (!response || !response.credential) {
    showToast("Google login did not return a valid credential.", "error");
    return;
  }

  showToast("Verifying Google account...", "info");

  try {
    const res = await fetch("/api/auth/google", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ credential: response.credential }),
    });

    const data = await res.json();
    if (res.ok && data.success) {
      showToast(`Welcome back, ${data.user.name}! Opening dashboard...`, "success");
      setTimeout(() => {
        window.location.href = "/";
      }, 500);
    } else {
      showToast(data.detail || "Authentication failed.", "error");
    }
  } catch (err) {
    showToast("Network error during Google authentication.", "error");
    console.error(err);
  }
}

/**
 * Execute Login Session Request
 */
async function executeLogin(profile) {
  showToast("Signing in...", "info");

  try {
    const res = await fetch("/api/auth/demo-login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(profile),
    });

    const data = await res.json();
    if (res.ok && data.success) {
      showToast(`Welcome back, ${data.user.name}! Opening dashboard...`, "success");
      setTimeout(() => {
        window.location.href = "/";
      }, 450);
    } else {
      showToast(data.detail || "Sign-in failed. Please try again.", "error");
    }
  } catch (err) {
    showToast("Network error. Please check server connection.", "error");
    console.error(err);
  }
}
