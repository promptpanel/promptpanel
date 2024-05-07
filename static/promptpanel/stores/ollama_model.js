var localModelState = () => {
  return {
    modalCreateModel: false,
    models: [],
    modelsDownloading: [],
    modelForCreate: {
      customName: false,
      modelName: "",
    },
    createModel() {
      const hostname = window.location.origin;
      const url = hostname + "/api/v1/app/ollama/pull/";
      const data = {
        name: this.modelForCreate.modelName,
        stream: false,
      };
      let modelsInProgress = localStorage.getItem("modelsInProgress");
      this.modelsDownloading = modelsInProgress ? JSON.parse(modelsInProgress) : [];
      if (!this.modelsDownloading.includes(this.modelForCreate.modelName)) {
        this.modelsDownloading.push(this.modelForCreate.modelName);
        localStorage.setItem("modelsInProgress", JSON.stringify(this.modelsDownloading));
      }
      const loadingModelToast = {
        type: "success",
        header: "Loading local model",
        message: "Your model will take a couple minutes to download and load. Feel free to leave the page, it will continue loading in the background.",
      };
      Alpine.store("toastStore").addToast(loadingModelToast);
      this.modalCreateModel = false;
      this.getModels();
      fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify(data),
      })
        .then((response) => response.json())
        .then(() => {
          successToast = {
            type: "success",
            header: "Local model loaded successfully.",
          };
          Alpine.store("toastStore").addToast(successToast);
          this.getModels();
        })
        .catch((error) => {
          failToast = {
            type: "error",
            header: "We had a problem loading your local model. Please try again.",
            message: error.message,
          };
          Alpine.store("toastStore").addToast(failToast);
          this.getModels();
        });
    },
    removeModel(modelName) {
      const hostname = window.location.origin;
      const url = hostname + "/api/v1/app/ollama/delete/";

      const data = {
        name: modelName,
      };
      fetch(url, {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify(data),
      })
        .then((response) => response.json())
        .then(() => {
          successToast = {
            type: "success",
            header: "Local model removed successfully.",
          };
          Alpine.store("toastStore").addToast(successToast);
          this.getModels();
        })
        .catch((error) => {
          failToast = {
            type: "error",
            header: "We had a problem loading your local model. Please try again.",
            message: error.message,
          };
          Alpine.store("toastStore").addToast(failToast);
        });
    },
    getModels() {
      const hostname = window.location.origin;
      const url = hostname + "/api/v1/app/ollama/tags";

      fetch(url, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
      })
        .then((response) => response.json())
        .then((data) => {
          this.models = data.models;
          let modelsInProgress = localStorage.getItem("modelsInProgress");
          let modelsDownloading = modelsInProgress ? JSON.parse(modelsInProgress) : [];
          let filteredModelsDownloading = modelsDownloading.filter((modelName) => !data.models.some((model) => model.name.startsWith(modelName)));
          this.modelsDownloading = filteredModelsDownloading;
          localStorage.setItem("modelsInProgress", JSON.stringify(filteredModelsDownloading));
        })
        .catch((error) => {
          failToast = {
            type: "error",
            header: "We had a problem retrieving your models. Please try again.",
            message: error.message,
          };
          Alpine.store("toastStore").addToast(failToast);
        });
    },
  };
};
