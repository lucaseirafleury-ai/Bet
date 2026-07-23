"""
ligas.py — configuração e enriquecimento POR LIGA sobre a biblioteca
compartilhada planilha_lib.py.

Substitui os antigos seriea_lib.py / serieb_lib.py (que eram ~98% idênticos,
divergindo só em nomes de arquivo e comentários) por um único módulo
parametrizado por `liga`: "copa" | "seriea" | "serieb".

O que é genuinamente igual entre ligas (histórico, clonagem de fórmulas,
build_workbook, ajuste de mando, fórmula Pró/Contra, sanitização de XML) já
está em planilha_lib.py. Aqui fica só o que MUDA por competição:
  - onde estão os CSVs agregados de liga/time/jogador (league.csv/teams.csv/
    teams2.csv/players.csv) — só Série A/B têm; Copa (seleções) não tem.
  - qual banco de estilos usar.
  - se a competição é de mando neutro (Copa) ou tem mando real (Série A/B).
  - o prefixo do arquivo de saída (Copa_/SerieA_/SerieB_).

Uso típico:

    import sys
    sys.path.insert(0, "/mnt/skills/user/planilha-liga-dia/scripts")
    from planilha_lib import *
    from ligas import *

    liga = "serieb"
    stats = league_stats(liga)                 # médias da temporada
    df = load_all_matches()                    # partidas (planilha_lib)
    hist_A = get_historico("Ceará", df)
    attach_estilo(hist_A, estilo_db_path=estilo_db_path(liga))
    mu = corner_matchup(liga, "Ceará", "Athletic Club", fav_em_casa=True)
    props = player_props(liga, "Ceará", top=4)
    ...
    aplicar_ajuste_mando(path, k=mando_shrink_k_default(liga), home_teams={"Ceará"})
"""
import os
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA = os.path.join(_HERE, "..", "data")


class LigaConfig:
    def __init__(self, nome, estilo_db, neutro, output_prefix,
                 footystats_dir=None, mando_shrink_k=None, csv_alias=None):
        self.nome = nome
        self.estilo_db = estilo_db
        self.neutro = neutro                  # True = torneio neutro (Copa) -> sem ajuste de mando
        self.output_prefix = output_prefix
        self.footystats_dir = footystats_dir  # None p/ Copa (sem CSVs agregados de liga/jogador)
        self.mando_shrink_k = mando_shrink_k  # default de k para aplicar_ajuste_mando
        self.csv_alias = csv_alias or {}


LIGAS = {
    "copa": LigaConfig(
        nome="Copa do Mundo 2026",
        estilo_db=os.path.join(_DATA, "estilos_selecoes.json"),
        neutro=True,
        output_prefix="Copa_",
        csv_alias={"USMNT": "USA", "Congo DR": "DR Congo"},
    ),
    "seriea": LigaConfig(
        nome="Brasileirão Série A 2026",
        estilo_db=os.path.join(_DATA, "estilos_seriea.json"),
        neutro=False,
        output_prefix="SerieA_",
        footystats_dir=os.path.join(_DATA, "footystats", "seriea"),
        mando_shrink_k=0.35,  # ponto de partida herdado da Série B, recalibrar (ver SKILL.md)
    ),
    "serieb": LigaConfig(
        nome="Brasileirão Série B 2026",
        estilo_db=os.path.join(_DATA, "estilos_serieb.json"),
        neutro=False,
        output_prefix="SerieB_",
        footystats_dir=os.path.join(_DATA, "footystats", "serieb"),
        mando_shrink_k=0.35,
    ),
}


def _cfg(liga):
    if liga not in LIGAS:
        raise ValueError(f"Liga desconhecida: {liga!r}. Use uma de {list(LIGAS)}.")
    return LIGAS[liga]


def estilo_db_path(liga):
    """Caminho do banco de estilos desta liga. Passe como estilo_db_path=
    em attach_estilo/save_estilo_db (planilha_lib) para não misturar bancos
    entre competições."""
    return _cfg(liga).estilo_db


def output_path_for(liga, sufixo):
    """Ex.: output_path_for('serieb', '13jul') -> 'SerieB_13jul.xlsx'
    (sufixo é livre — dia+mês, rodada, o que fizer sentido)."""
    return f"{_cfg(liga).output_prefix}{sufixo}.xlsx"


