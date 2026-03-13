// 🔑 PASTE YOUR NEW GEMINI API KEY HERE
const GEMINI_API_KEY = "--";

const PERSONALITIES = {
  sarcastic:
    "You are a sarcastic desktop mascot. The user opened a distracting website instead of working. Write a short (2 sentences MAX), funny, sarcastic guilt-trip message. Be witty, not mean. End with a passive-aggressive suggestion to get back to work. Only respond with the message, nothing else.",
  disappointed_dad:
    "You are a disappointed but loving dad. The user opened a distracting website instead of working. Write a short (2 sentences MAX) message like a dad who is not angry, just disappointed. Reference vague sacrifices you made. End with '...just saying.' Only respond with the message, nothing else.",
  hype_coach:
    "You are an over-the-top motivational coach SHOCKED the user is distracted. Write a short (2 sentences MAX) high-energy guilt message. Use CAPS for emphasis. End with an aggressive motivational push. Only respond with the message, nothing else.",
};

const FALLBACKS = {
  sarcastic: [
    "Oh wow, scrolling again? Your future self is already writing your apology letter — back to work.",
    "Bold choice opening that instead of your tasks. Really bold. Incredibly bold.",
    "Ah yes, this is definitely more important than everything you have to do today. Totally.",
  ],
  disappointed_dad: [
    "I didn't work double shifts so you could do this all day... just saying.",
    "Your mother and I just wanted better for you. That's all. Just saying.",
    "I'm not mad. I'm just... I thought we raised you differently. Just saying.",
  ],
  hype_coach: [
    "WHAT ARE YOU DOING?! YOUR DREAMS DON'T SCROLL THEMSELVES!! GET BACK TO WORK!!!",
    "NO NO NO!! Champions don't browse, they GRIND!! CLOSE THIS TAB RIGHT NOW!!!",
    "YOUR FUTURE SELF IS WATCHING YOU RIGHT NOW AND CRYING!! MOVE IT!!",
  ],
};

const FACES = { sarcastic: "😤", disappointed_dad: "😔", hype_coach: "🔥" };

let currentPersonality = "sarcastic";
let mascotVisible = false;

async function generateMessage(site) {
  const siteName = site.replace("www.", "").split(".")[0];

  try {
    const response = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=${GEMINI_API_KEY}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          contents: [
            {
              parts: [
                {
                  text: `${PERSONALITIES[currentPersonality]}\n\nThe user just opened ${siteName}.`,
                },
              ],
            },
          ],
          generationConfig: { maxOutputTokens: 80, temperature: 1.1 },
        }),
      },
    );

    const data = await response.json();
    const text = data?.candidates?.[0]?.content?.parts?.[0]?.text;
    if (text) return text.trim();
    throw new Error("no response");
  } catch (err) {
    const list = FALLBACKS[currentPersonality];
    return list[Math.floor(Math.random() * list.length)];
  }
}

function createMascot(message) {
  const existing = document.getElementById("guilt-mascot-container");
  if (existing) existing.remove();

  const container = document.createElement("div");
  container.id = "guilt-mascot-container";

  container.innerHTML = `
    <div id="guilt-mascot-bubble">
      <div id="guilt-mascot-face">${FACES[currentPersonality]}</div>
      <div id="guilt-mascot-message">${message}</div>
      <div id="guilt-mascot-buttons">
        <button id="guilt-ok-btn">ok ok I'll stop 😔</button>
        <button id="guilt-ignore-btn">leave me alone</button>
      </div>
      <div id="guilt-personality-switch">
        <span>mood:</span>
        <button class="personality-btn ${currentPersonality === "sarcastic" ? "active" : ""}" data-p="sarcastic">😏 sarcastic</button>
        <button class="personality-btn ${currentPersonality === "disappointed_dad" ? "active" : ""}" data-p="disappointed_dad">😞 dad</button>
        <button class="personality-btn ${currentPersonality === "hype_coach" ? "active" : ""}" data-p="hype_coach">📣 coach</button>
      </div>
    </div>
  `;

  document.body.appendChild(container);
  mascotVisible = true;
  setTimeout(() => container.classList.add("visible"), 50);

  document.getElementById("guilt-ok-btn").addEventListener("click", () => {
    container.classList.remove("visible");
    setTimeout(() => container.remove(), 400);
    mascotVisible = false;
    history.back();
  });

  document.getElementById("guilt-ignore-btn").addEventListener("click", () => {
    container.classList.remove("visible");
    setTimeout(() => {
      container.remove();
      setTimeout(() => {
        if (!mascotVisible) showMascot(window.location.hostname);
      }, 60000);
    }, 400);
    mascotVisible = false;
  });

  document.querySelectorAll(".personality-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      currentPersonality = btn.dataset.p;
      document
        .querySelectorAll(".personality-btn")
        .forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const msgEl = document.getElementById("guilt-mascot-message");
      const faceEl = document.getElementById("guilt-mascot-face");
      const loadingPhrases = {
        sarcastic: "preparing judgment...",
        disappointed_dad: "sighing deeply...",
        hype_coach: "CHARGING UP...",
      };
      msgEl.textContent = loadingPhrases[currentPersonality];
      faceEl.textContent = "⏳";
      const newMsg = await generateMessage(window.location.hostname);
      msgEl.textContent = newMsg;
      faceEl.textContent = FACES[currentPersonality];
    });
  });
}

async function showMascot(site) {
  mascotVisible = true;

  const container = document.createElement("div");
  container.id = "guilt-mascot-container";
  const loadingPhrases = {
    sarcastic: "preparing judgment...",
    disappointed_dad: "sighing deeply...",
    hype_coach: "CHARGING UP...",
  };
  container.innerHTML = `
    <div id="guilt-mascot-bubble">
      <div id="guilt-mascot-face">⏳</div>
      <div id="guilt-mascot-message">${loadingPhrases[currentPersonality]}</div>
    </div>
  `;
  document.body.appendChild(container);
  setTimeout(() => container.classList.add("visible"), 50);

  const message = await generateMessage(site);
  container.remove();
  createMascot(message);
}

chrome.runtime.onMessage.addListener((msg) => {
  if (msg.action === "showMascot" && !mascotVisible) {
    showMascot(msg.site);
  }
});
