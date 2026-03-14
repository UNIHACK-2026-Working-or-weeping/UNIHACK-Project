const api = (function() {
  const isFirefox = typeof browser !== 'undefined';
  const chromeObj = chrome;

  const storage = {
    local: {
      get: function(keys, callback) {
        if (isFirefox) {
          const promise = browser.storage.local.get(keys);
          if (callback) {
            promise.then(result => callback(result));
          }
          return promise;
        } else {
          return chromeObj.storage.local.get(keys, callback);
        }
      },
      set: function(items, callback) {
        if (isFirefox) {
          const promise = browser.storage.local.set(items);
          if (callback) {
            promise.then(() => callback());
          }
          return promise;
        } else {
          return chromeObj.storage.local.set(items, callback);
        }
      }
    }
  };

  const tabs = {
    get: function(tabId) {
      if (isFirefox) {
        return browser.tabs.get(tabId);
      } else {
        return new Promise((resolve, reject) => {
          chromeObj.tabs.get(tabId, (tab) => {
            if (chrome.runtime.lastError) {
              reject(chrome.runtime.lastError);
            } else {
              resolve(tab);
            }
          });
        });
      }
    },
    query: function(queryInfo, callback) {
      if (isFirefox) {
        const promise = browser.tabs.query(queryInfo);
        if (callback) {
          promise.then(tabs => callback(tabs));
        }
        return promise;
      } else {
        return chromeObj.tabs.query(queryInfo, callback);
      }
    },
    onUpdated: {
      addListener: function(callback) {
        if (isFirefox) {
          browser.tabs.onUpdated.addListener(callback);
        } else {
          chromeObj.tabs.onUpdated.addListener(callback);
        }
      }
    },
    onActivated: {
      addListener: function(callback) {
        if (isFirefox) {
          browser.tabs.onActivated.addListener(callback);
        } else {
          chromeObj.tabs.onActivated.addListener(callback);
        }
      }
    },
    onRemoved: {
      addListener: function(callback) {
        if (isFirefox) {
          browser.tabs.onRemoved.addListener(callback);
        } else {
          chromeObj.tabs.onRemoved.addListener(callback);
        }
      }
    }
  };

  const runtime = {
    onInstalled: {
      addListener: function(callback) {
        if (isFirefox) {
          browser.runtime.onInstalled.addListener(callback);
        } else {
          chromeObj.runtime.onInstalled.addListener(callback);
        }
      }
    }
  };

  const contextMenus = {
    create: function(createProperties, callback) {
      if (isFirefox) {
        return browser.menus.create(createProperties, callback);
      } else {
        return chromeObj.contextMenus.create(createProperties, callback);
      }
    },
    onClicked: {
      addListener: function(callback) {
        if (isFirefox) {
          browser.menus.onClicked.addListener(callback);
        } else {
          chromeObj.contextMenus.onClicked.addListener(callback);
        }
      }
    },
    exists: function() {
      if (isFirefox) {
        return typeof browser.menus !== 'undefined';
      } else {
        return typeof chromeObj.contextMenus !== 'undefined';
      }
    }
  };

  const scripting = {
    executeScript: function(injection) {
      if (isFirefox) {
        return browser.tabs.executeScript(injection.target.tabId, {
          code: `(${injection.func.toString()})()`
        });
      } else {
        return chromeObj.scripting.executeScript(injection);
      }
    }
  };

  return {
    storage,
    tabs,
    runtime,
    contextMenus,
    scripting
  };
})();