def csv_alias(liga):
    return dict(_cfg(liga).csv_alias)


def is_neutro(liga):
    return _cfg(liga).neutro


def mando_shrink_k_default(liga):
    """Default de k para aplicar_ajuste_mando() nesta liga. Levanta erro para
    torneios neutros (Copa), onde o ajuste de mando não se aplica -- não há
    mandante real."""
    cfg = _cfg(liga)
    if cfg.neutro:
        raise ValueError(
            f"{cfg.nome} é torneio neutro — aplicar_ajuste_mando não se aplica "
            f"(não há mandante real; jogos são em sede neutra)."
        )
    return cfg.mando_shrink_k


def _require_footystats(liga):
    cfg = _cfg(liga)
    if cfg.footystats_dir is None:
        raise ValueError(
            f"A liga '{liga}' ({cfg.nome}) não tem CSVs agregados de liga/time/"
            f"jogador — isso só existe para ligas de clube (Série A/B). "
            f"league_stats/team_corner_profile/corner_matchup/player_props "
            f"não se aplicam à Copa (seleções)."
        )
    return cfg.footystats_dir


# ---------------------------------------------------------------------------
# 1. LIGA — médias agregadas da temporada (só Série A/B)
# ---------------------------------------------------------------------------

def league_stats(liga):
    """Retorna um dict achatado com as médias da temporada corrente da liga
    (gols, %Under/Over, BTTS, clean sheets, escanteios, cartões, vantagem de
    mando). Use para calibrar priors ANTES de montar mercados."""
    fs = _require_footystats(liga)
    l = pd.read_csv(os.path.join(fs, "league.csv")).iloc[0]
    g = lambda k: l[k] if k in l else None
    return {
        "jogos_completos": int(g("matches_completed")),
        "media_gols": float(g("average_goals_per_match")),
        "btts_pct": int(g("btts_percentage")),
        "clean_sheets_pct": int(g("clean_sheets_percentage")),
        "over_15_pct": int(g("over_15_percentage")),
        "over_25_pct": int(g("over_25_percentage")),
        "under_25_pct": int(g("under_25_percentage")),
        "over_35_pct": int(g("over_35_percentage")),
        "media_escanteios": float(g("average_corners_per_match")),
        "over_95_corners_pct": int(g("over_95_corners_percentage")),
        "over_105_corners_pct": int(g("over_105_corners_percentage")),
        "media_cartoes": float(g("average_cards_per_match")),
        "over_35_cards_pct": int(g("over_35_cards_percentage")),
        "over_45_cards_pct": int(g("over_45_cards_percentage")),
        "vantagem_mando_pct": int(g("home_advantage_percentage")),
        "prediction_risk": int(g("prediction_risk")),
    }


def _resolve_team(name, series, alias=None):
    """Acha o nome exato de `name` dentro de uma Series de nomes de time,
    tentando alias e, por fim, correspondência por 'começa com'."""
    alias = alias or {}
    name = alias.get(name, name)
    vals = set(series.dropna())
    if name in vals:
        return name
    for v in vals:  # fallback tolerante
        if v.lower().startswith(name.lower()) or name.lower().startswith(v.lower()):
            return v
    return None


# ---------------------------------------------------------------------------
# 2. TIMES — escanteios/cartões pró e CONTRA, casa/fora (Princípio 5)
# ---------------------------------------------------------------------------

