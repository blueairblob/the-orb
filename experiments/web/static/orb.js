// The orb — a canvas particle sphere whose colour tracks the guard's mood
// dial (PRD §7 step 7) and whose motion tracks the conversation's phase
// (idle / listening / thinking / speaking). Ported and redesigned from the
// two prototypes in experiments/orb_graphic/ — demo0's colour-ripple
// transition and demo1's mic-reactive particle field, unified around one
// explicit state object instead of copy-pasted separately.
//
// Note on colour: PRD §12's "never a raw mood number, only the narrative
// band" rule is about what goes into the LLM's brief. This is a different,
// nonverbal channel — the orb is *allowed* to use the continuous 0-100
// value for smoother animation.

(() => {
  "use strict";

  // ---------------------------------------------------------------------
  // Mood → colour: continuous HSL interpolation across control points
  // matching the guard's narrative bands (engine/guard.py MoodDial.band).
  // ---------------------------------------------------------------------
  const MOOD_COLOR_STOPS = [
    { at: 0, h: 358, s: 72, l: 46 },   // hostile — red
    { at: 15, h: 12, s: 74, l: 47 },
    { at: 40, h: 32, s: 80, l: 50 },   // gruff and suspicious — amber
    { at: 65, h: 178, s: 45, l: 42 },  // wary but listening — teal
    { at: 85, h: 142, s: 55, l: 45 },  // warming — green
    { at: 100, h: 112, s: 70, l: 55 }, // ready to help — green-gold
  ];

  // The DM's colour while narrating — pale, cool, mood-agnostic. Distinct
  // on sight from anywhere on the guard's mood gradient above.
  const DM_NEUTRAL_HSL = { h: 220, s: 18, l: 68 };

  function moodToHsl(mood) {
    const clamped = Math.max(0, Math.min(100, mood));
    let lo = MOOD_COLOR_STOPS[0];
    let hi = MOOD_COLOR_STOPS[MOOD_COLOR_STOPS.length - 1];
    for (let i = 0; i < MOOD_COLOR_STOPS.length - 1; i++) {
      if (clamped >= MOOD_COLOR_STOPS[i].at && clamped <= MOOD_COLOR_STOPS[i + 1].at) {
        lo = MOOD_COLOR_STOPS[i];
        hi = MOOD_COLOR_STOPS[i + 1];
        break;
      }
    }
    const span = hi.at - lo.at || 1;
    const t = (clamped - lo.at) / span;
    return {
      h: lo.h + (hi.h - lo.h) * t,
      s: lo.s + (hi.s - lo.s) * t,
      l: lo.l + (hi.l - lo.l) * t,
    };
  }

  function hslToRgb(h, s, l) {
    s /= 100;
    l /= 100;
    const k = (n) => (n + h / 30) % 12;
    const a = s * Math.min(l, 1 - l);
    const f = (n) => l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
    return { r: 255 * f(0), g: 255 * f(8), b: 255 * f(4) };
  }

  // ---------------------------------------------------------------------
  // Orb renderer
  // ---------------------------------------------------------------------
  const PARTICLE_COUNT = 3200;
  const BASE_RADIUS = 110;

  class Particle {
    constructor() {
      this.theta = Math.random() * Math.PI * 2;
      this.phi = Math.acos(Math.random() * 2 - 1);
      this.radius = BASE_RADIUS + (Math.random() * 70 - 35);
      this.speed = 0.01 + Math.random() * 0.02;
      this.size = 0.8 + Math.random() * 1.3;
      this.r = 255;
      this.g = 255;
      this.b = 255;
    }
  }

  class Orb {
    constructor(canvas) {
      this.canvas = canvas;
      this.ctx = canvas.getContext("2d");
      this.width = canvas.width = window.innerWidth;
      this.height = canvas.height = window.innerHeight;
      window.addEventListener("resize", () => {
        this.width = canvas.width = window.innerWidth;
        this.height = canvas.height = window.innerHeight;
      });

      this.particles = Array.from({ length: PARTICLE_COUNT }, () => new Particle());
      this.moodValue = 40;
      this.phase = "idle"; // idle | listening | thinking | speaking
      this.speaker = "guard"; // guard | dm — only matters while phase === "speaking"
      this.micVolume = 0;
      this._angleY = 0;
      this._angleX = 0;

      this._tick = this._tick.bind(this);
      requestAnimationFrame(this._tick);
    }

    setMood(value) {
      this.moodValue = value;
    }

    setPhase(phase) {
      this.phase = phase;
    }

    setSpeaker(speaker) {
      this.speaker = speaker;
    }

    setMicVolume(volume) {
      this.micVolume = volume;
    }

    // Per-phase target radius offset + swirl speed multiplier + brightness.
    _phaseDynamics(now) {
      switch (this.phase) {
        case "listening":
          return {
            swirl: 1.3 + this.micVolume * 2.5,
            radiusPulse: this.micVolume * 90,
            brightness: 1 + this.micVolume * 0.4,
          };
        case "thinking": {
          // Tight, fast shimmer — reads as "considering," not lag.
          const shimmer = Math.sin(now * 0.018) * 12;
          return { swirl: 3.2, radiusPulse: shimmer, brightness: 1.15 };
        }
        case "speaking": {
          // No real amplitude data from speechSynthesis — a rhythmic pulse
          // stands in for one. Documented compromise, not real lip-sync.
          const talk = (Math.sin(now * 0.012) + 1) / 2;
          return { swirl: 1.8, radiusPulse: talk * 35, brightness: 1.2 };
        }
        default:
          return {
            swirl: 1.0,
            radiusPulse: Math.sin(now * 0.0015) * 8,
            brightness: 1.0,
          };
      }
    }

    _tick(now) {
      const ctx = this.ctx;
      ctx.fillStyle = "rgba(3, 3, 4, 0.22)";
      ctx.fillRect(0, 0, this.width, this.height);

      const { swirl, radiusPulse, brightness } = this._phaseDynamics(now);
      // The DM isn't a mood-bearing character — while it's speaking, the
      // orb shouldn't borrow the guard's colour. A fixed neutral tone
      // instead; the guard's mood gradient applies everywhere else.
      const isDmSpeaking = this.phase === "speaking" && this.speaker === "dm";
      const { h, s, l } = isDmSpeaking ? DM_NEUTRAL_HSL : moodToHsl(this.moodValue);
      const targetRgb = hslToRgb(h, s, Math.min(85, l * brightness));

      this._angleY += 0.0016 + swirl * 0.0006;
      this._angleX = Math.sin(now * 0.0003) * 0.22;

      const dynamicRadius = BASE_RADIUS + radiusPulse;
      const cosY = Math.cos(this._angleY);
      const sinY = Math.sin(this._angleY);
      const cosX = Math.cos(this._angleX);
      const sinX = Math.sin(this._angleX);
      const fov = 380;

      for (const p of this.particles) {
        p.theta += p.speed * swirl;
        p.radius += (dynamicRadius - p.radius) * 0.06;
        p.r += (targetRgb.r - p.r) * 0.08;
        p.g += (targetRgb.g - p.g) * 0.08;
        p.b += (targetRgb.b - p.b) * 0.08;

        const x3d = p.radius * Math.sin(p.phi) * Math.cos(p.theta);
        const y3d = p.radius * Math.cos(p.phi);
        const z3d = p.radius * Math.sin(p.phi) * Math.sin(p.theta);

        const xRot = x3d * cosY - z3d * sinY;
        const zRot1 = x3d * sinY + z3d * cosY;
        const yRot = y3d * cosX - zRot1 * sinX;
        const zRot = y3d * sinX + zRot1 * cosX;

        const scale = fov / (fov + zRot);
        const screenX = this.width / 2 + xRot * scale;
        const screenY = this.height / 2 + yRot * scale;

        if (screenX >= 0 && screenX <= this.width && screenY >= 0 && screenY <= this.height) {
          const alpha = Math.max(0.15, scale * 0.85);
          ctx.fillStyle = `rgba(${p.r | 0}, ${p.g | 0}, ${p.b | 0}, ${alpha})`;
          const renderedSize = Math.max(0.5, p.size * scale);
          ctx.fillRect(screenX, screenY, renderedSize, renderedSize);
        }
      }

      requestAnimationFrame(this._tick);
    }
  }

  // ---------------------------------------------------------------------
  // UI wiring
  // ---------------------------------------------------------------------
  const orb = new Orb(document.getElementById("orb-canvas"));
  const statusDot = document.getElementById("status-dot");
  const statusText = document.getElementById("status-text");
  const micBtn = document.getElementById("mic-btn");
  const debugToggle = document.getElementById("debug-toggle");
  const debugPanel = document.getElementById("debug-panel");
  const debugForm = document.getElementById("debug-form");
  const debugInput = document.getElementById("debug-input");
  const transcript = document.getElementById("transcript");

  function setStatus(mode, text) {
    statusDot.className = `status-dot ${mode}`;
    statusText.textContent = text;
  }

  const ROLE_LABELS = { player: "You", guard: "Guard", dm: "DM" };

  function appendLine(role, text) {
    const el = document.createElement("div");
    el.className = `line ${role}`;
    const label = ROLE_LABELS[role];
    el.textContent = label ? `${label}: ${text}` : text;
    transcript.appendChild(el);
    transcript.scrollTop = transcript.scrollHeight;
  }

  debugToggle.addEventListener("click", () => {
    debugPanel.hidden = !debugPanel.hidden;
  });

  // ---------------------------------------------------------------------
  // WebSocket client
  // ---------------------------------------------------------------------
  let ws = null;

  function connect() {
    ws = new WebSocket(`ws://${location.host}/ws`);

    ws.addEventListener("open", () => {
      setStatus("connected", "Connected");
      micBtn.disabled = false;
    });

    ws.addEventListener("close", () => {
      setStatus("", "Disconnected — retrying…");
      micBtn.disabled = true;
      setTimeout(connect, 2000);
    });

    ws.addEventListener("message", (event) => {
      const message = JSON.parse(event.data);
      if (message.type === "state") {
        orb.setMood(message.mood);
        if (message.intro) {
          appendLine(message.speaker || "dm", message.intro);
          speak(message.intro, message.speaker || "dm");
        }
      } else if (message.type === "thinking") {
        orb.setPhase("thinking");
        setStatus("thinking", "Considering…");
      } else if (message.type === "reply") {
        orb.setMood(message.mood);
        appendLine(message.speaker, message.text);
        speak(message.text, message.speaker);
        if (message.outcome === "unlock") {
          appendLine("system", "(The door creaks open. You're free.)");
        } else if (message.outcome === "lockout") {
          appendLine("system", "(The guard storms off. Your only way out just left.)");
        }
      }
    });
  }

  function sendUtterance(text) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    appendLine("player", text);
    ws.send(JSON.stringify({ type: "utterance", text }));
  }

  // ---------------------------------------------------------------------
  // Text-to-speech: speaks the DM's narration or the guard's reply, with
  // different pitch/rate per speaker (PRD §12 — the DM narrates, the guard
  // only ever speaks his own dialogue; they should sound like two voices,
  // not one). No real amplitude/timing data is exposed by speechSynthesis
  // in most browsers, so the orb's "speaking" animation (see
  // Orb._phaseDynamics) is a rhythmic stand-in, not synced to actual audio.
  // ---------------------------------------------------------------------
  const VOICE_PROFILES = {
    dm: { pitch: 1.0, rate: 0.95 },
    guard: { pitch: 0.75, rate: 1.05 },
  };

  function speak(text, speaker) {
    orb.setPhase("speaking");
    orb.setSpeaker(speaker);
    setStatus(
      speaker === "dm" ? "narrating" : "speaking",
      speaker === "dm" ? "The DM narrates…" : "Guard is speaking…"
    );
    if (!("speechSynthesis" in window)) {
      // No TTS support: hold the speaking phase briefly, then settle.
      setTimeout(() => {
        orb.setPhase("idle");
        setStatus("connected", "Connected");
      }, 1200);
      return;
    }
    const utterance = new SpeechSynthesisUtterance(text);
    const profile = VOICE_PROFILES[speaker] || VOICE_PROFILES.guard;
    utterance.pitch = profile.pitch;
    utterance.rate = profile.rate;
    utterance.onend = () => {
      orb.setPhase("idle");
      setStatus("connected", "Connected");
    };
    speechSynthesis.speak(utterance);
  }

  // ---------------------------------------------------------------------
  // Speech recognition (click to talk) + live mic volume for the
  // "listening" visual. Known limitation (see README): SpeechRecognition
  // is Chrome/Edge-only and cloud-backed, not on-device.
  // ---------------------------------------------------------------------
  let recognizer = null;
  let audioContext = null;
  let analyser = null;
  let micDataArray = null;
  let listening = false;

  function ensureMicVolumeAnalysis() {
    if (audioContext) return Promise.resolve();
    return navigator.mediaDevices.getUserMedia({ audio: true }).then((stream) => {
      audioContext = new (window.AudioContext || window.webkitAudioContext)();
      const source = audioContext.createMediaStreamSource(stream);
      analyser = audioContext.createAnalyser();
      analyser.fftSize = 512;
      source.connect(analyser);
      micDataArray = new Uint8Array(analyser.frequencyBinCount);
      pollMicVolume();
    });
  }

  function pollMicVolume() {
    if (!analyser) return;
    analyser.getByteFrequencyData(micDataArray);
    let total = 0;
    for (let i = 0; i < micDataArray.length; i++) total += micDataArray[i];
    const volume = total / micDataArray.length / 255;
    if (listening) orb.setMicVolume(volume);
    requestAnimationFrame(pollMicVolume);
  }

  function startListening() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      appendLine("system", "SpeechRecognition isn't supported in this browser — use the text box below.");
      debugPanel.hidden = false;
      return;
    }

    ensureMicVolumeAnalysis().catch(() => {
      appendLine("system", "Microphone access denied — use the text box below.");
    });

    recognizer = new SpeechRecognition();
    recognizer.lang = "en-GB";
    recognizer.interimResults = true;
    recognizer.maxAlternatives = 1;

    listening = true;
    orb.setPhase("listening");
    micBtn.classList.add("active");
    micBtn.textContent = "🎙 Listening…";
    setStatus("listening", "Listening…");

    recognizer.onresult = (event) => {
      const result = event.results[event.results.length - 1];
      if (result.isFinal) {
        stopListening();
        sendUtterance(result[0].transcript.trim());
      }
    };
    recognizer.onerror = () => stopListening();
    recognizer.onend = () => {
      if (listening) stopListening();
    };

    recognizer.start();
  }

  function stopListening() {
    listening = false;
    orb.setMicVolume(0);
    micBtn.classList.remove("active");
    micBtn.textContent = "🎙 Hold to talk";
    if (recognizer) {
      recognizer.onresult = null;
      recognizer.onerror = null;
      recognizer.onend = null;
      recognizer.stop();
      recognizer = null;
    }
  }

  micBtn.addEventListener("click", () => {
    if (listening) {
      stopListening();
    } else {
      startListening();
    }
  });

  debugForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const text = debugInput.value.trim();
    if (!text) return;
    sendUtterance(text);
    debugInput.value = "";
  });

  connect();
})();
