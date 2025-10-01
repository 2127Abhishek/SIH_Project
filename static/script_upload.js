// static/upload.js
document.getElementById("uploadBtn").addEventListener("click", async () => {
  const fileInput = document.getElementById("fileInput");
  const status = document.getElementById("status");
  const jsonOutput = document.getElementById("jsonOutput");

  if (!fileInput.files.length) {
    alert("Select a file first");
    return;
  }

  const file = fileInput.files[0];
  const form = new FormData();
  form.append("file", file);

  status.textContent = "Uploading...";
  jsonOutput.textContent = "";

  try {
    const res = await fetch("/upload", { method: "POST", body: form });
    const data = await res.json();
    if (res.ok) {
      status.textContent = data.message;
      jsonOutput.textContent = JSON.stringify(data.data, null, 2);
    } else {
      status.textContent = data.message || "Server error";
      console.error("Server error:", data);
    }
  } catch (err) {
    status.textContent = "Upload failed (network).";
    console.error(err);
  }
});
