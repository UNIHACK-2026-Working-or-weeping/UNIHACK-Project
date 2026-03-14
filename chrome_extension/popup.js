document.addEventListener("DOMContentLoaded", function () {
  const domainInput = document.getElementById("domainInput");
  const addBtn = document.getElementById("addBtn");
  const domainList = document.getElementById("domainList");
  const icsFileInput = document.getElementById("icsFileInput");

  function loadDomains() {
    chrome.storage.local.get("customDomains", function (result) {
      const customDomains = result.customDomains || [];
      renderDomains(customDomains);
    });
  }

  function renderDomains(domains) {
    domainList.innerHTML = "";
    if (domains.length === 0) {
      domainList.innerHTML = '<div class="empty-domain-msg" id="emptyMsg">NO DOMAINS ADDED<br><span class="blink">_</span></div>';
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


  function parseIcs(icsData) {
    const jCalData = ICAL.parse(icsData);
    const comp = new ICAL.Component(jCalData);
    const vevents = comp.getAllProperties('vevent');

    const now = new Date();
    const oneWeekLater = new Date();
    oneWeekLater.setDate(now.getDate() + 7);

    const upcomingEvents = [];

    vevents.forEach((event) => {
      const start = event.getFirstValue().startDate.toJSDate();
      if (start >= now && start <= oneWeekLater) {
        upcomingEvents.push({
          summary: event.getFirstValue('summary'),
          start: start,
          end: event.getFirstValue('dtend').toJSDate(),
          location: event.getFirstValue('location'),
        });
      }
    });
    if (upcomingEvents.length > 0) {
      spawnMascotOnSocialMedia();
    }
  }

  icsFileInput.addEventListener("change", function (e) {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = function (e) {
      const icsData = e.target.result;
      parseIcs(icsData); 
    };
    reader.readAsText(file);
  });


  function spawnMascotOnSocialMedia() {
    chrome.storage.local.get("defaultDomains", function (result) {
      const defaultDomains = result.defaultDomains || [];
      
      chrome.tabs.query({}, function (tabs) {
        chrome.storage.local.get("customDomains", function (result) {
          const customDomains = result.customDomains || [];
          const allDomains = [...defaultDomains, ...customDomains];

          tabs.forEach((tab) => {
            const url = new URL(tab.url);
            const hostname = url.hostname.toLowerCase();
            
            if (allDomains.some(domain => hostname.endsWith(domain))) {
              chrome.scripting.executeScript({
                target: { tabId: tab.id },
                func: changeMascotImage
              });
            }
          });
        });
      });
    });
  }

  addBtn.addEventListener("click", addDomain);
  domainInput.addEventListener("keypress", function (e) {
    if (e.key === "Enter") addDomain();
  });

  loadDomains();

  const tabV1 = document.getElementById("tabV1");
  const tabV2 = document.getElementById("tabV2");

  async function sendAvatarRequest(version) {
    try {
      await fetch("http://localhost:8000/avatar/set", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ version }),
      });
    } catch (error) {
      console.error("Failed to send avatar request:", error);
    }
  }

  // Restore saved state on popup open
  chrome.storage.local.get("avatarVersion", ({ avatarVersion }) => {
    if (avatarVersion === "v1") {
      tabV1.classList.add("active");
      tabV2.classList.remove("active");
    } else if (avatarVersion === "v2") {
      tabV2.classList.add("active");
      tabV1.classList.remove("active");
    }
  });

  tabV1.addEventListener("click", () => {
    tabV1.classList.add("active");
    tabV2.classList.remove("active");
    chrome.storage.local.set({ avatarVersion: "v1" });
    sendAvatarRequest("v1");
  });

  tabV2.addEventListener("click", () => {
    tabV2.classList.add("active");
    tabV1.classList.remove("active");
    chrome.storage.local.set({ avatarVersion: "v2" });
    sendAvatarRequest("v2");
  });

});