def team_corner_profile(liga, team):
    """Perfil de escanteios/cartões do time na temporada, com o lado CEDIDO
    (fundamental p/ Princípio 5: o gatilho de Over escanteios é o adversário
    que CEDE muitos, não o estilo inferido).

    Retorna dict com esc_pro_j, esc_contra_j, esc_pro_casa, esc_contra_casa,
    cart_pro_j, e o número de jogos — tudo por-jogo quando disponível.
    """
    fs = _require_footystats(liga)
    alias = csv_alias(liga)
    t = pd.read_csv(os.path.join(fs, "teams.csv"))
    t2 = pd.read_csv(os.path.join(fs, "teams2.csv"))
    key = _resolve_team(team, t["common_name"], alias)
    r = t[t["common_name"] == key].iloc[0]
    mp = r["matches_played"] or 1
    out = {
        "nome": team,
        "jogos": int(mp),
        "esc_pro_j": round(r["corners_total"] / mp, 2),
        "cart_pro_j": round(r["cards_total"] / mp, 2),
        "clean_sheets": int(r["clean_sheets"]),
        "btts_count": int(r["btts_count"]),
    }
    # teams2 tem os splits por-jogo já calculados e o lado CONTRA
    key2 = _resolve_team(team, t2["team_name"], alias) or _resolve_team(team, t2.get("common_name", pd.Series()), alias)
    row2 = None
    if key2 is not None and key2 in set(t2["team_name"]):
        row2 = t2[t2["team_name"] == key2].iloc[0]
    elif "common_name" in t2.columns:
        m = t2[t2["common_name"] == team]
        if len(m):
            row2 = m.iloc[0]
    if row2 is not None:
        def gv(k):
            return round(float(row2[k]), 2) if k in row2 and pd.notna(row2[k]) else None
        out.update({
            "esc_pro_j_overall": gv("corners_total_per_match_overall") or gv("corners_total_per_match"),
            "esc_pro_casa": gv("corners_total_per_match_home"),
            "esc_pro_fora": gv("corners_total_per_match_away"),
            "esc_contra_j": gv("corners_against_per_match_overall"),
            "esc_contra_casa": gv("corners_against_per_match_home"),
            "esc_contra_fora": gv("corners_against_per_match_away"),
        })
    return out


def corner_matchup(liga, fav, dog, fav_em_casa=True):
    """Estima escanteios do FAVORITO combinando o que ele PRODUZ com o que o
    adversário CEDE. Sinaliza se o cenário do Princípio 5 se sustenta pelos
    NÚMEROS (dog cede muito) em vez de só pelo estilo.

    Retorna dict com esc_fav_estimado e um flag p5_por_numeros.
    """
    pf = team_corner_profile(liga, fav)
    pdog = team_corner_profile(liga, dog)
    prod = pf.get("esc_pro_casa" if fav_em_casa else "esc_pro_fora") or pf["esc_pro_j"]
    cede = pdog.get("esc_contra_fora" if fav_em_casa else "esc_contra_casa") or pdog.get("esc_contra_j")
    est = None
    if prod is not None and cede is not None:
        est = round((prod + cede) / 2, 1)  # média simples produz/cede
    liga_media = league_stats(liga)["media_escanteios"] / 2  # ~esc por time/jogo
    return {
        "esc_fav_produz": prod,
        "esc_dog_cede": cede,
        "esc_fav_estimado": est,
        "media_liga_por_time": round(liga_media, 1),
        # gatilho por números: dog cede acima da média E fav produz acima da média
        "p5_por_numeros": bool(est and cede and prod and cede > liga_media and prod > liga_media),
    }


# ---------------------------------------------------------------------------
# 3. JOGADORES — âncoras de props (chutes / cartões)
# ---------------------------------------------------------------------------

def player_props(liga, team, top=4, min_apps=5):
    """Retorna os principais atletas do time como candidatos a prop âncora,
    ordenados por chutes/jogo. Cada item traz chutes/jogo, chutes no gol/90,
    gols, e cartões/90 — para montar 'X + de N chutes' (alta prob., independe
    do placar) e leitura de risco de cartão.
    """
    fs = _require_footystats(liga)
    alias = csv_alias(liga)
    p = pd.read_csv(os.path.join(fs, "players.csv"))
    key = _resolve_team(team, p["Current Club"], alias)
    sub = p[p["Current Club"] == key].copy()
    sub = sub[sub["appearances_overall"] >= min_apps]
    sub = sub.sort_values("shots_per_game_overall", ascending=False).head(top)
    props = []
    for _, r in sub.iterrows():
        props.append({
            "nome": r["full_name"],
            "pos": r["position"],
            "jogos": int(r["appearances_overall"]),
            "gols": int(r["goals_overall"]),
            "chutes_por_jogo": round(float(r["shots_per_game_overall"]), 2),
            "chutes_gol_90": round(float(r["shots_on_target_per_90_overall"]), 2),
            "cartoes_90": round(float(r["cards_per_90_overall"]), 2),
        })
    return props
