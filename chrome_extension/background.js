const DISABLE_TIMER = true;

const defaultDomains = [
  "facebook.com",
  "twitter.com",
  "x.com",
  "instagram.com",
  "linkedin.com",
  "tiktok.com",
  "reddit.com",
  "snapchat.com",
  "pinterest.com",
  "youtube.com",
  "twitch.tv",
];
chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.get("defaultDomains", function (result) {
    if (!result.defaultDomains) {
      chrome.storage.local.set({ defaultDomains });
    }
  });
});

let customDomains = [];
let previousTabId = null;
const tabUrlCache = new Map();
const pendingTimers = new Map();

async function loadCustomDomains() {
  const result = await chrome.storage.local.get("customDomains");
  customDomains = result.customDomains || [];
}

async function saveCustomDomains(domains) {
  await chrome.storage.local.set({ customDomains: domains });
  customDomains = domains;
}

async function addDomain(domain) {
  if (!domain || customDomains.includes(domain)) return;
  const newDomains = [...customDomains, domain];
  await saveCustomDomains(newDomains);
  console.log("Added domain:", domain);
}

function getAllDomains() {
  return [...defaultDomains, ...customDomains];
}

async function sendTeethRequest(domain, tabId) {
  if (pendingTimers.has(tabId)) {
    clearTimeout(pendingTimers.get(tabId));
    pendingTimers.delete(tabId);
  }

  if (DISABLE_TIMER) {
    await executeTeethRequest(domain);
  } else {
    const timerId = setTimeout(() => {
      executeTeethRequest(domain);
      pendingTimers.delete(tabId);
    }, 10000);
    pendingTimers.set(tabId, timerId);
  }
}

async function executeTeethRequest(domain) {
  try {
    console.log("executeTeethRequest: Sending request to /image/angry");
    await fetch("http://localhost:8000/image/angry", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ domain: domain }),
    });
    console.log("TEETH", domain);
  } catch (error) {
    console.error("Failed to send POST request:", error);
  }
}

async function sendDefaultRequest() {
  try {
    console.log("sendDefaultRequest: Sending request to /image/calm");
    const response = await fetch("http://localhost:8000/image/calm", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    });
    console.log(
      "sendDefaultRequest: Response received",
      response.status,
      response.statusText,
    );
  } catch (error) {
    console.error("Failed to send POST request:", error);
  }
}

function isSocialMediaUrl(url) {
  if (!url) return false;

  try {
    const hostname = new URL(url).hostname.toLowerCase();
    return getAllDomains().some(
      (domain) => hostname === domain || hostname.endsWith(`.${domain}`),
    );
  } catch {
    return false;
  }
}

function changeMascotImage() {
  const mascotImage = document.querySelector('img[src*="mascot.png"]');

  if (mascotImage) {
    mascotImage.src = mascotImage.src.replace("mascot.png", "mascot_smile.png");
  } else {
    console.log("Mascot image not found.");
  }
}

console.log("background loaded");
console.log("chrome.contextMenus =", chrome.contextMenus);

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "addDomain",
    title: "Add current domain to tracker",
    contexts: ["page"],
  });
});

if (chrome.contextMenus) {
  chrome.contextMenus.onClicked.addListener(async (info, tab) => {
    if (info.menuItemId !== "addDomain" || !tab?.url) return;

    try {
      const hostname = new URL(tab.url).hostname.toLowerCase();
      await addDomain(hostname);
    } catch (error) {
      console.error("Failed to add domain:", error);
    }
  });
} else {
  console.error("contextMenus API is unavailable");
}

loadCustomDomains();

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (tab.url) {
    tabUrlCache.set(tabId, tab.url);
  }

  if (changeInfo.status === "complete" && tab.url) {
    if (isSocialMediaUrl(tab.url)) {
      const hostname = new URL(tab.url).hostname.toLowerCase();
      console.log("THIS RAN");
      sendTeethRequest(hostname, tabId);
    } else {
      sendDefaultRequest();
    }
  }
});

chrome.tabs.onActivated.addListener(async (activeInfo) => {
  try {
    if (previousTabId !== null) {
      const previousUrl = tabUrlCache.get(previousTabId);
      if (previousUrl && isSocialMediaUrl(previousUrl)) {
        sendDefaultRequest();
        if (pendingTimers.has(previousTabId)) {
          clearTimeout(pendingTimers.get(previousTabId));
          pendingTimers.delete(previousTabId);
        }
      }
    }

    const currentTab = await chrome.tabs.get(activeInfo.tabId);
    if (currentTab.url) {
      tabUrlCache.set(activeInfo.tabId, currentTab.url);
    }

    if (currentTab.url) {
      if (isSocialMediaUrl(currentTab.url)) {
        const hostname = new URL(currentTab.url).hostname.toLowerCase();
        sendTeethRequest(hostname, activeInfo.tabId);
      } else {
        sendDefaultRequest();
      }
    }

    previousTabId = activeInfo.tabId;
  } catch (error) {
    console.error("Failed to get tab info:", error);
  }
});

chrome.tabs.onRemoved.addListener((tabId) => {
  try {
    const url = tabUrlCache.get(tabId);
    if (url && isSocialMediaUrl(url)) {
      sendDefaultRequest();
      if (pendingTimers.has(tabId)) {
        clearTimeout(pendingTimers.get(tabId));
        pendingTimers.delete(tabId);
      }
    }
    tabUrlCache.delete(tabId);
  } catch (error) {
    console.error("Failed to handle tab close:", error);
  }
});
