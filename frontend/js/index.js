let currentPage = 1;
const pageSize = 10;
let appliedSearch = "";
let appliedDate = "";
const tableBody = document.getElementById("patientsTableBody");
const searchInput = document.getElementById("searchPatient");
const dateFilter = document.getElementById("filterDate");
const filterForm = document.getElementById("patientFilters");
const clearFiltersButton = document.getElementById("clearFilters");
const pagination = document.getElementById("pagination");
const statusMessage = document.getElementById("loadStatus");
const retryButton = document.getElementById("retryLoad");

function renderPatients(result) {
    tableBody.replaceChildren();
    for (const patient of result.items) {
        const row = document.createElement("tr");
        const codeCell = row.insertCell();
        const code = document.createElement("strong");
        code.textContent = patient.patient_id;
        codeCell.append(code);
        row.insertCell().textContent = SAIS.formatDate(patient.data_avaliacao);
        const probability = row.insertCell();
        const latest = patient.ultima_avaliacao;
        if (latest) {
            probability.textContent = latest.probabilidade.toLocaleString("pt-BR", {
                style: "percent", minimumFractionDigits: 2, maximumFractionDigits: 2
            });
            probability.className = "probability-calculated";
        } else {
            probability.textContent = "Nao calculada";
            probability.className = "probability-empty";
        }
        const link = document.createElement("a");
        link.href = "avaliacao.html?id=" + encodeURIComponent(patient.patient_id);
        link.className = "btn-view";
        link.textContent = latest ? "Ver resultado" : "Realizar avaliacao";
        link.setAttribute("aria-label", `${link.textContent} de ${patient.patient_id}`);
        row.insertCell().append(link);
        tableBody.append(row);
    }
    if (!result.items.length) {
        const cell = tableBody.insertRow().insertCell();
        cell.colSpan = 4;
        cell.textContent = "Nenhum paciente encontrado.";
    }
    renderPagination(result.total_pages);
}
function renderPagination(totalPages) {
    pagination.replaceChildren();
    if (totalPages < 1) return;
    function button(label, target, disabled, active = false) {
        const element = document.createElement("button");
        element.type = "button";
        element.textContent = label;
        element.disabled = disabled;
        if (active) { element.className = "active"; element.setAttribute("aria-current", "page"); }
        element.addEventListener("click", () => loadPatients(target));
        pagination.append(element);
    }
    button("<", currentPage - 1, currentPage === 1);
    const pages = [...new Set([1, currentPage - 1, currentPage, currentPage + 1, totalPages])]
        .filter(page => page >= 1 && page <= totalPages).sort((a, b) => a - b);
    let previous = 0;
    for (const page of pages) {
        if (page - previous > 1) {
            const ellipsis = document.createElement("span");
            ellipsis.textContent = "...";
            pagination.append(ellipsis);
        }
        button(String(page), page, page === currentPage, page === currentPage);
        previous = page;
    }
    button(">", currentPage + 1, currentPage === totalPages);
}
async function loadPatients(page = currentPage) {
    retryButton.hidden = true;
    statusMessage.textContent = "Carregando pacientes...";
    searchInput.disabled = true;
    dateFilter.disabled = true;
    filterForm.querySelectorAll("button").forEach(button => { button.disabled = true; });
    tableBody.replaceChildren();
    pagination.replaceChildren();
    try {
        let result = await SAIS.patients({
            page,
            page_size: pageSize,
            search: appliedSearch,
            data_avaliacao: appliedDate
        });
        if (result.total_pages > 0 && result.page > result.total_pages) {
            result = await SAIS.patients({
                page: result.total_pages,
                page_size: pageSize,
                search: appliedSearch,
                data_avaliacao: appliedDate
            });
        }
        currentPage = result.page;
        renderPatients(result);
        statusMessage.textContent = `${result.total} paciente(s) encontrados.`;
    } catch (error) {
        statusMessage.textContent = error.message;
        retryButton.hidden = false;
    } finally {
        searchInput.disabled = false;
        dateFilter.disabled = false;
        filterForm.querySelectorAll("button").forEach(button => { button.disabled = false; });
    }
    SAIS.healthStatus(document.getElementById("apiStatus"));
}
filterForm.addEventListener("submit", event => {
    event.preventDefault();
    appliedSearch = searchInput.value.trim();
    appliedDate = dateFilter.value;
    currentPage = 1;
    loadPatients(1);
});
clearFiltersButton.addEventListener("click", () => {
    searchInput.value = "";
    dateFilter.value = "";
    appliedSearch = "";
    appliedDate = "";
    currentPage = 1;
    loadPatients(1);
});
retryButton.addEventListener("click", () => loadPatients(currentPage));
loadPatients(1);
