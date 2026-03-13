document.addEventListener("DOMContentLoaded", function () {
  const domainInput = document.getElementById("domainInput");
  const addBtn = document.getElementById("addBtn");
  const domainList = document.getElementById("domainList");

  function loadDomains() {
    chrome.storage.local.get("customDomains", function (result) {
      const customDomains = result.customDomains || [];
      renderDomains(customDomains);
    });
  }

  function renderDomains(domains) {
    domainList.innerHTML = "";
    if (domains.length === 0) {
      domainList.innerHTML = '<div class="empty-message">No custom domains added</div>';
      return;
    }

    domains.forEach((domain) => {
      const item = document.createElement("div");
      item.className = "domain-item";
      item.innerHTML = `
        <span>${domain}</span>
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
          chrome.storage.local.set({ customDomains: customDomains }, function () {
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
    chrome.storage.local.get("customDomains", function (result) {
      let customDomains = result.customDomains || [];
      customDomains = customDomains.filter((d) => d !== domain);
      chrome.storage.local.set({ customDomains: customDomains }, function () {
        loadDomains();
      });
    });
  }

  addBtn.addEventListener("click", addDomain);
  domainInput.addEventListener("keypress", function (e) {
    if (e.key === "Enter") addDomain();
  });

  loadDomains();
});
