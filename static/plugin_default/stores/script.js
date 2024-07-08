var pluginState = () => {
  return {
    // Mobile
    mobileOpen: false,
    // Loaded State
    loadedThreads: false,
    loadedMessages: false,
    // Threads
    threadLimit: 100000,
    activeThread: {},
    threadSearchInput: "",
    threads: [],
    // Model Select
    isOllama: false,
    ollamaModels: [],
    activeOllamaModel: false,
    ollamaNotFoundError: false,
    selectedOllamaModel: null,
    // Messages
    messageLimit: 40,
    messages: [],
    responseStream: "",
    messageFormatted: "",
    messageFromEditor: "",
    messageAbortController: null,
    // Message UI
    osPlatform: "",
    // Files
    fileLimit: 100000,
    files: [],
    filesQueue: [],
    isFileDragged: false,
    fileStream: "Processing Upload...",
    // Images
    extractedImages: [],
    messageImages: [],
    // Modals
    modalSelectModel: false,
    modalThreadEdit: false,
    modalMessageEdit: false,
    modalDocuments: false,
    modalMessageId: 0,
    threadNameForUpdate: "",
    messageForUpdate: "",
    // Indicators
    indicateProcessing: false,
    indicateFile: false,
    // Page-load Redirects
    redirectMessage() {
      panelId = Alpine.store("active").panelId;
      threadId = Alpine.store("active").threadId;
      hostname = window.location.origin;
      let redirectUrl = null;
      if (panelId && threadId) {
        redirectUrl = `${hostname}/panel/${panelId}/${threadId}/`;
        window.location.href = redirectUrl;
      } else {
        console.error("panelId or threadId not found.");
      }
    },
    redirectPanel() {
      const panelId = Alpine.store("active").panelId;
      const hostname = window.location.origin;
      const url = hostname + "/api/v1/app/threads/panel/" + panelId + "/";
      fetch(url, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
      })
        .then((response) => response.json())
        .then((data) => {
          this.threads = data;
          // Create a new thread if none exist
          if (this.threads.length === 0) {
            this.createThread();
          } else {
            const maxThread = this.threads.reduce((prev, current) => (prev.id > current.id ? prev : current));
            window.location.href = "/panel/" + Alpine.store("active").panelId + "/" + maxThread.id + "/";
          }
        })
        .catch((error) => {
          failToast = {
            type: "error",
            header: "We had a problem retrieving your threads. Please try again.",
            message: error.message,
          };
          Alpine.store("toastStore").addToast(failToast);
        });
    },
    // Models
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
          this.ollamaModels = data.models;
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
    setModel(showToast = true) {
      const hostname = window.location.origin;
      const url = hostname + "/api/v1/app/thread/update/" + Alpine.store("active").threadId + "/";
      const threadData = {
        meta: { ollamaModel: this.selectedOllamaModel },
      };
      fetch(url, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify(threadData),
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.status === "success") {
            if (showToast) {
              successToast = {
                type: "success",
                header: "Your model has been updated.",
              };
              Alpine.store("toastStore").addToast(successToast);
            }
            this.getThreads();
            this.getModels();
            this.modalSelectModel = false;
          }
        })
        .catch((error) => {
          failToast = {
            type: "error",
            header: "We had a problem updating your model. Please try again.",
            message: error.message,
          };
          Alpine.store("toastStore").addToast(failToast);
        });
    },
    // Threads
    createThread() {
      const hostname = window.location.origin;
      const url = hostname + "/api/v1/app/thread/create/";
      const threadData = {
        title: "New Thread",
        panel_id: Alpine.store("active").panelId,
      };
      fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify(threadData),
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.status === "success") {
            window.location.href = "/panel/" + Alpine.store("active").panelId + "/" + data.id + "/";
          } else {
            console.error(data);
            failToast = {
              type: "error",
              header: "We had a problem creating your thread. Please try again.",
              message: data.message,
            };
            Alpine.store("toastStore").addToast(failToast);
          }
        })
        .catch((error) => {
          console.error(error);
          failToast = {
            type: "error",
            header: "We had a problem creating your thread. Please try again.",
            message: error.message,
          };
          Alpine.store("toastStore").addToast(failToast);
        });
    },
    getThreads() {
      const hostname = window.location.origin;
      const url = hostname + "/api/v1/app/threads/panel/" + Alpine.store("active").panelId + "/?limit=" + this.threadLimit;
      fetch(url, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
      })
        .then((response) => response.json())
        .then((data) => {
          this.threads = data;
          // Create a new thread if none exist
          if (this.threads.length === 0) {
            this.createThread();
          }
          this.setActiveThread();
          this.loadedThreads = true;
        })
        .catch((error) => {
          failToast = {
            type: "error",
            header: "We had a problem retrieving your threads. Please try again.",
            message: error.message,
          };
          Alpine.store("toastStore").addToast(failToast);
          this.loadedThreads = true;
        });
    },
    deleteThread() {
      if (!confirm("Are you sure you want to delete this thread?")) {
        return;
      }
      const hostname = window.location.origin;
      const url = hostname + "/api/v1/app/thread/delete/" + Alpine.store("active").threadId + "/";
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
            window.location.href = "/panel/" + Alpine.store("active").panelId + "/?deleted=true";
          } else {
            failToast = {
              type: "error",
              header: "We had a problem deleting your thread. Please try again.",
              message: data.message,
            };
            Alpine.store("toastStore").addToast(failToast);
          }
        })
        .catch((error) => {
          failToast = {
            type: "error",
            header: "We had a problem deleting your thread. Please try again.",
            message: error.message,
          };
          Alpine.store("toastStore").addToast(failToast);
        });
    },
    updateThread() {
      const hostname = window.location.origin;
      const url = hostname + "/api/v1/app/thread/update/" + Alpine.store("active").threadId + "/";
      const threadData = {
        title: this.threadNameForUpdate,
      };
      fetch(url, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify(threadData),
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.status === "success") {
            successToast = {
              type: "success",
              header: "Your thread has been updated.",
            };
            Alpine.store("toastStore").addToast(successToast);
            this.getThreads();
            this.modalThreadEdit = false;
          }
        })
        .catch((error) => {
          failToast = {
            type: "error",
            header: "We had a problem updating your thread. Please try again.",
            message: error.message,
          };
          Alpine.store("toastStore").addToast(failToast);
        });
    },
    cloneThread() {
      const hostname = window.location.origin;
      const url = hostname + "/api/v1/app/thread/duplicate/" + Alpine.store("active").threadId + "/";
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
              header: "Your thread has been duplicated.",
            };
            Alpine.store("toastStore").addToast(successToast);
            this.getThreads();
          }
        })
        .catch((error) => {
          failToast = {
            type: "error",
            header: "We had a problem updating your thread. Please try again.",
            message: error.message,
          };
          Alpine.store("toastStore").addToast(failToast);
        });
    },
    retryThread() {
      if (!confirm("Are you sure you want to retry this message (your last message will be replaced)?")) {
        return;
      }
      let mdConverter = new showdown.Converter();
      // Streaming container for WIP generation
      let streaming = "";
      // Prune the last message locally in order to retry creating
      let maxId = -1;
      this.messages.forEach((message) => {
        if (message.id > maxId) maxId = message.id;
      });
      this.messages = this.messages.filter((message) => message.id !== maxId);
      this.messageAbortController = new AbortController();
      this.indicateProcessing = true;
      let isCancelled = false;
      const hostname = window.location.origin;
      const url = hostname + "/api/v1/app/thread/retry/" + Alpine.store("active").threadId + "/";
      fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        signal: this.messageAbortController.signal,
      })
        .then((response) => {
          if (!response.ok) {
            return response.json().then((errorBody) => {
              throw new Error(errorBody.message || "Unknown error occurred");
            });
          }
          return response.body.getReader();
        })
        .then((reader) => {
          return new ReadableStream({
            start: (controller) => {
              const push = () => {
                reader
                  .read()
                  .then(({ done, value }) => {
                    if (done) {
                      controller.close();
                      return;
                    }
                    const string = new TextDecoder().decode(value);
                    streaming += string;
                    this.responseStream = mdConverter.makeHtml(streaming);
                    controller.enqueue(value);
                    push();
                  })
                  .catch((error) => {
                    if (error.name === "AbortError") {
                      isCancelled = true;
                      controller.error(error);
                      console.log("Message cancelled");
                    } else {
                      controller.error(error);
                    }
                  });
              };
              push();
            },
            cancel: () => {
              isCancelled = true;
              console.log("Stream cancelled");
            },
          });
        })
        .then((stream) => new Response(stream).text())
        .catch((error) => {
          if (error.name === "AbortError" || isCancelled) {
            console.log("Message cancelled");
            this.responseStream = "Message cancelled.";
          } else {
            const failToast = {
              type: "error",
              header: "We had a problem retrieving your message response. Please try again.",
              message: error.message,
            };
            Alpine.store("toastStore").addToast(failToast);
          }
        })
        .finally(() => {
          console.log("Trigger finally...");
          if (isCancelled) {
            const successToast = {
              type: "success",
              header: "Message cancelled",
              message: "Your message was cancelled successfully.",
            };
            Alpine.store("toastStore").addToast(successToast);
          }
          this.getMessages();
          this.getThreads();
          this.messageFormatted = "";
          this.extractedImages = [];
          this.indicateProcessing = false;
          this.messageAbortController = null;
        });
    },
    get filteredThreads() {
      if (this.threadSearchInput === "") {
        return this.threads;
      }
      return this.threads.filter((thread) => thread.title.toLowerCase().includes(this.threadSearchInput.toLowerCase()));
    },
    setActiveThread() {
      // Scroll placement
      setTimeout(() => {
        const sidebar = document.getElementById("sidebar");
        const activeLink = document.getElementById("active-link");
        if (activeLink) {
          const topPos = activeLink.offsetTop;
          sidebar.scrollTop = topPos - sidebar.offsetTop - 84;
        }
      }, 80);
      // Load thread
      this.activeThread = this.threads.find((thread) => thread.id === Alpine.store("active").threadId) || {};
      if (typeof this.activeThread.meta === "string") {
        try {
          this.activeThread.meta = JSON.parse(this.activeThread.meta);
        } catch (e) {
          console.warn("Error parsing thread meta:", e);
          this.activeThread.meta = {};
        }
      }
      // Set Ollama active model / default model
      if (this.isOllama) {
        this.activeOllamaModel = this.activeThread.meta && this.activeThread.meta.ollamaModel ? this.activeThread.meta.ollamaModel : null;
        setTimeout(() => {
          if (!this.activeThread.meta || !this.activeThread.meta.ollamaModel) {
            // Update missing model
            if (this.ollamaModels) {
              this.selectedOllamaModel = this.ollamaModels[0].name;
              this.setModel(false);
            }
          } else {
            // Check active model vs ollama stack
            if (this.activeOllamaModel !== null) {
              const modelFound = this.ollamaModels.some((model) => model.name === this.activeOllamaModel);
              if (!modelFound) {
                this.ollamaNotFoundError = true;
              }
            }
          }
        }, 500);
      }
    },
    autoExpand(field) {
      field.style.height = "inherit";
      var computed = window.getComputedStyle(field);
      var height = parseInt(computed.getPropertyValue("border-top-width"), 10) + parseInt(computed.getPropertyValue("padding-top"), 10) + field.scrollHeight + parseInt(computed.getPropertyValue("padding-bottom"), 10) + parseInt(computed.getPropertyValue("border-bottom-width"), 10) - 15;
      field.style.height = height + "px";
    },
    // Messages
    addPrompt(prompt) {
      if (!this.messageFromEditor.startsWith(prompt)) {
        if (!confirm("Are you sure you want to add this prompt, your current message will be replaced?")) {
          return;
        }
        this.messageFromEditor = prompt;
      }
    },
    createMessageSubmit() {
      if (typeof window.clarity === "function") {
        window.clarity("event", "messageSent");
      }
      // Streaming container for WIP generation
      let streaming = "";
      let mdConverter = new showdown.Converter();
      this.messageFromEditor = this.messageFromEditor.replace(/</g, "&lt;").replace(/>/g, "&gt;");
      this.messageFormatted = mdConverter.makeHtml(this.messageFromEditor);
      const hostname = window.location.origin;
      const url = hostname + "/api/v1/app/message/create/";
      const messageData = {
        content: this.messageFromEditor,
        meta: { sender: "user", images: this.extractedImages },
        panel_id: Alpine.store("active").panelId,
        thread_id: Alpine.store("active").threadId,
      };
      this.messageImages = this.extractedImages;
      // Wipe interim message before sending
      this.extractedImages = [];
      this.messageFromEditor = "";
      // Set abort controller => indicate processing => positioning div
      this.messageAbortController = new AbortController();
      this.indicateProcessing = true;
      let isCancelled = false;
      setTimeout(() => {
        document.getElementById("processingChat").scrollIntoView();
      }, 80);
      fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify(messageData),
        signal: this.messageAbortController.signal,
      })
        .then((response) => {
          if (!response.ok) {
            return response.json().then((errorBody) => {
              throw new Error(errorBody.message || "Unknown error occurred");
            });
          }
          return response.body.getReader();
        })
        .then((reader) => {
          return new ReadableStream({
            start: (controller) => {
              const push = () => {
                reader
                  .read()
                  .then(({ done, value }) => {
                    if (done) {
                      controller.close();
                      return;
                    }
                    const string = new TextDecoder().decode(value);
                    streaming += string;
                    this.responseStream = mdConverter.makeHtml(streaming);
                    controller.enqueue(value);
                    push();
                  })
                  .catch((error) => {
                    if (error.name === "AbortError") {
                      isCancelled = true;
                      controller.error(error);
                      console.log("Message cancelled");
                    } else {
                      controller.error(error);
                    }
                  });
              };
              push();
            },
            cancel: () => {
              isCancelled = true;
              console.log("Stream cancelled");
            },
          });
        })
        .then((stream) => new Response(stream).text())

        .catch((error) => {
          if (error.name === "AbortError" || isCancelled) {
            console.log("Message cancelled");
            this.responseStream = "Message cancelled.";
          } else {
            const failToast = {
              type: "error",
              header: "We had a problem retrieving your message response. Please try again.",
              message: error.message,
            };
            Alpine.store("toastStore").addToast(failToast);
          }
        })
        .finally(() => {
          console.log("Trigger finally...");
          if (isCancelled) {
            const successToast = {
              type: "success",
              header: "Message cancelled",
              message: "Your message was cancelled successfully.",
            };
            Alpine.store("toastStore").addToast(successToast);
          }
          this.getMessages();
          this.getThreads();
          this.messageFormatted = "";
          this.extractedImages = [];
          this.indicateProcessing = false;
          this.messageAbortController = null;
        });
    },
    cancelMessageRequest() {
      if (this.messageAbortController) {
        this.messageAbortController.abort();
        this.messageAbortController = null;
        this.indicateProcessing = false;
        this.responseStream = "";
      }
    },
    getMessages(incrementLimit = false, setLimit = true) {
      const hostname = window.location.origin;
      if (incrementLimit) {
        this.messageLimit = this.messageLimit + 40;
      }
      if (setLimit) {
        this.messageLimit = 40;
      }
      const url = hostname + "/api/v1/app/messages/thread/" + Alpine.store("active").threadId + "/?limit=" + this.messageLimit;
      fetch(url, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
      })
        .then((response) => response.json())
        .then((data) => {
          let mdConverter = new showdown.Converter();
          // Reset message state
          this.messageFormatted = "";
          this.messageImages = [];
          this.responseStream = "";
          // Add new messages (re-sorted by date)
          this.messages = data.sort((a, b) => new Date(a.created_on) - new Date(b.created_on));
          console.log(this.messages);
          this.newMessage = "";
          this.newRawMessage = "";
          setTimeout(() => {
            // Convert any markdown fields (which aren't converted by default)
            document.querySelectorAll(".markdown-convert").forEach((element) => {
              var markdownText = element.textContent;
              var html = mdConverter.makeHtml(markdownText);
              element.innerHTML = html;
            });
            // Check for any un-highlighted blocks (default to bash)
            document.querySelectorAll("pre code").forEach((block) => {
              if (!block.classList.contains("hljs")) {
                hljs.highlightElement(block);
              }
              if (!block.classList.contains("hljs")) {
                block.classList.add("language-bash");
                block.classList.add("bash");
                hljs.highlightElement(block);
              }
            });
            // Add Copy Code Control
            document.querySelectorAll("pre").forEach((codeBlock) => {
              // Remove existing copy buttons
              let existingCopyButtonAbove = codeBlock.previousElementSibling;
              if (existingCopyButtonAbove && existingCopyButtonAbove.classList.contains("copyCodeBtn")) {
                existingCopyButtonAbove.remove();
              }
              let existingCopyButtonBelow = codeBlock.nextElementSibling;
              if (existingCopyButtonBelow && existingCopyButtonBelow.classList.contains("copyCodeBtn")) {
                existingCopyButtonBelow.remove();
              }
              // Create button above
              let wrapperDivAbove = document.createElement("div");
              wrapperDivAbove.classList.add("flex", "w-full", "-mb-[1.7142857em]", "bg-slate-900", "rounded-t-md");
              let copyButtonAbove = document.createElement("button");
              copyButtonAbove.textContent = "📋 Copy";
              copyButtonAbove.classList.add("copyCodeBtn", "bg-transparent", "text-stone-400", "px-3", "py-2", "ml-auto", "text-base", "inline-block", "hover:text-stone-50");
              copyButtonAbove.addEventListener("click", () => {
                let text = codeBlock.textContent;
                navigator.clipboard.writeText(text).then(() => {
                  copyButtonAbove.textContent = "✅ Copied!";
                  setTimeout(() => {
                    copyButtonAbove.textContent = "📋 Copy";
                  }, 2000);
                });
              });
              wrapperDivAbove.appendChild(copyButtonAbove);
              codeBlock.parentNode.insertBefore(wrapperDivAbove, codeBlock);
              // Create button below
              let wrapperDivBelow = document.createElement("div");
              wrapperDivBelow.classList.add("flex", "w-full", "-mt-[1.7142857em]", "bg-slate-900", "rounded-b-md");
              let copyButtonBelow = document.createElement("button");
              copyButtonBelow.textContent = "📋 Copy";
              copyButtonBelow.classList.add("copyCodeBtn", "bg-transparent", "text-stone-400", "px-3", "py-2", "ml-auto", "text-base", "inline-block", "hover:text-stone-50");
              copyButtonBelow.addEventListener("click", () => {
                let text = codeBlock.textContent;
                navigator.clipboard.writeText(text).then(() => {
                  copyButtonBelow.textContent = "✅ Copied!";
                  setTimeout(() => {
                    copyButtonBelow.textContent = "📋 Copy";
                  }, 2000);
                });
              });
              wrapperDivBelow.appendChild(copyButtonBelow);
              codeBlock.parentNode.insertBefore(wrapperDivBelow, codeBlock.nextSibling);
            });
            // Scroll to top (as long as not using pagination)
            if (!incrementLimit) {
              document.querySelector("#content-area").scrollTop = document.querySelector("#content-area").scrollHeight;
            }
          }, 80);
          this.loadedMessages = true;
        })
        .catch((error) => {
          failToast = {
            type: "error",
            header: "We had a problem retrieving your messages. Please try again.",
            message: error.message,
          };
          Alpine.store("toastStore").addToast(failToast);
          this.loadedMessages = true;
        });
    },
    deleteMessage(messageId) {
      if (!confirm("Are you sure you want to delete this message?")) {
        return;
      }
      const hostname = window.location.origin;
      const url = `${hostname}/api/v1/app/message/delete/${messageId}/`;
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
            successToast = {
              type: "success",
              header: "Successfully deleted your message.",
            };
            Alpine.store("toastStore").addToast(successToast);
            this.getMessages();
            this.modalMessageEdit = false;
          } else {
            failToast = {
              type: "error",
              header: "We had a problem deleting your message. Please try again.",
              message: data.message,
            };
            Alpine.store("toastStore").addToast(failToast);
          }
        })
        .catch((error) => {
          failToast = {
            type: "error",
            header: "We had a problem deleting your message. Please try again.",
            message: error.message,
          };
          Alpine.store("toastStore").addToast(failToast);
        });
    },
    updateMessage(messageId) {
      const hostname = window.location.origin;
      const url = `${hostname}/api/v1/app/message/update/${messageId}/`;
      const messageData = {
        content: this.messageForUpdate,
      };
      fetch(url, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify(messageData),
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.status === "success") {
            successToast = {
              type: "success",
              header: "Your message has been updated.",
            };
            Alpine.store("toastStore").addToast(successToast);
            this.getMessages();
            this.modalMessageEdit = false;
          }
        })
        .catch((error) => {
          failToast = {
            type: "error",
            header: "We had a problem updating your message. Please try again.",
            message: error.message,
          };
          Alpine.store("toastStore").addToast(failToast);
        });
    },
    // Files
    getFiles() {
      const hostname = window.location.origin;
      const url = hostname + "/api/v1/app/files/thread/" + Alpine.store("active").threadId + "/?limit=" + this.fileLimit;
      fetch(url, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
      })
        .then((response) => response.json())
        .then((data) => {
          this.files = data.reverse();
        })
        .catch((error) => {
          failToast = {
            type: "error",
            header: "We had a problem retrieving your files. Please try again.",
            message: error.message,
          };
          Alpine.store("toastStore").addToast(failToast);
        });
    },
    handleFiles(event, isDrop) {
      let filesArray = isDrop ? event.dataTransfer.files : event.target.files;
      this.filesQueue = Array.from(filesArray).map((f) => ({ file: f, filename: f.name, status: "queued" }));
      this.processNextFile();
    },
    processNextFile() {
      let nextFile = this.filesQueue.find((f) => f.status === "queued");
      if (nextFile) {
        this.createFileSubmit(nextFile);
      }
    },
    createFileSubmit(fileItem) {
      fileItem.status = "uploading";
      let mdConverter = new showdown.Converter();
      let formData = new FormData();
      let fileStatus = "";
      const fileObj = fileItem.file;
      formData.append("file", fileObj);
      formData.append("panel_id", Alpine.store("active").panelId);
      formData.append("thread_id", Alpine.store("active").threadId);
      const hostname = window.location.origin;
      const url = hostname + "/api/v1/app/file/create/";
      this.indicateFile = true;
      setTimeout(() => {
        document.getElementById("processingChat").scrollIntoView();
      }, 80);
      const controller = new AbortController();
      fileItem.controller = controller;
      fetch(url, {
        method: "POST",
        credentials: "include",
        body: formData,
        signal: controller.signal,
      })
        .then((response) => {
          if (!response.ok) {
            response
              .clone()
              .json()
              .then((errorBody) => {
                const errorMessage = errorBody.message || "Unknown error occurred";
                let failToast = {
                  type: "error",
                  header: "We had a problem processing your uploaded file. Please try again.",
                  message: errorMessage,
                };
                Alpine.store("toastStore").addToast(failToast);
                fileItem.status = "error";
                this.getFiles();
                this.processNextFile();
              })
              .catch((err) => {
                console.error("Error parsing response error body:", err);
                fileItem.status = "error";
                this.getFiles();
                this.processNextFile();
              });
          }
          return response.body.getReader();
        })
        .then((reader) => {
          return new ReadableStream({
            start: (controller) => {
              const push = () => {
                reader
                  .read()
                  .then(({ done, value }) => {
                    if (done) {
                      controller.close();
                      this.indicateFile = false;
                      this.fileStream = "";
                      fileItem.status = "completed";
                      this.processNextFile();
                      this.getFiles();
                      this.getMessages();
                      return;
                    }
                    const string = new TextDecoder().decode(value);
                    // fileStatus += string;
                    this.fileStream = mdConverter.makeHtml(string);
                    controller.enqueue(value);
                    push();
                  })
                  .catch((error) => {
                    failToast = {
                      type: "error",
                      header: "We had a problem retrieving your message response. Please try again.",
                      message: error.message,
                    };
                    Alpine.store("toastStore").addToast(failToast);
                    fileItem.status = "error";
                    this.indicateFile = false;
                    this.getFiles();
                    this.processNextFile();
                  });
              };
              push();
            },
          });
        })
        .then((stream) => new Response(stream))
        .then((response) => response.text())
        .catch((err) => {
          if (err.name === "AbortError") {
            fileItem.status = "cancelled";
            this.indicateFile = false;
            this.processNextFile();
          } else {
            failToast = {
              type: "error",
              header: "We had a problem processing your uploaded file. Please try again.",
              message: err.message,
            };
            Alpine.store("toastStore").addToast(failToast);
            fileItem.status = "error";
            this.indicateFile = false;
            this.processNextFile();
          }
        });
    },
    cancelUpload(fileItem) {
      if (fileItem.status === "completed" || fileItem.status === "cancelled") {
        this.filesQueue = this.filesQueue.filter((f) => f !== fileItem);
      } else {
        if (!confirm("Are you sure you want to cancel your file upload?")) {
          return;
        }
        if (fileItem.status === "uploading") {
          if (fileItem.controller) {
            fileItem.controller.abort();
          }
        } else {
          this.filesQueue = this.filesQueue.filter((f) => f !== fileItem);
        }
      }
    },
    updateFileEnableState(file, isEnabled) {
      file.meta.enabled = isEnabled;
      this.updateFile(file.id, file.filename, file.meta);
    },
    updateFile(fileId, fileName, metadata, showToast = false) {
      const hostname = window.location.origin;
      const url = hostname + "/api/v1/app/file/update/" + fileId + "/";
      const fileData = {
        filename: fileName,
        meta: metadata,
      };
      fetch(url, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify(fileData),
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.status === "success" && showToast === true) {
            successToast = {
              type: "success",
              header: "Your file has been updated.",
            };
            Alpine.store("toastStore").addToast(successToast);
            this.getFiles();
          }
        })
        .catch((error) => {
          failToast = {
            type: "error",
            header: "We had a problem updating your file. Please try again.",
            message: error.message,
          };
          Alpine.store("toastStore").addToast(failToast);
        });
    },
    getEnabledDocumentsCount() {
      return this.files.filter((file) => file.meta?.enabled).length;
    },
    deleteFile(fileId) {
      if (!confirm("Are you sure you want to delete this file?")) {
        return;
      }
      const hostname = window.location.origin;
      const fileUrl = `${hostname}/api/v1/app/file/delete/${fileId}/`;
      fetch(fileUrl, {
        method: "DELETE",
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
              header: "Successfully deleted your file.",
            };
            Alpine.store("toastStore").addToast(successToast);
            this.getFiles();
          } else {
            failToast = {
              type: "error",
              header: "We had a problem deleting your file. Please try again.",
              message: data.message,
            };
            Alpine.store("toastStore").addToast(failToast);
          }
        })
        .catch((error) => {
          failToast = {
            type: "error",
            header: "We had a problem deleting your file. Please try again.",
            message: error.message,
          };
          Alpine.store("toastStore").addToast(failToast);
        });
    },
    // Images
    imageUpload(event) {
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
          const newImage = reader.result;
          this.extractedImages.push(newImage);
        };
        reader.readAsDataURL(file);
      }
    },
    imageUploadRemove(index) {
      this.extractedImages.splice(index, 1);
    },
    // Utilities
    get matchedActions() {
      if (this.messageFromEditor === "") {
        return [];
      }
      if (!this.messageFromEditor.startsWith("/")) {
        return [];
      }
      let firstWord = this.messageFromEditor.split(" ")[0];
      let actionSet = Alpine.store("actionStore").actions;
      return actionSet.filter((action) => action.command.startsWith(firstWord));
    },
    isLastAssistantMessage(messageId) {
      let lastAssistantMessageId = this.messages.reduce((lastId, current) => {
        return current.meta?.sender == "assistant" ? current.id : lastId;
      }, null);
      return messageId === lastAssistantMessageId;
    },
    formatDate: function (datetime) {
      const date = new Date(datetime); // parse the datetime string into a Date object
      const year = date.getFullYear();
      const month = ("0" + (date.getMonth() + 1)).slice(-2); // getMonth() returns 0-11, so we add 1
      const day = ("0" + date.getDate()).slice(-2); // getDate() returns the day of the month
      const hour = ("0" + (date.getHours() > 12 ? date.getHours() - 12 : date.getHours())).slice(-2); // getHours() returns the hour (0-23), convert to 12-hour format
      const minute = ("0" + date.getMinutes()).slice(-2); // getMinutes() returns the minute (0-59)
      const ampm = date.getHours() >= 12 ? "PM" : "AM";
      return `${year}/${month}/${day} at ${hour}:${minute}${ampm}`;
    },
    getOS() {
      let platform = window.navigator.platform;
      if (/^Mac/.test(platform)) {
        this.osPlatform = "mac";
      } else if (/^Win/.test(platform)) {
        this.osPlatform = "windows";
      } else {
        this.osPlatform = "other";
      }
    },
    copyToClipboard(text, type) {
      // Copy text to clipboard
      successToast = {
        type: "success",
        header: "Successfully copied your {type} to clipboard.",
      };
      Alpine.store("toastStore").addToast(successToast);
    },
    copyToClipboard(text, type) {
      try {
        // Use the Clipboard API for modern browsers
        navigator.clipboard.writeText(text).then(() => {
          Alpine.store("toastStore").addToast({
            type: "success",
            header: `Successfully copied your ${type} to clipboard.`,
          });
        });
      } catch (error) {
        // Fallback for older browsers or if Clipboard API fails
        const textArea = document.createElement("textarea");
        textArea.value = text;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand("copy");
        document.body.removeChild(textArea);
        Alpine.store("toastStore").addToast({
          type: "success",
          header: `Successfully copied your ${type} to clipboard.`,
        });
      }
    },
    insertTab(event) {
      let textarea = event.target;
      let start = textarea.selectionStart;
      let end = textarea.selectionEnd;
      textarea.value = textarea.value.substring(0, start) + "\t" + textarea.value.substring(end);
      textarea.selectionStart = textarea.selectionEnd = start + 1;
      event.preventDefault();
    },
  };
};

// Querystring
document.addEventListener("DOMContentLoaded", () => {
  // Querystring > delete thread
  const urlParams = new URLSearchParams(window.location.search);
  if (urlParams.get("deleted") === "true") {
    successToast = {
      type: "success",
      header: "Thread deleted successfully",
      message: "Your thread was deleted successfully.",
    };
    Alpine.store("toastStore").addToast(successToast);
  }
});
