/* auth-effects.js — تفاعلات صفحة الدخول: جزيئات ذهبية، اختلاف منظر خفيف،
   إظهار كلمة المرور، وتذكّر بيانات المؤسسة/البريد (دون كلمة المرور). */
(function () {
  "use strict";

  var reduceMotion = false;
  try { reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch (e) { /* ignore */ }

  /* ------------------------------------------------------------------
     إظهار / إخفاء كلمة المرور
     ------------------------------------------------------------------ */
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-toggle-password]");
    if (!btn) return;
    var input = document.getElementById(btn.getAttribute("data-toggle-password"));
    if (!input) return;
    var willShow = input.type === "password";
    input.type = willShow ? "text" : "password";
    btn.setAttribute("aria-pressed", String(willShow));
    btn.setAttribute("aria-label", willShow ? "إخفاء كلمة المرور" : "إظهار كلمة المرور");
    var open = btn.querySelector(".eye-open");
    var off = btn.querySelector(".eye-off");
    if (open) open.hidden = willShow;
    if (off) off.hidden = !willShow;
    input.focus({ preventScroll: true });
  });

  /* ------------------------------------------------------------------
     تذكّر رمز المؤسسة والبريد فقط — لا نخزّن كلمة المرور أبدًا
     ------------------------------------------------------------------ */
  var tenant = document.getElementById("tenant");
  var email = document.getElementById("email");
  var remember = document.getElementById("remember-me");
  var loginForm = document.getElementById("login-form");
  var REMEMBER_KEY = "daftar_login_hint_v1";

  if (tenant && email && remember && loginForm) {
    try {
      var saved = JSON.parse(localStorage.getItem(REMEMBER_KEY) || "null");
      if (saved && saved.email) {
        email.value = saved.email;
        if (saved.tenant) tenant.value = saved.tenant;
        remember.checked = true;
      }
    } catch (e) { /* ignore */ }

    loginForm.addEventListener("submit", function () {
      try {
        if (remember.checked) {
          localStorage.setItem(REMEMBER_KEY, JSON.stringify({
            tenant: tenant.value.trim(),
            email: email.value.trim()
          }));
        } else {
          localStorage.removeItem(REMEMBER_KEY);
        }
      } catch (e) { /* ignore */ }
    }, true);
  }

  /* إخفاء رسالة الخطأ بمجرد بدء التصحيح */
  document.querySelectorAll(".auth-form .form-control").forEach(function (input) {
    input.addEventListener("input", function () {
      var alert = document.getElementById("login-error");
      if (alert && !alert.hidden) alert.hidden = true;
    });
  });

  /* ------------------------------------------------------------------
     غبار ذهبي متحرك (Canvas) — خفيف ويتوقف عند إخفاء التبويب
     ------------------------------------------------------------------ */
  var canvas = document.getElementById("auth-particles");
  var stage = document.querySelector(".auth-stage");

  function initParticles(cv, host) {
    var ctx = cv.getContext("2d");
    if (!ctx) return;

    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var particles = [];
    var w = 1;
    var h = 1;
    var running = true;

    function spawn() {
      return {
        x: Math.random() * w,
        y: Math.random() * h,
        r: Math.random() * 1.7 + 0.5,
        vx: (Math.random() - 0.5) * 0.16,
        vy: -(Math.random() * 0.22 + 0.05),
        a: Math.random() * 0.45 + 0.12,
        phase: Math.random() * Math.PI * 2,
        speed: Math.random() * 0.012 + 0.004
      };
    }

    function resize() {
      var rect = host.getBoundingClientRect();
      w = Math.max(1, Math.floor(rect.width));
      h = Math.max(1, Math.floor(rect.height));
      cv.width = Math.floor(w * dpr);
      cv.height = Math.floor(h * dpr);
      cv.style.width = w + "px";
      cv.style.height = h + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      var count = Math.max(18, Math.min(52, Math.round(w * h / 26000)));
      particles = [];
      for (var i = 0; i < count; i++) particles.push(spawn());
    }

    function draw() {
      if (!running) return;
      ctx.clearRect(0, 0, w, h);
      for (var i = 0; i < particles.length; i++) {
        var p = particles[i];
        p.x += p.vx;
        p.y += p.vy;
        p.phase += p.speed;
        if (p.y < -10) { p.y = h + 8; p.x = Math.random() * w; }
        if (p.x < -10) p.x = w + 8;
        if (p.x > w + 10) p.x = -8;
        var alpha = p.a * (0.65 + Math.sin(p.phase) * 0.35);
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(235, 217, 168, " + alpha.toFixed(3) + ")";
        ctx.fill();
      }
      requestAnimationFrame(draw);
    }

    resize();
    var resizeTimer = null;
    window.addEventListener("resize", function () {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(resize, 180);
    });
    document.addEventListener("visibilitychange", function () {
      if (document.hidden) {
        running = false;
      } else if (!running) {
        running = true;
        requestAnimationFrame(draw);
      }
    });
    requestAnimationFrame(draw);
  }

  if (canvas && stage && !reduceMotion) {
    initParticles(canvas, stage);
  }

  /* ------------------------------------------------------------------
     اختلاف منظر خفيف للختم عند تحريك المؤشر
     ------------------------------------------------------------------ */
  var scene = document.querySelector("[data-auth-parallax]");
  if (scene && stage && !reduceMotion && window.matchMedia("(pointer: fine)").matches) {
    var targetX = 0;
    var targetY = 0;
    var currentX = 0;
    var currentY = 0;
    var raf = null;

    function animateScene() {
      currentX += (targetX - currentX) * 0.08;
      currentY += (targetY - currentY) * 0.08;
      scene.style.transform =
        "rotateX(" + (-currentY * 3.5).toFixed(2) + "deg) " +
        "rotateY(" + (currentX * 4.5).toFixed(2) + "deg) " +
        "translate3d(" + (currentX * 5).toFixed(2) + "px, " + (currentY * 4).toFixed(2) + "px, 0)";
      if (Math.abs(targetX - currentX) > 0.001 || Math.abs(targetY - currentY) > 0.001) {
        raf = requestAnimationFrame(animateScene);
      } else {
        raf = null;
      }
    }

    stage.addEventListener("pointermove", function (e) {
      var rect = stage.getBoundingClientRect();
      targetX = ((e.clientX - rect.left) / rect.width - 0.5) * 2;
      targetY = ((e.clientY - rect.top) / rect.height - 0.5) * 2;
      if (!raf) raf = requestAnimationFrame(animateScene);
    });
    stage.addEventListener("pointerleave", function () {
      targetX = 0;
      targetY = 0;
      if (!raf) raf = requestAnimationFrame(animateScene);
    });
  }
})();
