document.addEventListener("DOMContentLoaded", function () {
  const domainInput = document.getElementById("domainInput");
  const addBtn = document.getElementById("addBtn");
  const domainList = document.getElementById("domainList");
  const icsFileInput = document.getElementById("icsFileInput");

  function loadDomains() {
    chrome.storage.local.get(
      ["customDomains", "calendarIcs", "calendarName", "nextCalendarEventText"],
      function (result) {
        const customDomains = result.customDomains || [];
        renderDomains(customDomains);
        if (result.calendarName) {
          document.getElementById("fileLabel").textContent =
            result.calendarName;
        }
        if (result.calendarIcs) {
          parseIcs(result.calendarIcs);
        } else if (result.nextCalendarEventText) {
          nextCalendarEventText = result.nextCalendarEventText;
          updateNextEventLabel();
        } else {
          nextCalendarEventText = null;
          updateNextEventLabel();
        }
      },
    );
  }

  function saveCalendar(icsData, fileName) {
    chrome.storage.local.set({
      calendarIcs: icsData,
      calendarName: fileName,
      nextCalendarEventText,
    });
  }

  function renderDomains(domains) {
    domainList.innerHTML = "";
    if (domains.length === 0) {
      domainList.innerHTML =
        '<div class="empty-domain-msg" id="emptyMsg">NO DOMAINS ADDED<br><span class="blink">_</span></div>';
      return;
    }

    domains.forEach((domain) => {
      const item = document.createElement("div");
      item.className = "domain-item";
      item.innerHTML = `
        <span class="domain-name">${domain}</span>
        <button class="remove-btn" data-domain="${domain}">Remove</button>
      `;
      domainList.appendChild(item);
    });

    document.querySelectorAll(".remove-btn").forEach((btn) => {
      btn.addEventListener("click", function () {
        const domainToRemove = this.getAttribute("data-domain");
        removeDomain(domainToRemove);
      });
    });
  }

  function addDomain() {
    let domain = domainInput.value.trim().toLowerCase();
    if (!domain) return;

    if (!domain.startsWith("http://") && !domain.startsWith("https://")) {
      domain = "https://" + domain;
    }

    try {
      const hostname = new URL(domain).hostname.toLowerCase();
      chrome.storage.local.get("customDomains", function (result) {
        let customDomains = result.customDomains || [];
        if (!customDomains.includes(hostname)) {
          customDomains.push(hostname);
          chrome.storage.local.set(
            { customDomains: customDomains },
            function () {
              domainInput.value = "";
              loadDomains();
            },
          );
        }
      });
    } catch (e) {
      console.error("Invalid URL:", e);
    }
  }

  function removeDomain(domain) {
    chrome.storage.local.get("customDomains", function (result) {
      let customDomains = result.customDomains || [];
      customDomains = customDomains.filter((d) => d !== domain);
      chrome.storage.local.set({ customDomains: customDomains }, function () {
        loadDomains();
      });
    });
  }

  function sendDesktopReminder(eventText) {
    fetch("http://127.0.0.1:8000/image/angry", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ domain: "calendar", event: eventText }),
    })
      .then((response) => response.json())
      .then((data) => console.log("Reminder sent", data))
      .catch((error) =>
        console.warn("Cannot reach desktop reminder API", error),
      );
  }

  const nextEventLabel = document.getElementById("nextEventLabel");
  const statusLabel = document.getElementById("mascotStatus");
  const turnOnBtn = document.getElementById("turnOnBtn");
  const turnOffBtn = document.getElementById("turnOffBtn");
  let mascotOn = false;
  let nextCalendarEventText = null;

  function updateNextEventLabel() {
    const titleEl = document.getElementById("nextEventTitle");
    const timeEl = document.getElementById("nextEventTime");
    if (nextCalendarEventText) {
      const [title, ...rest] = nextCalendarEventText.split(" at ");
      titleEl.textContent = title || "—";
      timeEl.textContent = rest.length ? "@ " + rest.join(" at ") : "";
    } else {
      titleEl.textContent = "—";
      timeEl.textContent = "No upcoming event in the next 7 days.";
    }
  }

  function updateMascotStatus() {
    if (mascotOn) {
      statusLabel.textContent = "Mascot is ON";
      statusLabel.style.color = "#7cff4f";
    } else {
      statusLabel.textContent = "Mascot is OFF";
      statusLabel.style.color = "#ff7f7f";
    }
    if (turnOnBtn) turnOnBtn.disabled = mascotOn;
    if (turnOffBtn) turnOffBtn.disabled = !mascotOn;
  }

  function setMascotState(value) {
    mascotOn = value;
    chrome.storage.local.set({ mascotOn: value });
    updateMascotStatus();
  }

  function initMascotState() {
    chrome.storage.local.get(
      ["mascotOn", "nextCalendarEventText"],
      function (result) {
        mascotOn = result.mascotOn || false;
        nextCalendarEventText = result.nextCalendarEventText || null;
        updateMascotStatus();
        updateNextEventLabel();
      },
    );
  }

  function parseIcs(icsData) {
    const unfolded = icsData.replace(/\r?\n[ \t]/g, "");
    const lines = unfolded.split(/\r?\n/);
    const events = [];
    let currentEvent = null;

    lines.forEach((rawLine) => {
      const line = rawLine.trim();
      if (line === "BEGIN:VEVENT") {
        currentEvent = {};
      } else if (line === "END:VEVENT") {
        if (currentEvent) {
          events.push(currentEvent);
          currentEvent = null;
        }
      } else if (currentEvent) {
        const separatorIndex = line.indexOf(":");
        if (separatorIndex < 0) return;
        const keyPart = line.slice(0, separatorIndex);
        const value = line.slice(separatorIndex + 1);

        const key = keyPart.split(";")[0];
        if (key === "DTSTART") {
          const parsed = parseIcsDate(value);
          if (parsed) {
            currentEvent.start = parsed;
          }
        } else if (key === "SUMMARY") {
          currentEvent.summary = value;
        }
      }
    });

    const now = new Date();
    const oneWeekLater = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);
    const upcomingEvents = events
      .filter(
        (e) =>
          e.start instanceof Date &&
          !isNaN(e.start.getTime()) &&
          e.start >= now &&
          e.start <= oneWeekLater,
      )
      .sort((a, b) => a.start - b.start);

    let nearestEvent = null;
    if (upcomingEvents.length > 0) {
      const nextEvent = upcomingEvents[0];
      const title = (nextEvent.summary || "Next activity").trim();
      nextCalendarEventText = `${title} at ${nextEvent.start.toLocaleString()}`;
      nearestEvent = { title, start: nextEvent.start.toISOString() };
      console.log("Parsed next calendar event:", nextCalendarEventText);
    } else {
      nextCalendarEventText = null;
      console.log("No upcoming events in next 7 days.");
    }
    chrome.storage.local.set({
      nextCalendarEventText,
      nearestEvent,
      calendarIcs: icsData,
    });
    updateNextEventLabel();
  }

  function parseIcsDate(value) {
    let trimmed = String(value || "").trim();
    const valuePrefix = "VALUE=DATE:";
    if (trimmed.toUpperCase().startsWith(valuePrefix)) {
      trimmed = trimmed.slice(valuePrefix.length).trim();
    }
    const dateOnly = /^\d{8}$/.test(trimmed);
    if (dateOnly) {
      const y = +trimmed.slice(0, 4);
      const m = +trimmed.slice(4, 6) - 1;
      const d = +trimmed.slice(6, 8);
      return new Date(y, m, d);
    }

    const dt = trimmed.replace(/Z$/, "");
    const parts = dt.split("T");
    if (parts.length === 2) {
      const date = parts[0];
      const time = parts[1];
      const y = +date.slice(0, 4);
      const mo = +date.slice(4, 6) - 1;
      const d = +date.slice(6, 8);
      const hh = +time.slice(0, 2);
      const mm = +time.slice(2, 4);
      const ss = +time.slice(4, 6);
      return new Date(y, mo, d, hh, mm, ss);
    }

    const parsed = Date.parse(trimmed);
    return isNaN(parsed) ? null : new Date(parsed);
  }

  icsFileInput.addEventListener("change", function (e) {
    const file = e.target.files[0];
    if (!file) return;

    const fileLabel = document.getElementById("fileLabel");
    if (fileLabel) {
      fileLabel.textContent = file.name;
    }

    console.log("[Calendar][Chrome] Selected file", file.name);

    const reader = new FileReader();
    reader.onload = function (e) {
      const icsData = e.target.result;
      document.getElementById("fileLabel").textContent = file.name;
      saveCalendar(icsData, file.name);
      parseIcs(icsData);
    };
    reader.readAsText(file);
  });

  async function setMascotPower(on) {
    const endpoint = on ? "/image/show" : "/image/hide";
    try {
      const res = await fetch("http://127.0.0.1:8000" + endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (!res.ok) throw new Error(`Status ${res.status}`);
      const data = await res.json();
      console.log("Mascot power response", data);
      setMascotState(on);
      updateNextEventLabel();
    } catch (err) {
      setMascotState(false);
      updateNextEventLabel();
      console.warn(
        "Could not change mascot power (desktop app not running)",
        err,
      );
    }
  }

  turnOnBtn.addEventListener("click", function () {
    setMascotPower(true);
  });

  turnOffBtn.addEventListener("click", function () {
    setMascotPower(false);
  });

  initMascotState();

  addBtn.addEventListener("click", addDomain);
  domainInput.addEventListener("keypress", function (e) {
    if (e.key === "Enter") addDomain();
  });

  loadDomains();
});
