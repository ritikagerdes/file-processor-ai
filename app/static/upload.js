// Minimal chunked upload client
const form = document.getElementById("upload-form");
const fileInput = document.getElementById("file");
const projectInput = document.getElementById("project");
const chunkSizeInput = document.getElementById("chunk-size");
const status = document.getElementById("status");
const bar = document.getElementById("bar");
const progressWrap = document.querySelector(".progress");

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const file = fileInput.files[0];
  if (!file) { status.textContent = "Choose a file"; return; }
  const project = projectInput.value || "default";
  const chunkSize = Number(chunkSizeInput.value) || 262144;
  const totalChunks = Math.ceil(file.size / chunkSize);
  progressWrap.style.display = "block";
  for (let i = 0; i < totalChunks; i++) {
    const start = i * chunkSize;
    const end = Math.min(file.size, start + chunkSize);
    const blob = file.slice(start, end);
    const fd = new FormData();
    fd.append("project", project);
    fd.append("filename", file.name);
    fd.append("chunk_index", String(i));
    fd.append("total_chunks", String(totalChunks));
    fd.append("data", blob, file.name);
    try {
      const res = await fetch("/upload", { method: "POST", body: fd });
      if (!res.ok) {
        const txt = await res.text();
        status.textContent = `Upload failed: ${res.status} ${txt}`;
        return;
      }
      const j = await res.json();
      status.textContent = `Uploaded chunk ${i+1}/${totalChunks} — ${file.name}`;
      bar.style.width = `${Math.round(((i+1)/totalChunks) * 100)}%`;
      // when server assembled, show assembled path
      if (j.assembled) {
        status.textContent = `Assembled: ${j.assembled} (embeddings_len=${j.embeddings_len})`;
      }
    } catch (err) {
      status.textContent = `Upload error: ${err}`;
      return;
    }
  }
  status.textContent = "Upload complete";
});