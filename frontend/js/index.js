let patients = [];
let currentPage = 1;
let appliedSearch = "";
let appliedDate = "";
const pageSize = 10;
const tableBody = document.getElementById("patientsTableBody");
const searchInput = document.getElementById("searchPatient");
const dateFilter = document.getElementById("filterDate");
const filterForm = document.getElementById("patientFilters");
const pagination = document.getElementById("pagination");
const statusMessage = document.getElementById("loadStatus");
const retryButton = document.getElementById("retryLoad");

function filteredPatients() {
    return patients.filter(patient =>
        patient.patient_id.toLowerCase().includes(appliedSearch) &&
        (!appliedDate || patient.data_avaliacao === appliedDate)
    );
}
function renderPatients() {
    const filtered = filteredPatients();
    const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
    currentPage = Math.min(currentPage, totalPages);
    tableBody.replaceChildren();
    for (const patient of filtered.slice((currentPage - 1) * pageSize, currentPage * pageSize)) {
        const row = document.createElement("tr");
        const codeCell = row.insertCell();
        const code = document.createElement("strong");
        code.textContent = patient.patient_id;
        codeCell.append(code);
        row.insertCell().textContent = SAIS.formatDate(patient.data_avaliacao);
        const probability = row.insertCell();
        const savedPrediction = SAIS.getSavedPrediction(patient.patient_id);
        if (savedPrediction) {
            probability.textContent = savedPrediction.probabilidade.toLocaleString("pt-BR", {
                style: "percent", minimumFractionDigits: 2, maximumFractionDigits: 2
            });
            probability.className = "probability-calculated";
        } else {
            probability.textContent = "Não calculada";
            probability.className = "probability-empty";
        }
        const link = document.createElement("a");
        link.href = "avaliacao.html?id=" + encodeURIComponent(patient.patient_id);
        link.className = "btn-view";
        link.textContent = savedPrediction ? "Ver resultado" : "Realizar avaliação";
        link.setAttribute("aria-label", `${link.textContent} de ${patient.patient_id}`);
        row.insertCell().append(link);
        tableBody.append(row);
    }
    if (!filtered.length) {
        const cell = tableBody.insertRow().insertCell();
        cell.colSpan = 4;
        cell.textContent = "Nenhum paciente encontrado.";
    }
    pagination.replaceChildren();
    if (!filtered.length) return;
    function button(label, target, disabled, active = false) {
        const element = document.createElement("button");
        element.type = "button"; element.textContent = label; element.disabled = disabled;
        if (active) { element.className = "active"; element.setAttribute("aria-current", "page"); }
        element.addEventListener("click", () => { currentPage = target; renderPatients(); });
        pagination.append(element);
    }
    button("«", currentPage - 1, currentPage === 1);
    for (let page = 1; page <= totalPages; page++) button(String(page), page, page === currentPage, page === currentPage);
    button("»", currentPage + 1, currentPage === totalPages);
}
async function loadPatients() {
    retryButton.hidden = true; statusMessage.textContent = "Carregando pacientes sintéticos…";
    searchInput.disabled = true; dateFilter.disabled = true;
    filterForm.querySelector("button").disabled = true;
    tableBody.replaceChildren(); pagination.replaceChildren();
    try {
        patients = await SAIS.patients(); currentPage = 1; renderPatients();
        statusMessage.textContent = "";
    } catch (error) {
        patients = []; statusMessage.textContent = error.message; retryButton.hidden = false;
    } finally {
        searchInput.disabled = false; dateFilter.disabled = false;
        filterForm.querySelector("button").disabled = false;
    }
    SAIS.healthStatus(document.getElementById("apiStatus"));
}
filterForm.addEventListener("submit", event => {
    event.preventDefault();
    appliedSearch = searchInput.value.trim().toLowerCase();
    appliedDate = dateFilter.value;
    currentPage = 1;
    renderPatients();
});
retryButton.addEventListener("click", loadPatients);
loadPatients();
