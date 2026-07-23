"""
Dashboard local. Roda um servidor Flask em http://127.0.0.1:5000
com botões para disparar as Fases 1 e 2 e visualizar os resultados.
"""
import json
import os
import subprocess
import sys
import webbrowser
import threading

from flask import Flask, jsonify, render_template

import config

app = Flask(__name__)
PYTHON = sys.executable
BASE_DIR = os.path.dirname(__file__)

processo_live = {"proc": None}


def _ler_json(caminho, default):
    if not os.path.exists(caminho):
        return default
    with open(caminho, encoding="utf-8") as fp:
        return json.load(fp)


@app.route("/")
def home():
    return render_template("dashboard.html", ligas=config.LIGAS_MONITORADAS, margem_valor=config.LIMIAR_MARGEM_VALOR)


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


if __name__ == "__main__":
    porta = int(os.environ.get("PORT", 5000))
    if not os.environ.get("RENDER"):
        threading.Timer(1.2, _abrir_navegador).start()
    _iniciar_monitoramento_automatico()
    app.run(debug=False, host="0.0.0.0", port=porta)
