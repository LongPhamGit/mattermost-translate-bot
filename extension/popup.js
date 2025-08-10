document.getElementById("registerBtn").addEventListener("click", () => {
  const serverUrl = document.getElementById("serverUrl").value;
  const regCode = document.getElementById("regCode").value;
  chrome.runtime.sendMessage({
    action: "register",
    serverUrl,
    regCode
  }, (res) => {
    if (res.success) {
      alert("Registered successfully!");
    } else {
      alert("Registration failed!");
    }
  });
});
