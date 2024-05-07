var userManageState = () => {
  return {
    modalCreateUser: false,
    modalModifyUser: false,
    users: [],
    userForCreate: {
      username: "",
      email: "",
      password: "",
      isStaff: false,
      isActive: true,
    },
    userForModify: {
      userId: "",
      username: "",
      email: "",
      password: "",
      isStaff: false,
      isActive: true,
    },
    createUser() {
      const hostname = window.location.origin;
      const url = hostname + "/api/v1/users/create/";

      const data = {
        username: this.userForCreate.username,
        email: this.userForCreate.email,
        password: this.userForCreate.password,
        is_staff: this.userForCreate.isStaff,
        is_active: this.userForCreate.isActive,
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
              header: "User account created successfully.",
            };
            Alpine.store("toastStore").addToast(successToast);
            this.modalCreateUser = false;
            this.getUsers();
          } else {
            failToast = {
              type: "error",
              header: "We had a problem creating the user. Please try again.",
              message: data.message,
            };
            Alpine.store("toastStore").addToast(failToast);
          }
        })
        .catch((error) => {
          failToast = {
            type: "error",
            header: "We had a problem creating the user. Please try again.",
            message: error.message,
          };
          Alpine.store("toastStore").addToast(failToast);
        });
    },
    modifyUser() {
      const hostname = window.location.origin;
      const url = hostname + "/api/v1/users/update/" + this.userForModify.userId + "/";

      const data = {
        username: this.userForModify.username,
        email: this.userForModify.email,
        password: this.userForModify.password,
        is_active: this.userForModify.isActive,
        is_staff: this.userForModify.isStaff,
      };
      fetch(url, {
        method: "PUT",
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
              header: "User was updated successfully.",
            };
            Alpine.store("toastStore").addToast(successToast);
            this.modalModifyUser = false;
            this.getUsers();
          } else {
            failToast = {
              type: "error",
              header: "We had a problem updating the user account. Please try again.",
              message: data.message,
            };
            Alpine.store("toastStore").addToast(failToast);
            this.modalModifyUser = false;
            this.getUsers();
          }
        })
        .catch((error) => {
          failToast = {
            type: "error",
            header: "We had a problem updating the user account. Please try again.",
            message: error.message,
          };
          Alpine.store("toastStore").addToast(failToast);
        });
    },
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
    generatePassword(passwordType) {
      const characters = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz";
      let randomString = "";
      for (let i = 0; i < 16; i++) {
        const randomIndex = Math.floor(Math.random() * characters.length);
        randomString += characters[randomIndex];
      }
      const randomNumber = Math.floor(Math.random() * 9000) + 1000;
      const password = `${randomString}_${randomNumber}`;
      if (passwordType === "create") {
        this.userForCreate.password = password;
      }
      if (passwordType === "update") {
        this.userForModify.password = password;
      }
    },
  };
};
