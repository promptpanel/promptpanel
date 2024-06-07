var baseState = () => {
  return {
    panelId: Alpine.store("active").panelId,
    loadedPanels: false,
    modalSearch: false,
    searchResults: [],
    searchType: "all",
    searchInput: "",
    searchLoading: false,
    panelData: {},
    panels: [],
    panelSearchInput: "",
    isEditPage: false,
    mobileOpen: false,
    checkEditPage() {
      this.isEditPage = window.location.pathname.includes("panel/edit");
    },
    getSearchResults() {
      if (this.searchInput.length > 2) {
        this.searchLoading = true;
        const hostname = window.location.origin;
        const url = hostname + "/api/v1/app/search?q=" + this.searchInput;
        fetch(url, {
          method: "GET",
          headers: {
            "Content-Type": "application/json",
          },
          credentials: "include",
        })
          .then((response) => response.json())
          .then((data) => {
            this.searchResults = data;
            this.searchLoading = false;
          })
          .catch((error) => {
            this.searchLoading = false;
            failToast = {
              type: "error",
              header: "We had a problem retrieving your search results. Please try again.",
              message: error.message,
            };
            Alpine.store("toastStore").addToast(failToast);
          });
      }
    },
    getPanel() {
      if (this.panelId > 0) {
        const hostname = window.location.origin;
        const url = hostname + "/api/v1/app/panel/" + this.panelId + "/";
        fetch(url, {
          method: "GET",
          headers: {
            "Content-Type": "application/json",
          },
          credentials: "include",
        })
          .then((response) => response.json())
          .then((data) => {
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
      fetch(url, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
      })
        .then((response) => response.json())
        .then((data) => {
          this.panels = data;
          this.loadedPanels = true;
        })
        .catch((error) => {
          failToast = {
            type: "error",
            header: "We had a problem retrieving your panels. Please try again.",
            message: error.message,
          };
          Alpine.store("toastStore").addToast(failToast);
          this.loadedPanels = true;
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
