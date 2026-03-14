document.addEventListener("DOMContentLoaded", function () {
  const domainInput = document.getElementById("domainInput");
  const addBtn = document.getElementById("addBtn");
  const domainList = document.getElementById("domainList");
  const icsFileInput = document.getElementById("icsFileInput");

  function loadDomains() {
    api.storage.local.get("customDomains", function (result) {
      const customDomains = result.customDomains || [];
      renderDomains(customDomains);
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
      api.storage.local.get("customDomains", function (result) {
        let customDomains = result.customDomains || [];
        if (!customDomains.includes(hostname)) {
          customDomains.push(hostname);
          api.storage.local.set({ customDomains: customDomains }, function () {
            domainInput.value = "";
            loadDomains();
          });
        }
      });
    } catch (e) {
      console.error("Invalid URL:", e);
    }
  }

  function removeDomain(domain) {
    api.storage.local.get("customDomains", function (result) {
      let customDomains = result.customDomains || [];
      customDomains = customDomains.filter((d) => d !== domain);
      api.storage.local.set({ customDomains: customDomains }, function () {
        loadDomains();
      });
    });
  }

  function unfoldIcsLines(icsData) {
    const rawLines = String(icsData)
      .replace(/\r\n/g, "\n")
      .replace(/\r/g, "\n")
      .split("\n");
    const lines = [];

    rawLines.forEach((line) => {
      if ((line.startsWith(" ") || line.startsWith("\t")) && lines.length > 0) {
        lines[lines.length - 1] += line.slice(1);
      } else {
        lines.push(line);
      }
    });

    return lines;
  }

  function parseIcsDate(rawValue, params) {
    const value = String(rawValue || "").trim();
    const isDateOnly = (params.VALUE || "").toUpperCase() === "DATE";

    if (isDateOnly) {
      const dateMatch = value.match(/^(\d{4})(\d{2})(\d{2})$/);
      if (!dateMatch) {
        return null;
      }
      const [, y, m, d] = dateMatch;
      return new Date(Number(y), Number(m) - 1, Number(d), 0, 0, 0, 0);
    }

    const dateTimeMatch = value.match(
      /^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})(Z?)$/,
    );
    if (!dateTimeMatch) {
      return null;
    }

    const [, y, m, d, hh, mm, ss, utcFlag] = dateTimeMatch;
    if (utcFlag === "Z") {
      return new Date(
        Date.UTC(
          Number(y),
          Number(m) - 1,
          Number(d),
          Number(hh),
          Number(mm),
          Number(ss),
        ),
      );
    }

    return new Date(
      Number(y),
      Number(m) - 1,
      Number(d),
      Number(hh),
      Number(mm),
      Number(ss),
    );
  }

  function unescapeIcsText(value) {
    return String(value || "")
      .replace(/\\n/gi, "\n")
      .replace(/\\,/g, ",")
      .replace(/\\;/g, ";")
      .replace(/\\\\/g, "\\")
      .trim();
  }

  function parseIcs(icsData) {
    const lines = unfoldIcsLines(icsData);
    const events = [];
    let currentEvent = null;

    for (const line of lines) {
      if (!line) {
        continue;
      }

      const upperLine = line.toUpperCase();
      if (upperLine === "BEGIN:VEVENT") {
        currentEvent = { title: "Untitled event", start: null };
        continue;
      }

      if (upperLine === "END:VEVENT") {
        if (
          currentEvent?.start instanceof Date &&
          !Number.isNaN(currentEvent.start.getTime())
        ) {
          events.push(currentEvent);
        }
        currentEvent = null;
        continue;
      }

      if (!currentEvent || !line.includes(":")) {
        continue;
      }

      const [left, rawValue] = line.split(/:(.*)/s, 2);
      const [rawName, ...paramParts] = left.split(";");
      const name = rawName.toUpperCase();
      const params = {};
      paramParts.forEach((part) => {
        const [k, v] = part.split("=");
        if (k && v) {
          params[k.toUpperCase()] = v;
        }
      });

      if (name === "SUMMARY") {
        currentEvent.title = unescapeIcsText(rawValue || "Untitled event");
      } else if (name === "DTSTART") {
        currentEvent.start = parseIcsDate(rawValue, params);
      }
    }

    const now = new Date();
    const upcomingEvents = events
      .filter((event) => event.start >= now)
      .sort((a, b) => a.start.getTime() - b.start.getTime());
    const nearestEvent = upcomingEvents.length > 0 ? upcomingEvents[0] : null;

    console.log("[Calendar][Firefox] Parsed ICS", {
      totalEvents: events.length,
      upcomingEvents: upcomingEvents.length,
      nearestEvent,
    });

    api.storage.local.set(
      {
        nearestEvent: nearestEvent
          ? {
              title: nearestEvent.title,
              start: nearestEvent.start.toISOString(),
            }
          : null,
      },
      () => {
        console.log("[Calendar][Firefox] Stored nearestEvent", nearestEvent);
      },
    );
  }

  icsFileInput.addEventListener("change", function (e) {
    const file = e.target.files[0];
    if (!file) return;

    const fileLabel = document.getElementById("fileLabel");
    if (fileLabel) {
      fileLabel.textContent = file.name;
    }

    console.log("[Calendar][Firefox] Selected file", file.name);

    const reader = new FileReader();
    reader.onload = function (e) {
      try {
        const icsData = e.target.result;
        parseIcs(icsData);
      } catch (error) {
        console.error("[Calendar][Firefox] Failed to parse ICS", error);
      }
    };
    reader.onerror = function () {
      console.error("[Calendar][Firefox] Failed to read file");
    };
    reader.readAsText(file);
  });

  addBtn.addEventListener("click", addDomain);
  domainInput.addEventListener("keypress", function (e) {
    if (e.key === "Enter") addDomain();
  });

  loadDomains();
});
