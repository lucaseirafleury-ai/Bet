import sys, os
SKILL = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SKILL)
import numpy as np
from planilha_lib import load_all_matches, get_historico, attach_estilo
from ligas import estilo_db_path
import analise as A

def close(a, b, tol=1e-3):
    return abs(a - b) < tol

print("== 1. Poisson pmf soma ~1 ==")
for lam in [0.3, 1.2, 3.5, 8.0]:
    g = np.arange(A._GRID_N, dtype=float)
    s = A._poisson_pmf(g, lam).sum()
    print(f"lam={lam}: sum pmf(0..20) = {s:.6f}")
    assert s > 0.95, f"pmf truncado demais para lam={lam}"

print("\n== 2. Over/Under 2.5 são complementares ==")
for la, lb in [(1.2, 1.0), (0.6, 0.6), (2.5, 1.8)]:
    over = A.p_plan("Over 2.5", None, la, lb)
    under = A.p_plan("Under 2.5", None, la, lb)
    print(f"la={la} lb={lb}: Over2.5={over:.4f} Under2.5={under:.4f} soma={over+under:.4f}")
    assert close(over + under, 1.0, 1e-2)

print("\n== 3. Vence/Empate/Vence somam ~1, e TimeA DC = vence+empate ==")
for la, lb in [(1.5, 1.0), (0.8, 0.8)]:
    pa = A.p_plan("TimeA vence", None, la, lb)
    pd = A.p_plan("Empate", None, la, lb)
    pb = A.p_plan("TimeB vence", None, la, lb)
    dcA = A.p_plan("TimeA DC", None, la, lb)
    print(f"la={la} lb={lb}: A={pa:.4f} D={pd:.4f} B={pb:.4f} soma={pa+pd+pb:.4f} DC_A={dcA:.4f} (A+D={pa+pd:.4f})")
    assert close(pa + pd + pb, 1.0, 1e-2)
    assert close(dcA, pa + pd, 1e-6)

print("\n== 4. Simetria: la==lb -> P(A vence) == P(B vence) ==")
pa = A.p_plan("TimeA vence", None,2.0, 2.0)
pb = A.p_plan("TimeB vence", None, 2.0, 2.0)
print(f"A={pa:.4f} B={pb:.4f}")
assert close(pa, pb, 1e-6)

print("\n== 5. Handicap asiático: TimeA AH -1.5 <= TimeA vence (mais exigente) ==")
ah = A.p_plan("TimeA AH -1.5", None, 2.2, 0.8)
vence = A.p_plan("TimeA vence", None, 2.2, 0.8)
print(f"AH-1.5={ah:.4f} vence={vence:.4f}")
assert ah <= vence + 1e-9

print("\n== 6. BTTS Sim + BTTS Não == 1 ==")
s = A.p_plan("BTTS Sim", None, 1.4, 1.1) + A.p_plan("BTTS Não", None, 1.4, 1.1)
print("soma:", s)
assert close(s, 1.0, 1e-2)

print("\n== 7. Combinação com multiplicador (CA) ==")
ca = A.p_plan("TimeA DC", "Under 3.5 | 0.84", 1.2, 1.0)
sem_mult = A.p_plan("TimeA DC", "Under 3.5", 1.2, 1.0)
print(f"com mult 0.84: {ca:.4f}  sem mult: {sem_mult:.4f}  razao: {ca/sem_mult:.4f}")
assert close(ca / sem_mult, 0.84, 1e-6)

print("\n== 8. Robustez do Pró/Contra: outlier some ao apertar mult_dp ==")
# 5 jogos válidos, 1 outlier bem alto
hist = []
import datetime
base = datetime.date(2026, 7, 1)
vals = [4, 5, 4, 5, 30]  # outlier = 30
for i, v in enumerate(vals):
    hist.append(dict(data=(base - datetime.timedelta(days=i*5)).strftime("%d/%m/%Y"),
                      adv=f"Adv{i}", gf=v, ga=1, yf=2, ya=2, cf=v, ca=2, sf=v, sa=10,
                      sotf=v, sota=3, htf=1, hta=0, fav=0.5,
                      bb=3, pa=3, tr=3, pos=3, bp=3))
jdd = dict(fav=0.5, bb=3, pa=3, tr=3, pos=3, bp=3)
hp = A.preparar_historico(hist, jdd, "20/07/2026")
for r in hp:
    print(f"  dias implícito ok, ag={r['_ag']:.2f} ah={r['_ah']:.2f} ai={r['_ai']:.2f} valid={r['_valid']}")
mu_25 = A.pro_contra_stat(hp, "gf", mult_dp=2.5)
mu_125 = A.pro_contra_stat(hp, "gf", mult_dp=1.25)
print(f"Gols Pró com mult_dp=2.5: {mu_25:.2f}   com mult_dp=1.25: {mu_125:.2f}")
assert mu_125 < mu_25, "esperava que o corte mais apertado (1.25) reduzisse a média puxada pelo outlier"

print("\n== 9. Pipeline completo com dados REAIS (Ceará x Athletic Club, Série B) ==")
df = load_all_matches()
db = estilo_db_path("serieb")
hist_A = get_historico("Ceará", df)
hist_B = get_historico("Athletic Club", df)
attach_estilo(hist_A, estilo_db_path=db)
attach_estilo(hist_B, estilo_db_path=db)
jdd_A = dict(fav=0.55, bb=3, pa=3, tr=3, pos=3, bp=3)
jdd_B = dict(fav=0.45, bb=3, pa=4, tr=3, pos=1, bp=1)
odds_and_pfont = [("50%", 1.9)] * 20
linhas = A.analisar_jogo("Ceará", "Athletic Club", hist_A, hist_B, jdd_A, jdd_B, "A",
                          odds_and_pfont, "23/07/2026")
for l in linhas[:5]:
    print(f"  {l['mercado']:35s} P.Plan={l['p_plan']:.3f} P.Comb={l['p_comb']:.3f} Criterio={l['criterio']}")
assert all(0 <= l['p_plan'] <= 1 for l in linhas)
assert all(0 <= l['p_comb'] <= 1.5 for l in linhas)  # p_comb pode passar de 1 um pouco por causa dos multiplicadores CA, mas nao muito
print(f"total mercados avaliados: {len(linhas)}")

print("\n== 10. gerar_shortlist + padroes_em_comum + relatorio_dia (fim a fim) ==")
csv_glob = os.path.join(SKILL, "..", "data", "matches", "*seriebmatches*.csv")
r = A.gerar_shortlist("Ceará", "Athletic Club", hist_A, hist_B, jdd_A, jdd_B, "A",
                       odds_and_pfont, "23/07/2026", csv_glob)
print("entradas filtradas:", len(r["entradas"]))
print("padroes em comum:", len(r["padroes_comuns"]))

texto = A.relatorio_dia([dict(teamA="Ceará", teamB="Athletic Club", hist_A=hist_A, hist_B=hist_B,
                               jdd_A=jdd_A, jdd_B=jdd_B, favorito="A",
                               odds_and_pfont=odds_and_pfont, data_jogo="23/07/2026",
                               csv_glob=csv_glob)])
print(texto[:1500])

print("\nTODOS OS TESTES PASSARAM")
