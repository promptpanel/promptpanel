var userState = () => {
  return {
    user_id: Alpine.store("active").user_id,
    initialEmail: Alpine.store("active").initialEmail,
    email: Alpine.store("active").email,
    username: Alpine.store("active").username,
    password: "",
    passwordRepeat: "",
    userState: {
      emailChanged: false,
      email: false,
      match: false,
      special: false,
      length: false,
    },
    checkUser() {
      if (this.email !== this.initialEmail) {
        this.userState.emailChanged = true;
        const emailRegex = /^[\w-]+(\.[\w-]+)*@([\w-]+\.)+[a-zA-Z]{2,7}$/;
        this.userState.email = emailRegex.test(this.email);
      } else {
        this.userState.emailChanged = false;
      }
    },
    updateUser() {
      if (this.userState.email && this.userState.emailChanged) {
        const hostname = window.location.origin;
        const url = hostname + "/api/v1/users/update/" + this.user_id + "/";
        const data = {
          email: this.email,
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
                header: "Your user account was updated successfully.",
              };
              Alpine.store("toastStore").addToast(successToast);
            } else {
              failToast = {
                type: "error",
                header: "We had a problem updating your account. Please try again.",
                message: data.message,
              };
              Alpine.store("toastStore").addToast(failToast);
            }
          })
          .catch((error) => {
            failToast = {
              type: "error",
              header: "We had a problem updating your account. Please try again.",
              message: error.message,
            };
            Alpine.store("toastStore").addToast(failToast);
          });
      } else {
        failToast = {
          type: "error",
          header: "There was a problem validating the profile information you've entered. Please try again.",
        };
        Alpine.store("toastStore").addToast(failToast);
      }
    },
    checkPassword() {
      const specialChars = /[-!@#$%^&*(),.?":{}|<>]/;
      const containsSpecialChar = specialChars.test(this.password);
      this.userState.special = containsSpecialChar;

      const lengthCheck = this.password.length > 6;
      this.userState.length = lengthCheck;

      if (this.password.length > 0 && this.password === this.passwordRepeat) {
        this.userState.match = true;
      } else {
        this.userState.match = false;
      }
    },
    updatePassword() {
      if (this.userState.length && this.userState.special && this.userState.match) {
        const hostname = window.location.origin;
        const url = hostname + "/api/v1/users/update/" + this.user_id + "/";
        const data = {
          password: this.password,
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
              window.location.href = hostname + "/login/?password_changed=true";
            } else {
              failToast = {
                type: "error",
                header: "We had a problem updating your account. Please try again.",
                message: data.message,
              };
              Alpine.store("toastStore").addToast(failToast);
            }
          })
          .catch((error) => {
            failToast = {
              type: "error",
              header: "We had a problem updating your account. Please try again.",
              message: error.message,
            };
            Alpine.store("toastStore").addToast(failToast);
          });
      } else {
        failToast = {
          type: "error",
          header: "There was a problem validating the password information you've entered. Please try again.",
        };
        Alpine.store("toastStore").addToast(failToast);
      }
    },
  };
};
