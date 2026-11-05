window.SAIS = (() => {
    const features = ["leucocitos", "neutrofilos", "plaquetas", "temperatura", "fc", "pas", "lactato", "creatinina", "pao2_fio2", "rnl", "bastonetes"];
    async function request(path, options = {}) {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 15000);
        try {
            const response = await fetch(path, {...options, signal: controller.signal});
            if (!response.ok) {
                const messages = {404: "Registro nao encontrado.", 422: "Parametros invalidos.", 503: "Servico ou banco indisponivel.", 500: "Falha ao calcular a probabilidade."};
                const error = new Error(messages[response.status] || "Falha na solicitacao.");
                error.status = response.status;
                throw error;
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
    async function patients(filters = {}) {
        const params = new URLSearchParams();
        for (const name of ["page", "page_size", "search", "data_avaliacao"]) {
            const value = filters[name];
            if (value !== undefined && value !== null && value !== "") params.set(name, String(value));
        }
        const query = params.toString();
        const result = await request(`/demo/patients${query ? `?${query}` : ""}`);
        if (!result || !Array.isArray(result.items) || !Number.isInteger(result.total) ||
            !Number.isInteger(result.page) || !Number.isInteger(result.page_size) ||
            !Number.isInteger(result.total_pages)) throw new Error("A API retornou uma pagina invalida.");
        const ids = new Set();
        for (const patient of result.items) {
            if (typeof patient.patient_id !== "string" || ids.has(patient.patient_id) ||
                typeof patient.data_avaliacao !== "string") throw new Error("Dados de paciente invalidos.");
            inputs(patient); ids.add(patient.patient_id);
            const last = patient.ultima_avaliacao;
            if (last !== null && (!last || typeof last.id !== "number" ||
                typeof last.probabilidade !== "number" || !Number.isFinite(last.probabilidade) ||
                last.probabilidade < 0 || last.probabilidade > 1 ||
                typeof last.modelo_hash !== "string" || typeof last.calculado_em !== "string")) {
                throw new Error("Ultima avaliacao invalida.");
            }
        }
        return result;
    }
    async function predict(patient) {
        const result = await request(`/patients/${encodeURIComponent(patient.patient_id)}/evaluations`, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(inputs(patient))});
        if (typeof result.id !== "number" || typeof result.patient_id !== "string" || typeof result.probabilidade !== "number" || !Number.isFinite(result.probabilidade) || result.probabilidade < 0 || result.probabilidade > 1 || typeof result.versao_modelo !== "string" || typeof result.calculado_em !== "string") throw new Error("A API retornou um resultado invalido.");
        return result;
    }
    async function latestEvaluation(patientId) {
        try { return await request(`/patients/${encodeURIComponent(patientId)}/evaluations/latest`); }
        catch (error) { if (error.status === 404) return null; throw error; }
    }
    async function latestEvaluations() {
        const rows = await request("/evaluations/latest");
        if (!Array.isArray(rows)) throw new Error("A API retornou um historico invalido.");
        const ids = new Set();
        for (const row of rows) {
            if (typeof row.patient_id !== "string" || ids.has(row.patient_id) ||
                typeof row.id !== "number" || typeof row.probabilidade !== "number" ||
                !Number.isFinite(row.probabilidade) || row.probabilidade < 0 ||
                row.probabilidade > 1 || typeof row.modelo_hash !== "string" ||
                typeof row.calculado_em !== "string") throw new Error("A API retornou um historico invalido.");
            ids.add(row.patient_id);
        }
        return rows;
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
    return {features, patients, predict, latestEvaluation, latestEvaluations, healthStatus, formatDate};
})();
