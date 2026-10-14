"""Treina e persiste exclusivamente a RL selecionada; nao avalia o teste."""
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4
from zoneinfo import ZoneInfo

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import numpy as np
    import pandas as pd
    from src.modelo_rl import criar_modelo_rl
    from src.preparacao_dados import preparar_dados
    from src.modelo_persistido import salvar_modelo, carregar_modelo, prever_probabilidade, sha256
    protected = [p for directory in ["data", "notebooks", "results"] for p in (ROOT / directory).rglob("*") if p.is_file()]
    protected += list((ROOT / "src").glob("*.py"))
    before = {str(p): sha256(p) for p in protected}
    dataset = ROOT / "data/dataset.csv"
    X, xt, y, yt = preparar_dados(str(dataset))
    test_indices = xt.index.copy()
    del xt, yt
    assert len(X) == 4684 and int(y.sum()) == 505
    assert not np.intersect1d(X.index, test_indices).size
    ids = pd.read_csv(dataset, usecols=["patient_id"]).loc[X.index, "patient_id"]
    modelo = criar_modelo_rl()
    modelo.fit(X, y)
    stamp = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%Y%m%dT%H%M%S%f")
    folder = ROOT / "artifacts" / f"rl_{stamp}_{uuid4().hex[:8]}"
    commit = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    salvar_modelo(modelo, folder, dataset, ids, int(y.sum()), commit)
    carregado = carregar_modelo(folder, origem_confiavel=True)
    a, b = modelo.predict_proba(X), carregado.predict_proba(X)
    np.testing.assert_array_equal(a, b)
    exemplo = X.iloc[0].to_dict()
    result = {"training_count": len(X), "positive_training": int(y.sum()),
              "prediction_before_after_exactly_equal_all_training": True,
              "max_absolute_difference": float(np.abs(a-b).max()),
              "example": {"origin": "registro sintetico do treinamento", "patient_id": int(ids.iloc[0]),
                          "inputs": exemplo, "probability_before": prever_probabilidade(modelo, exemplo),
                          "probability_after": prever_probabilidade(carregado, exemplo)},
              "test_evaluated": False, "protected_files_unchanged": all(sha256(Path(p)) == h for p,h in before.items())}
    if not result["protected_files_unchanged"]:
        raise RuntimeError("Arquivo protegido alterado.")
    with (folder / "verificacao.json").open("x", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps({"artifact_directory": str(folder), **result}, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
