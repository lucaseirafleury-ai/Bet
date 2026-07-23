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
    405: "A Lyga",
    408: "1. Lyga",
    447: "1. Division",
}

# ── Janela de análise pré-live ────────────────────────────────
DIAS_A_FRENTE = 5          # quantos dias buscar fixtures à frente
JOGOS_HISTORICO_PERFIL = 8  # quantos jogos recentes usar p/ montar o perfil de cada time

# ── Parâmetros do modelo de placar modal (Poisson) ────────────
MAX_GOLS_GRADE = 6  # grade de 0 a 6 gols por time para achar o placar mais provável

# ── Limiares de alerta no monitoramento ao vivo ───────────────
MINUTO_MINIMO_ALERTA = 15       # só gera insight a partir desse minuto
LIMIAR_DELTA_PRESSAO = 0.30     # 30% de desvio do esperado já dispara insight
LIMIAR_DELTA_XG = 0.25          # 25% de desvio do esperado já dispara insight
LIMIAR_DELTA_GOLS = 0.35        # ritmo de gols vs esperado
LIMIAR_DELTA_ESCANTEIROS = 0.30
LIMIAR_DELTA_CARTOES = 0.35
LIMIAR_DIVERGENCIA_XG_GOLS = 0.8  # xG_proxy acumulado menos gols reais, em "gols"
LIMIAR_MARGEM_VALOR = 0.05        # margem mínima de vantagem exigida no cálculo de odd mínima (5%)
LINHA_ESCANTEIROS = 9.5           # linha usada no mercado de Over/Under total de escanteios
INTERVALO_POLLING_SEGUNDOS = 60  # frequência de checagem durante o jogo

# ── Momentum (tendência) ──────────────────────────────────────
JANELA_MOMENTUM = 3   # quantas leituras recentes usa para confirmar tendência
MIN_LEITURAS_CONSISTENTES = 2  # de quantas dessas precisa concordar na direção

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
LIVE_HISTORY_FILE = os.path.join(DATA_DIR, "live_history.json")
STATUS_FILE = os.path.join(DATA_DIR, "status.json")
PUSH_SUBS_FILE = os.path.join(DATA_DIR, "push_subscriptions.json")
