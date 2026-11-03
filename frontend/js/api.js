window.SAIS = (() => {
    const features = ["leucocitos", "neutrofilos", "plaquetas", "temperatura", "fc", "pas", "lactato", "creatinina", "pao2_fio2", "rnl", "bastonetes"];
    async function request(path, options = {}) {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 15000);
        try {
            const response = await fetch(path, {...options, signal: controller.signal});
            if (!response.ok) {
                const messages = {422: "Os parâmetros enviados são inválidos.", 503: "Serviço indisponível. Tente novamente.", 500: "Não foi possível calcular a probabilidade."};
                throw new Error(messages[response.status] || "Não foi possível concluir a solicitação.");
            }
            return await response.json();
        } catch (error) {
            if (error instanceof SyntaxError) throw new Error("A API retornou uma resposta inválida. Tente novamente.");
            if (error.name === "AbortError") throw new Error("O serviço demorou a responder. Tente novamente.");
            if (error instanceof TypeError) throw new Error("Falha de conexão com a API. Tente novamente.");
            throw error;
        } finally { clearTimeout(timer); }
    }
    function inputs(patient) {
        const data = {};
        for (const name of features) {
            if (typeof patient[name] !== "number" || !Number.isFinite(patient[name])) throw new Error("Parâmetros do paciente inválidos.");
            data[name] = patient[name];
        }
        return data;
    }
    async function patients() {
        const rows = await request("/demo/patients");
        if (!Array.isArray(rows) || rows.length !== 30) throw new Error("Lista de pacientes inválida.");
        const ids = new Set();
        for (const row of rows) {
            if (typeof row.patient_id !== "string" || !row.patient_id.startsWith("DEMO") || ids.has(row.patient_id) || typeof row.data_avaliacao !== "string") throw new Error("Dados demonstrativos inválidos.");
            inputs(row); ids.add(row.patient_id);
        }
        return rows;
    }
    async function predict(patient) {
        const result = await request("/predict", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(inputs(patient))});
        if (typeof result.probabilidade !== "number" || !Number.isFinite(result.probabilidade) || result.probabilidade < 0 || result.probabilidade > 1 || typeof result.versao_modelo !== "string") throw new Error("A API retornou um resultado inválido.");
        return result;
    }
    function savedPredictions() {
        const stored = localStorage.getItem("sais-predictions");
        if (!stored) return {};
        try {
            const parsed = JSON.parse(stored);
            return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
        } catch (error) {
            if (error instanceof SyntaxError) return {};
            throw error;
        }
    }
    function getSavedPrediction(patientId) {
        const result = savedPredictions()[patientId];
        if (!result || typeof result.probabilidade !== "number" ||
            !Number.isFinite(result.probabilidade) || result.probabilidade < 0 ||
            result.probabilidade > 1 || typeof result.versao_modelo !== "string" ||
            typeof result.calculado_em !== "string" || !Number.isFinite(Date.parse(result.calculado_em))) return null;
        return result;
    }
    function savePrediction(patientId, result) {
        if (typeof patientId !== "string" || !patientId.startsWith("DEMO") ||
            typeof result.probabilidade !== "number" || !Number.isFinite(result.probabilidade) ||
            result.probabilidade < 0 || result.probabilidade > 1 ||
            typeof result.versao_modelo !== "string") {
            throw new Error("Não foi possível guardar o resultado deste paciente.");
        }
        const predictions = savedPredictions();
        predictions[patientId] = {
            probabilidade: result.probabilidade,
            versao_modelo: result.versao_modelo,
            calculado_em: new Date().toISOString()
        };
        localStorage.setItem("sais-predictions", JSON.stringify(predictions));
    }
    async function healthStatus(element) {
        element.textContent = "";
        try {
            const health = await request("/health");
            if (health.status !== "ok") throw new Error("Modelo indisponível.");
        } catch (error) { element.textContent = error.message; }
    }
    function formatDate(value) {
        const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
        return match ? `${match[3]}/${match[2]}/${match[1]}` : "—";
    }
    return {features, patients, predict, getSavedPrediction, savePrediction, healthStatus, formatDate};
})();
