var baseState = () => {
  return {
    panelId: Alpine.store("active").panelId,
    panelData: {},
    panels: [],
    panelSearchInput: "",
    isEditPage: false,
    mobileOpen: false,
    checkEditPage() {
      this.isEditPage = window.location.pathname.includes("panel/edit");
    },
    getPanel() {
      if (this.panelId > 0) {
        const hostname = window.location.origin;
        const url = hostname + "/api/v1/app/panel/" + this.panelId + "/";
        const authToken = document.cookie
          .split("; ")
          .find((row) => row.startsWith("authToken="))
          .split("=")[1];
        fetch(url, {
          method: "GET",
          headers: {
            "Content-Type": "application/json",
            Authorization: "Bearer " + authToken,
          },
        })
          .then((response) => response.json())
          .then((data) => {
            console.log(data);
            this.panelData = data;
          })
          .catch((error) => {
            failToast = {
              type: "error",
              header: "We had a problem retrieving your panel. Please try again.",
              message: error.message,
            };
            Alpine.store("toastStore").addToast(failToast);
          });
      }
    },
    getPanels() {
      const hostname = window.location.origin;
      const url = hostname + "/api/v1/app/panels/";
      const authToken = document.cookie
        .split("; ")
        .find((row) => row.startsWith("authToken="))
        .split("=")[1];
      fetch(url, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer " + authToken,
        },
      })
        .then((response) => response.json())
        .then((data) => {
          this.panels = data;
        })
        .catch((error) => {
          failToast = {
            type: "error",
            header: "We had a problem retrieving your panels. Please try again.",
            message: error.message,
          };
          Alpine.store("toastStore").addToast(failToast);
        });
    },
    get filteredPanels() {
      if (this.panelSearchInput === "") {
        return this.panels;
      }
      return this.panels.filter((panel) => panel.name.toLowerCase().includes(this.panelSearchInput.toLowerCase()) || panel.plugin.toLowerCase().includes(this.panelSearchInput.toLowerCase()));
    },
  };
};

function initializeTheme() {
  if (localStorage.getItem("theme") === "dark") {
    document.body.classList.add("dark");
  } else {
    document.body.classList.add("light");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  // Light / dark theme
  initializeTheme();
  // URL params > toast
  const urlParams = new URLSearchParams(window.location.search);
  if (urlParams.get("created") === "true") {
    successToast = {
      type: "success",
      header: "Panel created successfully",
      message: "Your Panel was created successfully.",
    };
    Alpine.store("toastStore").addToast(successToast);
  }
});
