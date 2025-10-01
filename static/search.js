let docs = {};
let currentType = "";

// Fetch docs when community ID entered
function showButtons() {
    const code = document.getElementById('communityCode').value.trim();
    if (!code) {
        alert("Please enter a community code.");
        return;
    }

    fetch(`/api/search?community_id=${code}`)
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                alert(data.error);
                return;
            }

            docs = data; // store globally

            // Show sections
            document.getElementById("resultButtons").style.display = "flex";
            document.getElementById("documentsSection").style.display = "block";
            document.getElementById("filterBar").style.display = "flex";

            // Show all documents initially
            renderDocs(getAllDocs(), "All Documents");

            // Update button labels dynamically with count
            const btnContainer = document.getElementById("resultButtons");
            btnContainer.innerHTML = "";

            for (const status in docs) {
                const btn = document.createElement("button");
                btn.innerText = `${status} (${docs[status].length})`;
                btn.onclick = () => showDocuments(status);
                btnContainer.appendChild(btn);
            }
        })
        .catch(err => console.error(err));
}

function showDocuments(type) {
    currentType = type;
    renderDocs(docs[type], `${type} Documents`);
}

function getAllDocs() {
    let combined = [];
    for (const status in docs) {
        combined = combined.concat(docs[status]);
    }
    return combined;
}

function renderDocs(list, title = "Documents") {
    document.getElementById("docTitle").innerText = title;
    const docList = document.getElementById("docList");
    docList.innerHTML = "";

    list.forEach(d => {
        const li = document.createElement("li");
        li.innerHTML = `<span class="doc-id">${d.id}</span> - <span>${d.name}</span>`;
        li.style.cursor = "pointer";
        li.onclick = () => openJsonModal(d.id);
        docList.appendChild(li);
    });
}

// Fetch JSON and show in modal
function openJsonModal(docId) {
    fetch(`/api/document/${docId}`)
        .then(res => res.json())
        .then(data => {
            const pre = document.getElementById("jsonContent");
            pre.innerText = JSON.stringify(data, null, 2); // pretty print
            document.getElementById("jsonModal").style.display = "flex";
        })
        .catch(err => console.error(err));
}

function filterDocs(mode) {
    if (mode === "all") {
        renderDocs(getAllDocs(), "All Documents");
    } else if (mode === "id") {
        const idVal = parseInt(document.getElementById("docIdInput").value, 10);
        if (isNaN(idVal)) {
            alert("Please enter a valid ID.");
            return;
        }

        const filtered = getAllDocs().filter(d => d.id === idVal);
        if (filtered.length === 0) alert("No document found with ID " + idVal);

        renderDocs(filtered, "Search Result");
    }
}

// Wait until DOM is ready
document.addEventListener("DOMContentLoaded", () => {
    const closeBtn = document.getElementById("closeModal");
    const modal = document.getElementById("jsonModal");

    // Close button
    closeBtn.addEventListener("click", () => {
        modal.style.display = "none";
    });

    // Close modal when clicking outside content
    modal.addEventListener("click", (e) => {
        if (e.target === modal) {
            modal.style.display = "none";
        }
    });
});


