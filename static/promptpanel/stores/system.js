var systemState = () => {
  return {
    email: Alpine.store("active").email,
    licence_email: "",
    licence_key: "",
    modalLicenceInfo: false,
    activateTrial() {
      const hostname = window.location.origin;
      const url = hostname + "/api/v1/users/licence/trial/";
      const data = {
        email: this.email,
      };
      fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify(data),
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.status === "success") {
            successToast = {
              type: "success",
              header: "Your trial licence has been activated successfully.",
            };
            Alpine.store("toastStore").addToast(successToast);
            setTimeout(function () {
              window.location.reload();
            }, 2000);
          } else {
            failToast = {
              type: "error",
              header: "We had a problem activating your trial licence. Please contact support@promptpanel.com",
              message: data.message,
            };
            Alpine.store("toastStore").addToast(failToast);
          }
        })
        .catch((error) => {
          failToast = {
            type: "error",
            header: "We had a problem activating your trial licence. Please contact support@promptpanel.com",
            message: error.message,
          };
          Alpine.store("toastStore").addToast(failToast);
        });
    },
    setLicence() {
      const hostname = window.location.origin;
      const url = hostname + "/api/v1/users/licence/set/";

      const data = {
        email: this.licence_email,
        licence_key: this.licence_key,
      };
      fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify(data),
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.status === "success") {
            successToast = {
              type: "success",
              header: "Your licence has been updated successfully.",
            };
            Alpine.store("toastStore").addToast(successToast);
            setTimeout(function () {
              window.location.reload();
            }, 2000);
          } else {
            failToast = {
              type: "error",
              header: "We had a problem updating your licence. Please contact support@promptpanel.com",
              message: data.message,
            };
            Alpine.store("toastStore").addToast(failToast);
          }
        })
        .catch((error) => {
          failToast = {
            type: "error",
            header: "We had a problem updating your licence. Please contact support@promptpanel.com",
            message: error.message,
          };
          Alpine.store("toastStore").addToast(failToast);
        });
    },
    downgradeLicence() {
      const isConfirmed = window.confirm("Are you sure you want to downgrade your licence?");
      if (!isConfirmed) {
        return;
      }
      const hostname = window.location.origin;
      const url = hostname + "/api/v1/users/licence/downgrade/";

      fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.status === "success") {
            successToast = {
              type: "success",
              header: "Your licence has been downgraded successfully.",
            };
            Alpine.store("toastStore").addToast(successToast);
            setTimeout(function () {
              window.location.reload();
            }, 2000);
          } else {
            failToast = {
              type: "error",
              header: "We had a problem downgraded your licence. Please contact support@promptpanel.com",
              message: data.message,
            };
            Alpine.store("toastStore").addToast(failToast);
          }
        })
        .catch((error) => {
          failToast = {
            type: "error",
            header: "We had a problem downgraded your licence. Please contact support@promptpanel.com",
            message: error.message,
          };
          Alpine.store("toastStore").addToast(failToast);
        });
    },
  };
};
