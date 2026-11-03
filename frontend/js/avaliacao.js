let selectedPatient = null;
const statusElement = document.getElementById("evaluationStatus");
const calculate = document.getElementById("calculate");
const retry = document.getElementById("retryPatient");
const details = document.getElementById("patientDetails");
const resultSection = document.getElementById("predictionResult");
const labels = {
    pas: ["Pressão arterial sistólica", "mmHg"], fc: ["Frequência cardíaca", "bpm"],
    temperatura: ["Temperatura", "°C"], leucocitos: ["Leucócitos", "×10⁹/L"],
    neutrofilos: ["Neutrófilos absolutos", "×10⁹/L"], rnl: ["Razão neutrófilos/linfócitos", "adimensional"],
    bastonetes: ["Bastonetes", "%"], pao2_fio2: ["Relação PaO₂/FiO₂", "mmHg"],
    creatinina: ["Creatinina", "mg/dL"], lactato: ["Lactato", "mmol/L"], plaquetas: ["Plaquetas", "×10⁹/L"]
};
function showPrediction(result, calculatedAt) {
    document.getElementById("probability").textContent = result.probabilidade.toLocaleString("pt-BR", {
        style: "percent", minimumFractionDigits: 2, maximumFractionDigits: 2
    });
    document.getElementById("modelVersion").textContent = result.versao_modelo;
    document.getElementById("calculatedAt").textContent = `Calculado em: ${new Date(calculatedAt).toLocaleString("pt-BR", {timeZone: "America/Sao_Paulo"})}`;
    resultSection.hidden = false;
}
async function loadPatient() {
    selectedPatient = null; details.hidden = true; resultSection.hidden = true; retry.hidden = true; calculate.disabled = true;
    const id = new URLSearchParams(window.location.search).get("id");
    if (!id) { statusElement.textContent = "Selecione um paciente na listagem."; document.getElementById("patientIdentity").textContent = "Paciente não selecionado."; return; }
    statusElement.textContent = "Carregando parâmetros do paciente…";
    try {
        const patients = await SAIS.patients();
        selectedPatient = patients.find(patient => patient.patient_id === id);
        if (!selectedPatient) { statusElement.textContent = "Paciente sintético não encontrado. Retorne à listagem."; document.getElementById("patientIdentity").textContent = "Identificador desconhecido."; return; }
        document.getElementById("patientIdentity").textContent = `${id} · Data do registro: ${SAIS.formatDate(selectedPatient.data_avaliacao)}`;
        const parameters = document.getElementById("parameters"); parameters.replaceChildren();
        for (const name of Object.keys(labels)) {
            const box = document.createElement("div"); const title = document.createElement("dt"); const value = document.createElement("dd");
            title.textContent = labels[name][0];
            value.textContent = `${selectedPatient[name].toLocaleString("pt-BR", {maximumFractionDigits: 2})} ${labels[name][1]}`;
            box.append(title, value); parameters.append(box);
        }
        details.hidden = false; calculate.disabled = false;
        const savedPrediction = SAIS.getSavedPrediction(id);
        if (savedPrediction) {
            showPrediction(savedPrediction, savedPrediction.calculado_em);
            calculate.textContent = "Calcular novamente";
            statusElement.textContent = "Resultado anterior carregado.";
        } else {
            statusElement.textContent = "Registro carregado. O cálculo utiliza a API e a Regressão Logística persistida.";
        }
    } catch (error) { statusElement.textContent = error.message; retry.hidden = false; }
    SAIS.healthStatus(document.getElementById("apiStatus"));
}
calculate.addEventListener("click", async () => {
    if (!selectedPatient) return;
    calculate.disabled = true; resultSection.hidden = true; statusElement.textContent = "Calculando probabilidade…";
    try {
        const result = await SAIS.predict(selectedPatient);
        const calculatedAt = new Date().toISOString();
        showPrediction(result, calculatedAt);
        statusElement.textContent = "Cálculo experimental concluído.";
        calculate.textContent = "Calcular novamente";
        try {
            SAIS.savePrediction(selectedPatient.patient_id, {...result, calculado_em: calculatedAt});
        } catch (error) {
            statusElement.textContent = "Cálculo concluído, mas não foi possível guardar o resultado neste navegador.";
        }
    } catch (error) { statusElement.textContent = error.message; calculate.textContent = "Tentar novamente"; }
    finally { calculate.disabled = false; }
});
retry.addEventListener("click", loadPatient);
loadPatient();
