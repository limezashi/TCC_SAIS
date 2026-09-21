let patients = [];
const pageSize = 10;
let currentPage = 1;


async function loadPatients() {

    try {

        const response = await fetch(
            "../data/dataset_interface.csv"
        );

        if (!response.ok) {

            throw new Error(
                "Não foi possível carregar o dataset."
            );

        }

        const csv = await response.text();

        patients = parseCSV(csv);

        renderDashboard();

        renderPatients(patients);

    } catch (error) {

        console.error(
            "Erro ao carregar o dataset:",
            error
        );

    }

}


function parseCSV(csv) {

    const lines = csv
        .trim()
        .split(/\r?\n/);

    const headers = lines[0]
        .split(",")
        .map(header => header.trim());


    return lines
        .slice(1)
        .filter(line => line.trim() !== "")
        .map(line => {

            const values = line.split(",");

            const patient = {};

            headers.forEach((header, index) => {

                patient[header] =
                    values[index]?.trim() ?? "";

            });

            return patient;

        });

}


function renderDashboard() {

    document.getElementById(
        "totalPatients"
    ).textContent = patients.length;


    /*
        Por enquanto cada registro do dataset
        representa uma avaliação.
    */

    document.getElementById(
        "totalEvaluations"
    ).textContent = patients.length;


    /*
        A probabilidade ainda não está no CSV.

        Ela será adicionada posteriormente
        através do modelo.
    */

    document.getElementById(
        "averageProbability"
    ).textContent = "—";


    /*
        Encontrar a avaliação mais recente
        através da data existente no dataset.
    */

    if (patients.length > 0) {

        const dates = patients
            .map(patient => patient.data_avaliacao)
            .filter(date => date);


        const latestDate = dates
            .sort()
            .reverse()[0];


        document.getElementById(
            "lastEvaluation"
        ).textContent =
            formatDate(latestDate);

    }


    document.getElementById(
        "currentDate"
    ).textContent =
        formatCurrentDate();

}


function renderPatients(data) {

    const tableBody =
        document.getElementById(
            "patientsTableBody"
        );


    tableBody.innerHTML = "";

    const totalPages = Math.max(
        1,
        Math.ceil(data.length / pageSize)
    );

    if (currentPage > totalPages) {
        currentPage = totalPages;
    }

    const start = (currentPage - 1) * pageSize;
    const end = start + pageSize;
    const paginatedPatients = data.slice(start, end);

    paginatedPatients.forEach(patient => {

        const row =
            document.createElement("tr");


        row.innerHTML = `

            <td>

                <strong>
                    ${patient.patient_id}
                </strong>

            </td>


            <td>
                ${formatDate(
                    patient.data_avaliacao
                )}
            </td>


            <td>

                <span class="probability-empty">
                    —
                </span>

            </td>


            <td>

                <a
                    href="paciente.html?id=${patient.patient_id}"
                    class="btn-view"
                >
                    Ver avaliação
                </a>

            </td>

        `;


        tableBody.appendChild(row);

    });

    renderPagination(data.length);

}


function renderPagination(totalItems) {

    const totalPages = Math.max(
        1,
        Math.ceil(totalItems / pageSize)
    );

    const pagination = document.getElementById("pagination");

    if (!pagination) {
        return;
    }

    pagination.innerHTML = `
        <div class="pagination-controls">
            <button type="button" ${currentPage === 1 ? "disabled" : ""} data-page="prev">
                «
            </button>
            <button type="button" ${currentPage === 1 ? "disabled" : ""} data-page="1">1</button>
            <button type="button" ${currentPage === 2 ? "disabled" : ""} data-page="2">2</button>
            <button type="button" ${currentPage === 3 ? "disabled" : ""} data-page="3">3</button>
            <span>...</span>
            <button type="button" data-page="${totalPages}">${totalPages}</button>
            <button type="button" ${currentPage === totalPages ? "disabled" : ""} data-page="next">
                »
            </button>
        </div>
    `;

    const controls = pagination.querySelectorAll("[data-page]");

    controls.forEach(button => {
        const pageValue = button.getAttribute("data-page");

        if (pageValue === "prev") {
            button.addEventListener("click", () => {
                if (currentPage > 1) {
                    currentPage -= 1;
                    renderPatients(patients);
                }
            });
            return;
        }

        if (pageValue === "next") {
            button.addEventListener("click", () => {
                if (currentPage < totalPages) {
                    currentPage += 1;
                    renderPatients(patients);
                }
            });
            return;
        }

        const targetPage = Number(pageValue);

        if (!Number.isNaN(targetPage)) {
            button.addEventListener("click", () => {
                currentPage = targetPage;
                renderPatients(patients);
            });
        }
    });

    pagination.querySelector("[data-page='prev']")
        ?.addEventListener("click", () => {
            if (currentPage > 1) {
                currentPage -= 1;
                renderPatients(patients);
            }
        });

    pagination.querySelector("[data-page='next']")
        ?.addEventListener("click", () => {
            if (currentPage < totalPages) {
                currentPage += 1;
                renderPatients(patients);
            }
        });

}


function formatDate(dateString) {

    if (!dateString) {

        return "—";

    }


    const [year, month, day] =
        dateString.split("-");


    return `${day}/${month}/${year}`;

}


function formatCurrentDate() {

    const today = new Date();


    return today.toLocaleDateString(
        "pt-BR"
    );

}


/*
    Pesquisa por paciente.
*/

document
    .getElementById("searchPatient")
    .addEventListener(
        "input",
        function () {

            currentPage = 1;

            const search =
                this.value
                    .toLowerCase()
                    .trim();


            const filtered =
                patients.filter(patient =>
                    patient.patient_id
                        .toLowerCase()
                        .includes(search)
                );


            renderPatients(filtered);

        }
    );


loadPatients();


loadPatients();