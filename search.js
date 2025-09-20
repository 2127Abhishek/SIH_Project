const docs = {
  "Claim": [
    {id: 1, name: "Claim Document 1"},
    {id: 2, name: "Claim Document 2"},
    {id: 3, name: "Claim Document 3"}
  ],
  "Approved": [
    {id: 4, name: "Approved Doc 1"},
    {id: 5, name: "Approved Doc 2"}
  ],
  "Rejected": [
    {id: 6, name: "Rejected Doc 1"}
  ],
  "In Process": [
    {id: 7, name: "In Process Doc 1"},
    {id: 8, name: "In Process Doc 2"}
  ],
  "Denied": [
    {id: 9, name: "Denied Doc 1"},
    {id: 10, name: "Denied Doc 2"}
  ]
};

let currentType = "";

function showButtons() {
  const code = document.getElementById('communityCode').value.trim();
  if (code === "") {
    alert("Please enter a community code.");
    return;
  }
  document.getElementById("resultButtons").style.display = "flex";
  document.getElementById("documentsSection").style.display = "none";
  document.getElementById("filterBar").style.display = "none";
}

function showDocuments(type) {
  currentType = type;
  renderDocs(docs[type]);

  document.getElementById("docTitle").innerText = type + " Documents";
  document.getElementById("documentsSection").style.display = "block";
  document.getElementById("filterBar").style.display = "flex";
}

function renderDocs(list) {
  const docList = document.getElementById("docList");
  docList.innerHTML = "";
  list.forEach(d => {
    let li = document.createElement("li");
    let spanId = document.createElement("span");
    spanId.className = "doc-id";
    spanId.innerText = d.id;
    let spanName = document.createElement("span");
    spanName.innerText = d.name;
    li.appendChild(spanId);
    li.appendChild(spanName);
    docList.appendChild(li);
  });
}

function filterDocs(mode) {
  if (!currentType) return;
  if (mode === "all") {
    renderDocs(docs[currentType]);
  } else if (mode === "id") {
    const idVal = parseInt(document.getElementById("docIdInput").value);
    if (isNaN(idVal)) {
      alert("Please enter a valid ID.");
      return;
    }
    const filtered = docs[currentType].filter(d => d.id === idVal);
    if (filtered.length === 0) {
      alert("No document found with ID " + idVal);
    }
    renderDocs(filtered);
  }
}
