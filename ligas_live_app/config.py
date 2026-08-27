"""
Configuração central do sistema.
Edite este arquivo para ajustar token, ligas e limiares de alerta.
"""
import os

# ── Autenticação ──────────────────────────────────────────────
# Em deploy na nuvem, defina a variável de ambiente SPORTMONKS_TOKEN em vez de
# editar este arquivo (evita deixar o token exposto no repositório Git).
SPORTMONKS_TOKEN = os.environ.get("SPORTMONKS_TOKEN", "COLE_SEU_TOKEN_AQUI")
BASE_URL = "https://api.sportmonks.com/v3/football"

# ── Ligas monitoradas (id: nome) ─────────────────────────────
LIGAS_MONITORADAS = {
    579: "Superettan",
    573: "Allsvenskan",
    447: "1. Division",
    648: "Série A",
    651: "Série B",
}

# ── Janela de análise pré-live ────────────────────────────────
DIAS_A_FRENTE = 5          # quantos dias buscar fixtures à frente
JOGOS_HISTORICO_PERFIL = 8  # quantos jogos recentes usar p/ montar o perfil de cada time

# ── Parâmetros do modelo de placar modal (Poisson) ────────────
MAX_GOLS_GRADE = 6  # grade de 0 a 6 gols por time para achar o placar mais provável

# ── Limiares de alerta no monitoramento ao vivo ───────────────
# Único sinal do painel: ritmo de gols (real x esperado). Só dispara quando
# os DOIS critérios batem: desvio percentual grande E diferença mínima em
# número absoluto de gols. Só o percentual sozinho dispara sinal bobo quando
# o esperado até aquele minuto é um número pequeno (ex: esperado 0.3 gol,
# saiu 1 gol = "233% acima" por uma diferença de 1 gol só).
MINUTO_MINIMO_ALERTA = 15         # só gera insight a partir desse minuto
LIMIAR_DELTA_GOLS = 0.50          # 50% de desvio percentual
LIMIAR_ABS_GOLS = 1.0             # E pelo menos 1 gol de diferença
LIMIAR_MARGEM_VALOR = 0.05        # margem mínima de vantagem exigida no cálculo de odd mínima (5%)
LINHA_ESCANTEIROS = 9.5           # linha usada no mercado de Over/Under total de escanteios
INTERVALO_POLLING_SEGUNDOS = 60   # frequência de checagem durante o jogo
RETENCAO_JOGOS_ANTERIORES_DIAS = 7  # quantos dias manter um jogo encerrado arquivado

# ── Indicador de mercado no card (pré-live x ao vivo) ──────────
# Compara a probabilidade calculada ANTES do jogo com a probabilidade AO VIVO
# de cada mercado (vitória/empate/over-under/BTTS/escanteios), em pontos
# percentuais. Abaixo de LIMIAR_PP_MERCADO = "equilibrado". Acima disso =
# "acima"/"abaixo" do esperado. Acima de LIMIAR_PP_MERCADO_FORTE = mesmo
# padrão de destaque usado nos Sinais ao vivo.
LIMIAR_PP_MERCADO = 8
LIMIAR_PP_MERCADO_FORTE = 15

# ── Notificações push (Web Push / VAPID) ───────────────────────
# Chave pública: vai para o navegador, não é sigilosa.
VAPID_PUBLIC_KEY = "BNZ16axPU6HdeIDLV10BTfc5c5XYEkibrWP6nH3pfMDsriGlEVOHjHALTfDgh-Tfbyx84yyxK3FwLX2rx_Hj4Fk"
# Chave privada: define via variável de ambiente VAPID_PRIVATE_KEY em deploy na nuvem.
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_CLAIMS_EMAIL = "mailto:lucaseirafleury@gmail.com"

# ── Arquivos de dados (não editar) ────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
PRELIVE_FILE = os.path.join(DATA_DIR, "prelive_reports.json")
LIVE_INSIGHTS_FILE = os.path.join(DATA_DIR, "live_insights.json")
LIVE_SNAPSHOTS_FILE = os.path.join(DATA_DIR, "live_snapshots.json")
JOGOS_ANTERIORES_FILE = os.path.join(DATA_DIR, "jogos_anteriores.json")
STATUS_FILE = os.path.join(DATA_DIR, "status.json")
PUSH_SUBS_FILE = os.path.join(DATA_DIR, "push_subscriptions.json")
SINAIS_PENDENTES_FILE = os.path.join(DATA_DIR, "sinais_pendentes.json")
