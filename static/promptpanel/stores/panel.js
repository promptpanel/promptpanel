var panelUpdateState = () => {
  return {
    // Mobile
    activeMobileTab: "pluginSelect",
    // Panel State
    createName: "",
    createDisplayImg: null,
    createSetting: {},
    createUserMode: "adminOnly",
    createUsers: [],
    showAdvanced: false,
    showAccessControls: false,
    // User State
    users: [],
    // Plugin State
    activePluginID: "",
    activePlugin: {},
    plugins: [],
    pluginCategories: [],
    pluginSearchInput: "",
    // Panel Funcs
    getUsers() {
      const hostname = window.location.origin;
      const url = hostname + "/api/v1/users/list/";
      fetch(url, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
      })
        .then((response) => response.json())
        .then((data) => {
          this.users = data;
        })
        .catch((error) => {
          failToast = {
            type: "error",
            header: "We had a problem retrieving your users. Please try again.",
            message: error.message,
          };
          Alpine.store("toastStore").addToast(failToast);
        });
    },
    getPanel() {
      const hostname = window.location.origin;
      const url = hostname + "/api/v1/app/panel/" + Alpine.store("active").panelId + "/";
      fetch(url, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
      })
        .then((response) => response.json())
        .then((data) => {
          this.getPlugins();
          this.createName = data.name;
          this.createDisplayImg = data.display_image;
          this.createSetting = data.meta;
          this.createUsers = data.users_with_access.map((user) => user.id);
          const isGlobal = data.is_global;
          if (isGlobal == true) {
            this.createUserMode = "global";
          } else if (this.createUsers.length > 1) {
            this.createUserMode = "selectUsers";
          } else {
            this.createUserMode = "adminOnly";
          }
          this.activePluginID = data.plugin;
          this.setActivePlugin();
        })
        .catch((error) => {
          failToast = {
            type: "error",
            header: "We had a problem retrieving your panel. Please try again.",
            message: error.message,
          };
          Alpine.store("toastStore").addToast(failToast);
        });
    },
    createPanel() {
      const hostname = window.location.origin;
      const url = hostname + "/api/v1/app/panel/create/";
      const panelData = {
        name: this.createName,
        display_image: this.createDisplayImg,
        plugin: this.activePluginID,
        meta: this.createSetting,
        user_access_ids: this.createUsers,
      };
      if (this.createUserMode == "global") {
        panelData.is_global = true;
      }
      fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify(panelData),
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.status === "success") {
            window.location.href = "/app/" + data.id;
          } else {
            failToast = {
              type: "error",
              header: "We had a problem creating your panel. Please try again.",
              message: data.message,
            };
            Alpine.store("toastStore").addToast(failToast);
          }
        })
        .catch((error) => {
          failToast = {
            type: "error",
            header: "We had a problem creating your panel. Please try again.",
            message: error.message,
          };
          Alpine.store("toastStore").addToast(failToast);
        });
    },
    updatePanel() {
      const hostname = window.location.origin;
      const url = hostname + "/api/v1/app/panel/update/" + Alpine.store("active").panelId + "/";
      const panelData = {
        name: this.createName,
        display_image: this.createDisplayImg,
        plugin: this.activePluginID,
        meta: this.createSetting,
        user_access_ids: this.createUsers,
      };
      if (this.createUserMode == "global") {
        panelData.is_global = true;
      }
      fetch(url, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify(panelData),
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.status === "success") {
            window.location.href = "/app/" + data.id;
          } else {
            failToast = {
              type: "error",
              header: "We had a problem updating your panel. Please try again.",
              message: data.message,
            };
            Alpine.store("toastStore").addToast(failToast);
          }
        })
        .catch((error) => {
          failToast = {
            type: "error",
            header: "We had a problem updating your panel. Please try again.",
            message: error.message,
          };
          Alpine.store("toastStore").addToast(failToast);
        });
    },
    deletePanel() {
      if (!confirm("Are you sure you want to delete this panel?")) {
        return;
      }
      const hostname = window.location.origin;
      const url = hostname + "/api/v1/app/panel/delete/" + Alpine.store("active").panelId + "/";

      fetch(url, {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.status === "success") {
            failToast = {
              type: "success",
              header: "Your panel was deleted successfully.",
            };
            Alpine.store("toastStore").addToast(failToast);
            setTimeout(function () {
              window.location.href = "/app/";
            }, 1000);
          } else {
            failToast = {
              type: "error",
              header: "We had a problem deleting your panel. Please try again.",
              message: data.message,
            };
            Alpine.store("toastStore").addToast(failToast);
          }
        })
        .catch((error) => {
          failToast = {
            type: "error",
            header: "We had a problem deleting your panel. Please try again.",
            message: error.message,
          };
          Alpine.store("toastStore").addToast(failToast);
        });
    },
    displayImgUpload(event) {
      const file = event.target.files[0];
      if (file) {
        if (!file.type.startsWith("image/")) {
          failToast = {
            type: "error",
            header: "Invalid File Type",
            message: "Please upload an image file.",
          };
          Alpine.store("toastStore").addToast(failToast);
          return;
        }
        const reader = new FileReader();
        reader.onloadend = () => {
          this.createDisplayImg = reader.result;
        };
        reader.readAsDataURL(file);
      }
    },
    setInitialSettings(settings) {
      settings.forEach((setting) => {
        if (typeof this.createSetting[setting.name] === "undefined") {
          this.createSetting[setting.name] = setting.default;
        }
      });
    },
    hasAdvancedSettings() {
      if (!this.activePlugin) {
        return false;
      }
      const settings = this.activePlugin.settings;
      if (!Array.isArray(settings)) {
        return false;
      }
      return settings.some((setting) => setting.advanced);
    },
    // Plugin Funcs
    getPlugins() {
      const hostname = window.location.origin;
      const url = hostname + "/api/v1/app/plugins/";

      fetch(url, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
      })
        .then((response) => response.json())
        .then((data) => {
          this.plugins = data;
          this.pluginCategories = [...new Set(data.map((plugin) => plugin.category))].sort((a, b) => a.localeCompare(b));
          this.setActivePlugin();
        })
        .catch((error) => {
          failToast = {
            type: "error",
            header: "We had a problem retrieving your plugins. Please try again.",
            message: error.message,
          };
          Alpine.store("toastStore").addToast(failToast);
        });
    },
    get filteredPlugins() {
      if (this.pluginSearchInput === "") {
        return this.plugins;
      }
      return this.plugins.filter((plugin) => plugin.name.toLowerCase().includes(this.pluginSearchInput.toLowerCase()));
    },
    setActivePlugin() {
      this.activePlugin = this.plugins.find((plugin) => plugin.id === this.activePluginID) || {};
      if (this.activePlugin.settings) {
        this.activeMobileTab = "panelSetting";
        this.setInitialSettings(this.activePlugin.settings);
      }
    },
  };
};
