"""
Dashboard local. Roda um servidor Flask em http://127.0.0.1:5000
com botões para disparar as Fases 1 e 2 e visualizar os resultados.
"""
import json
import os
import subprocess
import sys
import time
import webbrowser
import threading
from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify, render_template, request

import config

HORA_PRELIVE_UTC = 6  # 06:00 UTC ~ manhã na Suécia/Lituânia (UTC+2 no verão)

app = Flask(__name__)
PYTHON = sys.executable
BASE_DIR = os.path.dirname(__file__)

processo_live = {"proc": None}


def _ler_json(caminho, default):
    if not os.path.exists(caminho):
        return default
    with open(caminho, encoding="utf-8") as fp:
        return json.load(fp)


def _salvar_json(caminho, obj):
    os.makedirs(config.DATA_DIR, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as fp:
        json.dump(obj, fp, ensure_ascii=False, indent=2)


@app.route("/")
def home():
    return render_template(
        "dashboard.html",
        ligas=config.LIGAS_MONITORADAS,
        margem_valor=config.LIMIAR_MARGEM_VALOR,
        vapid_public_key=config.VAPID_PUBLIC_KEY,
    )


@app.route("/api/push-subscribe", methods=["POST"])
def api_push_subscribe():
    sub = request.get_json(force=True)
    subs = _ler_json(config.PUSH_SUBS_FILE, [])
    if not any(s.get("endpoint") == sub.get("endpoint") for s in subs):
        subs.append(sub)
        _salvar_json(config.PUSH_SUBS_FILE, subs)
    return jsonify({"ok": True})


@app.route("/api/prelive")
def api_prelive():
    return jsonify(_ler_json(config.PRELIVE_FILE, {"gerado_em": None, "relatorios": []}))


@app.route("/api/insights")
def api_insights():
    return jsonify(_ler_json(config.LIVE_INSIGHTS_FILE, []))


@app.route("/api/live-snapshots")
def api_live_snapshots():
    return jsonify(_ler_json(config.LIVE_SNAPSHOTS_FILE, {}))


@app.route("/api/status")
def api_status():
    status = _ler_json(config.STATUS_FILE, {"ultima_checagem": None, "jogos_ao_vivo_monitorados": 0})
    status["monitor_ativo"] = processo_live["proc"] is not None and processo_live["proc"].poll() is None
    return jsonify(status)


@app.route("/api/rodar-prelive", methods=["POST"])
def api_rodar_prelive():
    subprocess.Popen([PYTHON, os.path.join(BASE_DIR, "prelive_analysis.py")])
    return jsonify({"ok": True, "mensagem": "Análise pré-live iniciada em segundo plano."})


@app.route("/api/iniciar-live", methods=["POST"])
def api_iniciar_live():
    if processo_live["proc"] is not None and processo_live["proc"].poll() is None:
        return jsonify({"ok": False, "mensagem": "Monitoramento já está rodando."})
    processo_live["proc"] = subprocess.Popen([PYTHON, os.path.join(BASE_DIR, "live_monitor.py")])
    return jsonify({"ok": True, "mensagem": "Monitoramento ao vivo iniciado."})


@app.route("/api/parar-live", methods=["POST"])
def api_parar_live():
    if processo_live["proc"] is not None and processo_live["proc"].poll() is None:
        processo_live["proc"].terminate()
        return jsonify({"ok": True, "mensagem": "Monitoramento parado."})
    return jsonify({"ok": False, "mensagem": "Nenhum monitoramento ativo."})


def _abrir_navegador():
    webbrowser.open("http://127.0.0.1:5000")


def _iniciar_monitoramento_automatico():
    if processo_live["proc"] is None or processo_live["proc"].poll() is not None:
        processo_live["proc"] = subprocess.Popen([PYTHON, os.path.join(BASE_DIR, "live_monitor.py")])
        print("[auto] Monitoramento ao vivo iniciado automaticamente na subida do servidor.")


def _ciclo_prelive_diario():
    subprocess.run([PYTHON, os.path.join(BASE_DIR, "prelive_analysis.py")])
    print("[auto] Análise pré-live inicial concluída.")
    while True:
        agora = datetime.now(timezone.utc)
        proximo = agora.replace(hour=HORA_PRELIVE_UTC, minute=0, second=0, microsecond=0)
        if proximo <= agora:
            proximo += timedelta(days=1)
        time.sleep((proximo - agora).total_seconds())
        try:
            subprocess.run([PYTHON, os.path.join(BASE_DIR, "prelive_analysis.py")])
            print(f"[auto] Análise pré-live diária concluída às {datetime.now(timezone.utc).isoformat()}.")
        except Exception as e:
            print(f"[auto] Erro na análise pré-live diária: {e}")


def _agendar_prelive_diario():
    threading.Thread(target=_ciclo_prelive_diario, daemon=True).start()


if __name__ == "__main__":
    porta = int(os.environ.get("PORT", 5000))
    if not os.environ.get("RENDER"):
        threading.Timer(1.2, _abrir_navegador).start()
    _iniciar_monitoramento_automatico()
    _agendar_prelive_diario()
    app.run(debug=False, host="0.0.0.0", port=porta)
